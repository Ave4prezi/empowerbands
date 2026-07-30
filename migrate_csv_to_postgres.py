"""One-time migration of customers.csv into PostgreSQL.

Set DATABASE_URL, or set PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD,
then run: python migrate_csv_to_postgres.py
"""
import csv
import os
from pathlib import Path

import psycopg
from werkzeug.security import generate_password_hash


def connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg.connect(url)
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "empowerbands"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def main():
    source = Path(__file__).with_name("customers.csv")
    if not source.exists():
        raise SystemExit(f"Missing {source}")

    with source.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    inserted = 0
    updated = 0
    with connect() as conn, conn.cursor() as cur:
        for row in rows:
            band_id = (row.get("band_id") or "").strip().upper()
            if not band_id:
                continue
            cur.execute("SELECT 1 FROM members WHERE UPPER(band_id)=UPPER(%s)", (band_id,))
            exists = cur.fetchone() is not None
            cur.execute(
                """
                INSERT INTO members (
                    band_id, full_name, email, primary_phone, emergency_contacts,
                    emergency_emails, age_group, public_condition, public_instructions,
                    private_medical_notes, pin_hash, address, race, gender, photo_url
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (band_id) DO UPDATE SET
                    full_name=EXCLUDED.full_name,
                    email=EXCLUDED.email,
                    primary_phone=EXCLUDED.primary_phone,
                    emergency_contacts=EXCLUDED.emergency_contacts,
                    emergency_emails=EXCLUDED.emergency_emails,
                    age_group=EXCLUDED.age_group,
                    public_condition=EXCLUDED.public_condition,
                    public_instructions=EXCLUDED.public_instructions,
                    private_medical_notes=EXCLUDED.private_medical_notes,
                    pin_hash=EXCLUDED.pin_hash,
                    address=EXCLUDED.address,
                    race=EXCLUDED.race,
                    gender=EXCLUDED.gender,
                    photo_url=EXCLUDED.photo_url,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    band_id,
                    (row.get("name") or "").strip(),
                    (row.get("email") or "").strip(),
                    (row.get("phone") or "").strip(),
                    (row.get("emergency_phones") or "").strip(),
                    (row.get("emergency_emails") or "").strip(),
                    (row.get("age_group") or "").strip(),
                    (row.get("condition") or "").strip(),
                    (row.get("instructions") or "").strip(),
                    (row.get("medical_notes") or "").strip(),
                    generate_password_hash((row.get("pin") or "1234").strip()),
                    (row.get("address") or "").strip(),
                    (row.get("race") or "").strip(),
                    (row.get("gender") or "").strip(),
                    (row.get("photo_url") or "").strip(),
                ),
            )
            updated += int(exists)
            inserted += int(not exists)

    print(f"Migration complete: {inserted} inserted, {updated} updated.")


if __name__ == "__main__":
    main()
