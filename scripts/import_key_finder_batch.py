"""Private one-time Key Finder inventory import.

Usage (from a trusted administrator machine with DATABASE_URL configured):
    python scripts/import_key_finder_batch.py /private/path/batch.csv

NEVER commit the batch CSV, serial numbers, or database credentials to GitHub.
Requires the key_finder_devices schema deployed first.
"""
import argparse
import csv
import hashlib
import hmac
import os
import re

import psycopg

SERIAL_RE = re.compile(r"^(?:KF|PF)-[A-Z0-9]{8,24}$")
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


def import_rows(conn, rows, pepper, old_pepper=None):
    """Verify trusted inventory; rotation requires proof with the previous pepper.

    The caller owns the transaction. Never replace consumed secrets or owners.
    """
    with conn.cursor() as cur:
        for serial, token, code in rows:
            message = ("activation:" + serial + ":" + code).encode()
            secret_hash = hmac.new(pepper.encode(), message, hashlib.sha256).hexdigest()
            cur.execute("""INSERT INTO key_finder_devices
                (serial, recovery_identifier, activation_secret_hash)
                VALUES (%s, %s, %s) ON CONFLICT (serial) DO NOTHING""",
                (serial, token, secret_hash))
            if cur.rowcount:
                continue
            cur.execute("""SELECT recovery_identifier, activation_secret_hash, activated_at
                FROM key_finder_devices WHERE serial=%s FOR UPDATE""", (serial,))
            existing = cur.fetchone()
            if not existing or existing[0] not in (None, token):
                raise ValueError("Existing recovery identifier does not match trusted inventory.")
            if existing[2] is not None:
                if existing[0] != token:
                    raise ValueError("Activated inventory needs separate recovery repair.")
                continue  # A consumed activation hash must never be restored.
            matches = hmac.compare_digest(existing[1], secret_hash)
            if not matches and old_pepper:
                old_hash = hmac.new(old_pepper.encode(), message, hashlib.sha256).hexdigest()
                matches = hmac.compare_digest(existing[1], old_hash)
            if not matches:
                raise ValueError("Activation hash mismatch; rotation requires the matching previous pepper.")
            cur.execute("""UPDATE key_finder_devices SET recovery_identifier=%s,
                activation_secret_hash=%s WHERE serial=%s AND activated_at IS NULL""",
                (token, secret_hash, serial))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_csv")
    parser.add_argument("--rotate-unclaimed", action="store_true",
                        help="Verify with KEY_FINDER_PREVIOUS_ACTIVATION_PEPPER before rehashing unclaimed inventory")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    pepper = os.environ.get("KEY_FINDER_ACTIVATION_PEPPER")
    if not database_url or not pepper or len(pepper) < 32:
        raise SystemExit("DATABASE_URL and a 32+ character KEY_FINDER_ACTIVATION_PEPPER are required.")
    old_pepper = os.environ.get("KEY_FINDER_PREVIOUS_ACTIVATION_PEPPER") if args.rotate_unclaimed else None
    if args.rotate_unclaimed and (not old_pepper or len(old_pepper) < 32):
        raise SystemExit("Rotation requires a 32+ character KEY_FINDER_PREVIOUS_ACTIVATION_PEPPER.")
    rows = list(load_rows(args.batch_csv))
    with psycopg.connect(database_url) as conn:
        import_rows(conn, rows, pepper, old_pepper)
        conn.commit()
    print("Imported/verified 25 Key Finder inventory records. No devices activated.")


if __name__ == "__main__":
    main()
