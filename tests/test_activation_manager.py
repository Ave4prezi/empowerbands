import csv
import io
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

from activation_manager import (
    BATCH_SIZES,
    CODE_ALPHABET,
    GeneratedBatch,
    generate_secure_code,
    register_activation_manager,
)


class MemoryRepository:
    rows = []
    batch_number = 0

    def __init__(self, _database_url):
        pass

    @classmethod
    def reset(cls):
        cls.rows = []
        cls.batch_number = 0

    def ensure_schema(self):
        return None

    def list_records(self, query="", status="all", store=""):
        rows = self.rows
        if query:
            rows = [r for r in rows if query.upper() in r["band_id"].upper()]
        if status == "available":
            rows = [r for r in rows if not r["claimed"]]
        if status == "claimed":
            rows = [r for r in rows if r["claimed"]]
        if store:
            rows = [r for r in rows if store.lower() in (r["assigned_to"] or "").lower()]
        return list(reversed(rows))

    def counts(self):
        return {
            "total": len(self.rows),
            "available": sum(not r["claimed"] for r in self.rows),
            "claimed": sum(r["claimed"] for r in self.rows),
            "assigned": sum(bool(r["assigned_to"]) for r in self.rows),
        }

    def generate(self, count):
        if count not in BATCH_SIZES:
            raise ValueError
        self.__class__.batch_number += 1
        batch_id = f"{self.batch_number:032x}"
        existing_numbers = [int(r["band_id"][2:]) for r in self.rows]
        next_number = max(existing_numbers, default=0) + 1
        records = []
        for offset in range(count):
            band_id = f"EB{next_number + offset:03d}"
            code = generate_secure_code()
            if any(r["band_id"] == band_id or r["activation_code"] == code for r in self.rows):
                raise ValueError("duplicate")
            record = {
                "band_id": band_id, "activation_code": code, "claimed": False,
                "created_at": datetime.now(timezone.utc), "claimed_at": None,
                "assigned_to": None, "assigned_at": None, "notes": None,
                "batch_id": batch_id, "code_rotated_at": None,
            }
            self.rows.append(record)
            records.append(record.copy())
        return GeneratedBatch(batch_id, records)

    def assign(self, band_id, assigned_to, notes):
        row = next((r for r in self.rows if r["band_id"] == band_id), None)
        if row is None or row["claimed"]:
            return False
        row.update(assigned_to=assigned_to or None, notes=notes or None,
                   assigned_at=datetime.now(timezone.utc) if assigned_to else None)
        return True

    def rotate_unclaimed(self, band_id):
        row = next((r for r in self.rows if r["band_id"] == band_id), None)
        if row is None:
            return None
        if row["claimed"]:
            raise ValueError("Claimed Safety IDs cannot be rotated here.")
        old = row["activation_code"]
        while row["activation_code"] == old:
            row["activation_code"] = generate_secure_code()
        row["code_rotated_at"] = datetime.now(timezone.utc)
        return row["activation_code"]

    def records_for_print(self, band_id="", batch_id=""):
        return [r for r in self.rows if r["band_id"] == band_id or r["batch_id"] == batch_id]


class ActivationManagerTests(unittest.TestCase):
    def setUp(self):
        MemoryRepository.reset()
        template_dir = Path(__file__).resolve().parents[1] / "templates"
        self.app = Flask(__name__, template_folder=str(template_dir))
        self.app.secret_key = "test-key"
        self.app.config.update(TESTING=True)

        @self.app.route("/admin")
        def admin():
            return "login"

        @self.app.route("/dashboard")
        def dashboard():
            return "dashboard"

        register_activation_manager(
            self.app, lambda: "test-database", "/static/logo.jpeg",
            "https://www.empowerbands.org", MemoryRepository,
        )
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def csrf(self):
        self.client.get("/admin/activation-codes")
        with self.client.session_transaction() as session:
            return session["activation_manager_csrf"]

    def generate(self, count):
        return self.client.post(
            "/admin/activation-codes/generate",
            data={"csrf_token": self.csrf(), "count": str(count)},
        )

    def test_unauthorized_admin_access_redirects(self):
        response = self.client.get("/admin/activation-codes")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin", response.location)

    def test_generation_requires_csrf(self):
        self.login()
        self.assertEqual(self.client.post("/admin/activation-codes/generate", data={"count": "1"}).status_code, 400)

    def test_generate_one_and_batch_are_sequential_and_secure(self):
        self.login()
        self.assertEqual(self.generate(1).status_code, 302)
        self.assertEqual(self.generate(10).status_code, 302)
        self.assertEqual([r["band_id"] for r in MemoryRepository.rows], [f"EB{i:03d}" for i in range(1, 12)])
        codes = [r["activation_code"] for r in MemoryRepository.rows]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(len(code) == 8 and set(code) <= set(CODE_ALPHABET) for code in codes))
        self.assertTrue(all(not set(code) & set("O0I1") for code in codes))

    def test_rejects_unsupported_batch_and_duplicate_constraints_exist(self):
        self.login()
        self.assertEqual(self.generate(7).status_code, 400)
        migration = Path("migrations/20260929_activation_code_manager.sql").read_text()
        self.assertIn("UNIQUE INDEX", migration)
        self.assertIn("UPPER(band_id)", migration)
        self.assertIn("UPPER(activation_code)", migration)

    def test_assignment_filter_and_csv_export(self):
        self.login(); self.generate(1)
        token = self.csrf()
        response = self.client.post("/admin/activation-codes/assign", data={
            "csrf_token": token, "band_id": "EB001", "assigned_to": "Main Street Store", "notes": "Shelf A"
        })
        self.assertEqual(response.status_code, 302)
        filtered = self.client.get("/admin/activation-codes?store=Main+Street")
        self.assertIn(b"Main Street Store", filtered.data)
        exported = self.client.get("/admin/activation-codes/export.csv")
        rows = list(csv.DictReader(io.StringIO(exported.get_data(as_text=True))))
        self.assertEqual(rows[0]["assigned_to"], "Main Street Store")
        self.assertEqual(exported.headers["Cache-Control"], "no-store, max-age=0")

    def test_rotate_unused_requires_confirmation_and_changes_code(self):
        self.login(); self.generate(1)
        old_code = MemoryRepository.rows[0]["activation_code"]
        token = self.csrf()
        bad = self.client.post("/admin/activation-codes/rotate", data={"csrf_token": token, "band_id": "EB001", "confirmation": "EB999"})
        self.assertEqual(bad.status_code, 400)
        good = self.client.post("/admin/activation-codes/rotate", data={"csrf_token": token, "band_id": "EB001", "confirmation": "EB001"})
        self.assertEqual(good.status_code, 302)
        self.assertNotEqual(MemoryRepository.rows[0]["activation_code"], old_code)

    def test_claimed_code_cannot_be_rotated_assigned_or_printed(self):
        self.login(); self.generate(1)
        MemoryRepository.rows[0]["claimed"] = True
        token = self.csrf()
        rotate = self.client.post("/admin/activation-codes/rotate", data={"csrf_token": token, "band_id": "EB001", "confirmation": "EB001"})
        self.assertEqual(rotate.status_code, 302)
        assign = self.client.post("/admin/activation-codes/assign", data={"csrf_token": token, "band_id": "EB001", "assigned_to": "Other", "notes": ""})
        self.assertEqual(assign.status_code, 404)
        self.assertEqual(self.client.get("/admin/activation-codes/print?band_id=EB001").status_code, 409)

    def test_print_card_has_qr_and_exact_activation_url(self):
        self.login(); self.generate(1)
        response = self.client.get("/admin/activation-codes/print?band_id=EB001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data:image/png;base64", response.data)
        self.assertIn(b"https://www.empowerbands.org/activate/EB001", response.data)
        self.assertIn(b"Protect What Matters Most", response.data)

    def test_malformed_manager_requests(self):
        self.login()
        token = self.csrf()
        self.assertEqual(self.client.post("/admin/activation-codes/assign", data={"csrf_token": token, "band_id": "bad id"}).status_code, 400)
        self.assertEqual(self.client.get("/admin/activation-codes/print?batch=not-a-batch").status_code, 400)


if __name__ == "__main__":
    unittest.main()
