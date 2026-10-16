"""Private one-time Key Finder inventory import.

Usage (from a trusted administrator machine with DATABASE_URL configured):
    python scripts/import_key_finder_batch.py /private/path/batch.csv

NEVER commit the batch CSV, serial numbers, or database credentials to GitHub.
Requires the key_finder_devices schema deployed first.
"""
import csv
import hashlib
import hmac
import os
import re
import sys

import psycopg

SERIAL_RE = re.compile(r"^KF-[A-Z0-9]{8,24}$")
RECOVERY_RE = re.compile(r"^[A-Z0-9]{20}$")
EXPECTED_HOST = "https://empowerbands.org/k/"


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 25:
        raise ValueError("Expected exactly 25 records in the first batch.")
    seen_serials, seen_tokens, seen_codes = set(), set(), set()
    for row in rows:
        serial = row["activation_card_serial"].strip().upper()
        token = row["nfc_recovery_identifier"].strip().upper()
        url = row["nfc_recovery_url"].strip()
        code = row["hidden_activation_code"].strip().upper()
        if not SERIAL_RE.fullmatch(serial) or not RECOVERY_RE.fullmatch(token):
            raise ValueError("Invalid serial or recovery identifier.")
        if not re.fullmatch(r"[A-Z0-9]{24}", code) or code in seen_codes:
            raise ValueError("Invalid or duplicate hidden activation code.")
        if url != EXPECTED_HOST + token:
            raise ValueError("Recovery URL and identifier mismatch.")
        if serial in seen_serials or token in seen_tokens:
            raise ValueError("Duplicate serial or recovery identifier.")
        seen_serials.add(serial)
        seen_tokens.add(token)
        seen_codes.add(code)
        yield serial, token, code


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_key_finder_batch.py /private/batch.csv")
    database_url = os.environ.get("DATABASE_URL")
    pepper = os.environ.get("KEY_FINDER_ACTIVATION_PEPPER")
    if not database_url or not pepper or len(pepper) < 32:
        raise SystemExit("DATABASE_URL and a 32+ character KEY_FINDER_ACTIVATION_PEPPER are required.")
    rows = list(load_rows(sys.argv[1]))
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for serial, token, code in rows:
                secret_hash = hmac.new(pepper.encode(), ("activation:" + serial + ":" + code).encode(), hashlib.sha256).hexdigest()
                cur.execute("""
                    INSERT INTO key_finder_devices
                        (serial, recovery_identifier, activation_secret_hash)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (serial) DO NOTHING
                """, (serial, token, secret_hash))
                if cur.rowcount == 0:
                    cur.execute("SELECT recovery_identifier, activation_secret_hash FROM key_finder_devices WHERE serial=%s", (serial,))
                    existing = cur.fetchone()
                    if not existing or existing[0] != token or not hmac.compare_digest(existing[1], secret_hash):
                        raise ValueError("Serial already registered with a different recovery URL.")
        conn.commit()
    print("Imported/verified 25 Key Finder inventory records. No devices activated.")


if __name__ == "__main__":
    main()
