"""Database integration checks for single-use activation and failed attempts."""
import concurrent.futures
import hashlib
import hmac
import os
import secrets
import unittest
from unittest.mock import patch

from scripts.import_key_finder_batch import import_rows

import psycopg
from flask import Flask

from key_finder_backend import initialize_key_finders, key_finder_api


class KeyFinderDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL"):
            raise unittest.SkipTest("Disposable test database unavailable")
        initialize_key_finders()

    def setUp(self):
        self.serial = "KF-" + secrets.token_hex(6).upper()
        self.code = secrets.token_hex(12).upper()
        self.app = Flask(__name__)
        self.app.secret_key = "integration-test-session"
        self.app.register_blueprint(key_finder_api)
        pepper = os.environ["KEY_FINDER_ACTIVATION_PEPPER"]
        digest = hmac.new(pepper.encode(),
            ("activation:" + self.serial + ":" + self.code).encode(),
            hashlib.sha256).hexdigest()
        self.recovery = secrets.token_hex(10).upper()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute("""INSERT INTO key_finder_devices
                (serial, activation_secret_hash, recovery_identifier)
                VALUES (%s,%s,%s)""",
                (self.serial, digest, self.recovery))

    def _claim(self, code, email):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["kf_email"] = email
                sess["kf_csrf"] = "testcsrf"
            return client.post("/key-finder/claim",
                data={"serial": self.serial, "activation_code": code, "csrf": "testcsrf"},
                headers={"Origin": "http://localhost"},
                environ_overrides={"REMOTE_ADDR": "192.0.2." + str(secrets.randbelow(200) + 1)}).status_code

    def test_concurrent_claims_only_one_owner(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda email: self._claim(self.code, email),
                ["one@example.test", "two@example.test"]))
        self.assertEqual(outcomes.count(303), 1, outcomes)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            row = conn.execute("SELECT owner_email, activated_at FROM key_finder_devices WHERE serial=%s",
                (self.serial,)).fetchone()
        self.assertIn(row[0], ("one@example.test", "two@example.test"))
        self.assertIsNotNone(row[1])

    def test_bad_code_does_not_activate(self):
        result = self._claim("A" * 24, "wrong@example.test")
        self.assertEqual(result, 400)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            row = conn.execute("SELECT activated_at FROM key_finder_devices WHERE serial=%s",
                (self.serial,)).fetchone()
        self.assertIsNone(row[0])

    def test_five_failed_claims_are_throttled(self):
        outcomes = [self._claim("B" * 24, "limit@example.test") for _ in range(6)]
        self.assertEqual(outcomes[:5], [400] * 5)
        self.assertEqual(outcomes[5], 429)


    def test_email_to_recovery_and_cross_owner_rejection(self):
        email = secrets.token_hex(8) + "@example.test"
        client = self.app.test_client()
        def post(route, **data):
            with client.session_transaction() as sess:
                csrf = sess.get("kf_csrf", "")
            return client.post("/key-finder/" + route, data=dict(data, csrf=csrf),
                headers={"Origin": "http://localhost"})
        client.get("/key-finder/account")
        with patch("key_finder_backend._email_code") as send:
            self.assertEqual(post("send-code", email=email).status_code, 303)
            code = send.call_args.args[1]
        self.assertEqual(post("verify-code", email=email, code=code).status_code, 303)
        self.assertEqual(post("verify-code", email=email, code=code).status_code, 400)
        self.assertEqual(post("claim", serial=self.serial, activation_code=self.code).status_code, 303)
        self.assertEqual(post("update", serial=self.serial, label="House keys", contact_email=email,
                              visible="on", lost="on").status_code, 303)
        self.assertIn(b"House keys", client.get("/key-finder/account").data)
        for path in ["/k/" + self.recovery, "/key-finder/found?serial=" + self.serial]:
            response = client.get(path)
            self.assertIn(email.encode(), response.data)
            self.assertIn(b"reported lost", response.data)
            self.assertNotIn(self.serial.encode(), response.data)
        with client.session_transaction() as sess:
            sess["kf_email"] = "other-" + email
        self.assertEqual(post("update", serial=self.serial, label="stolen").status_code, 404)
        with client.session_transaction() as sess:
            sess["kf_email"] = email
        self.assertEqual(post("update", serial=self.serial, contact_email=email).status_code, 303)
        self.assertNotIn(email.encode(), client.get("/k/" + self.recovery).data)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            self.assertEqual(conn.execute("SELECT lost, contact_visible FROM key_finder_devices WHERE serial=%s",
                (self.serial,)).fetchone(), (False, False))
        self.assertEqual(post("logout").status_code, 303)
        self.assertEqual(post("update", serial=self.serial).status_code, 403)

    def test_missing_recovery_identifier_blocks_claim(self):
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute("UPDATE key_finder_devices SET recovery_identifier=NULL WHERE serial=%s", (self.serial,))
        self.assertEqual(self._claim(self.code, "incomplete@example.test"), 400)

    def test_import_rerun_keeps_consumed_secret(self):
        self.assertEqual(self._claim(self.code, "import@example.test"), 303)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            before = conn.execute("SELECT activation_secret_hash, owner_email FROM key_finder_devices WHERE serial=%s",
                (self.serial,)).fetchone()
            import_rows(conn, [(self.serial, self.recovery, self.code)], os.environ["KEY_FINDER_ACTIVATION_PEPPER"])
            after = conn.execute("SELECT activation_secret_hash, owner_email FROM key_finder_devices WHERE serial=%s",
                (self.serial,)).fetchone()
        self.assertEqual(before, after)

    def test_rotation_requires_previous_pepper_and_backfills_recovery(self):
        old = os.environ["KEY_FINDER_ACTIVATION_PEPPER"]
        new = "new-test-only-pepper-" + secrets.token_hex(20)
        rows = [(self.serial, self.recovery, self.code)]
        with self.assertRaises(ValueError):
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                import_rows(conn, rows, new)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute("UPDATE key_finder_devices SET recovery_identifier=NULL WHERE serial=%s", (self.serial,))
            import_rows(conn, rows, new, old)
        with patch.dict(os.environ, {"KEY_FINDER_ACTIVATION_PEPPER": new}):
            self.assertEqual(self._claim(self.code, "rotated@example.test"), 303)


if __name__ == "__main__":
    unittest.main()
