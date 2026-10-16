"""Regression tests for the Key Finder pre-launch safety gate.
Run: python -m unittest discover -s tests -p 'test_key_finder_security.py'
"""
import os
import unittest
from unittest.mock import patch
from flask import Flask

from key_finder_backend import key_finder_api, SERIAL_RE, RECOVERY_RE, _code_digest


class KeyFinderSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-only-not-production"
        self.app.register_blueprint(key_finder_api)
        self.client = self.app.test_client()

    def test_serial_alone_never_claims_device(self):
        with self.client.session_transaction() as sess:
            sess["kf_email"] = "verified@example.com"
            sess["kf_csrf"] = "testcsrf"
        response = self.client.post(
            "/key-finder/claim",
            data={"serial": "KF-12345678", "csrf": "testcsrf"},
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(response.status_code, 503)

    def test_serial_only_cannot_claim_even_without_login(self):
        response = self.client.post("/key-finder/claim", data={"serial": "KF-12345678"})
        self.assertEqual(response.status_code, 503)

    def test_recovery_url_rejects_malformed_token_without_database(self):
        response = self.client.get("/k/invalid!")
        self.assertEqual(response.status_code, 404)

    def test_identifier_format(self):
        self.assertTrue(SERIAL_RE.fullmatch("KF-12345678"))
        self.assertTrue(RECOVERY_RE.fullmatch("ABCDEFGH123456789012"))
        self.assertFalse(RECOVERY_RE.fullmatch("KF-12345678"))

    def test_email_code_hash_is_email_bound(self):
        with patch.dict(os.environ, {"KEY_FINDER_ACTIVATION_PEPPER": "a" * 48}):
            a = _code_digest("one@example.com", "123456")
            b = _code_digest("two@example.com", "123456")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
