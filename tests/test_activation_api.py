import unittest
from unittest.mock import patch

import app as app_module


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.result = None

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split()).upper()
        band_id = params[-1].upper() if params and isinstance(params[-1], str) and params[-1].upper().startswith("EB") else None
        if normalized.startswith("SELECT ACTIVATION_CODE, CLAIMED"):
            row = self.state["codes"].get(band_id)
            self.result = None if row is None else (row["code"], row["claimed"])
        elif normalized.startswith("SELECT FULL_NAME, EMAIL"):
            self.result = self.state["members"].get(band_id)
        elif normalized.startswith("INSERT INTO MEMBERS"):
            self.state["members"][params[0]] = (params[1], params[2])
            self.result = None
        elif normalized.startswith("UPDATE MEMBERS"):
            self.state["members"][band_id] = (params[0], params[1])
            self.result = None
        elif normalized.startswith("UPDATE ACTIVATION_CODES"):
            self.state["codes"][band_id]["claimed"] = True
            self.result = None
        else:
            raise AssertionError(f"Unexpected SQL in activation test: {normalized[:80]}")

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def cursor(self): return FakeCursor(self.state)
    def commit(self): return None


class ActivationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.state = {"codes": {}, "members": {}}
        app_module.app.config.update(TESTING=True)
        app_module.DATABASE_URL = "test-database"
        self.connect_patch = patch.object(app_module.psycopg, "connect", side_effect=lambda *_a, **_k: FakeConnection(self.state))
        self.connect_patch.start()

    def tearDown(self):
        self.connect_patch.stop()

    @staticmethod
    def payload(band_id="EB019", code="ABCD2345"):
        return {"bandId": band_id, "activationCode": code, "firstName": "Test", "lastName": "Person",
                "email": "test@example.com", "phone": "555-123-4567", "profileType": "adult"}

    def test_successful_activation_and_reuse_block(self):
        self.state["codes"]["EB019"] = {"code": "ABCD2345", "claimed": False}
        success = self.client.post("/api/activate", json=self.payload())
        self.assertEqual(success.status_code, 200)
        self.assertTrue(self.state["codes"]["EB019"]["claimed"])
        reused = self.client.post("/api/activate", json=self.payload())
        self.assertEqual(reused.status_code, 409)

    def test_incorrect_code_and_unknown_id(self):
        self.state["codes"]["EB019"] = {"code": "ABCD2345", "claimed": False}
        self.assertEqual(self.client.post("/api/activate", json=self.payload(code="ZZZZ9999")).status_code, 403)
        self.assertEqual(self.client.post("/api/activate", json=self.payload(band_id="EB999")).status_code, 404)

    def test_existing_customer_profile_is_never_overwritten(self):
        self.state["codes"]["EB019"] = {"code": "ABCD2345", "claimed": False}
        self.state["members"]["EB019"] = ("Existing Person", "existing@example.com")
        response = self.client.post("/api/activate", json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.state["members"]["EB019"], ("Existing Person", "existing@example.com"))
        self.assertFalse(self.state["codes"]["EB019"]["claimed"])

    def test_malformed_requests_are_rejected_before_database(self):
        self.assertEqual(self.client.post("/api/activate", data="not json").status_code, 415)
        self.assertEqual(self.client.post("/api/activate", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/activate", json=self.payload(band_id="bad id")).status_code, 400)
        bad_email = self.payload(); bad_email["email"] = "not-an-email"
        self.assertEqual(self.client.post("/api/activate", json=bad_email).status_code, 400)
        bad_phone = self.payload(); bad_phone["phone"] = "123"
        self.assertEqual(self.client.post("/api/activate", json=bad_phone).status_code, 400)

    def test_important_routes_still_respond(self):
        for path in ("/", "/activate", "/admin", "/privacy", "/terms"):
            response = self.client.get(path)
            self.assertLess(response.status_code, 500, path)


if __name__ == "__main__":
    unittest.main()
