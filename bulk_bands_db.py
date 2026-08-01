"""
Bulk band provisioning & activation — database layer.

Why a separate module instead of adding this to app.py directly:
app.py already handles the existing NFC/emergency-profile system via
customers.csv, and this feature (bulk partner orders like the 500-band
Payless Pharmacy order) is new and self-contained. Keeping it in its
own module means the existing CSV-based code in app.py is never
touched by this file, which matters for "preserve all existing
functionality."

Database engine:
    Uses SQLite by default (a local file, EMPOWERBANDS_BULK.db) — zero
    extra dependencies, works out of the box for local dev and testing.

    Set DATABASE_URL to a postgres:// or postgresql:// URL to use
    PostgreSQL in production instead (requires `pip install
    psycopg2-binary`, already added to requirements.txt).

    The SQL in this file is written with '?' placeholders (SQLite
    style) and translated to '%s' (psycopg2 style) automatically via
    the _q() helper below, so the same query text works against both
    engines without an ORM.

This module does NOT touch customers.csv, scan_log.csv, or any other
existing file — see migrate_to_db.py for the safe, non-destructive
migration plan.
"""

import csv
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("BULK_DB_PATH", "empowerbands_bulk.db")

_USING_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if _USING_POSTGRES:
    import psycopg2  # requires psycopg2-binary — see requirements.txt


class BulkGenerationError(ValueError):
    """Raised for any invalid bulk-provisioning request (bad quantity,
    duplicate batch number, colliding band IDs, etc). Callers in
    app.py should catch this and show request.form-friendly error
    text instead of a stack trace."""


def get_connection():
    """Return a DB-API connection: PostgreSQL in production if
    DATABASE_URL is set, otherwise a local SQLite file."""
    if _USING_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _q(sql):
    """Translate '?' placeholders to psycopg2's '%s' style when
    running against Postgres; passes through unchanged for SQLite."""
    return sql.replace("?", "%s") if _USING_POSTGRES else sql


def _dict_rows(cursor):
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS bands (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    band_id               TEXT UNIQUE NOT NULL,
    partner_org           TEXT NOT NULL,
    batch_number          TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'unassigned',
    activation_token      TEXT UNIQUE NOT NULL,
    date_created          TEXT NOT NULL,
    date_activated        TEXT,
    assigned_customer_id  TEXT,
    nfc_url               TEXT NOT NULL,
    qr_url                TEXT NOT NULL,
    qc_status             TEXT NOT NULL DEFAULT 'pending',
    qc_tested_nfc         INTEGER NOT NULL DEFAULT 0,
    qc_tested_qr          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bands_batch   ON bands(batch_number);
CREATE INDEX IF NOT EXISTS idx_bands_partner ON bands(partner_org);
CREATE INDEX IF NOT EXISTS idx_bands_status  ON bands(status);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    details     TEXT,
    ip_address  TEXT
);
"""


def ensure_schema():
    """Idempotently make sure the bands/audit_log tables exist,
    regardless of which engine is active (SQLite or Postgres). Safe to
    call on every app boot and as many times as needed — every
    statement uses IF NOT EXISTS.

    This is what app.py calls at startup (for BOTH engines) instead of
    only initializing SQLite and skipping Postgres — that older
    behavior meant a host environment where DATABASE_URL unexpectedly
    pointed at Postgres (some platforms set it automatically) would
    silently skip schema creation entirely, and every audit-logged
    action (including admin login) would then fail with 'no such
    table'."""
    if _USING_POSTGRES:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_postgres.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        finally:
            conn.close()
    else:
        conn = get_connection()
        try:
            conn.executescript(SCHEMA_SQLITE)
            conn.commit()
        finally:
            conn.close()


def init_db():
    """Backwards-compatible SQLite-only alias. Prefer ensure_schema(),
    which works for both engines and is what app.py calls at startup."""
    if _USING_POSTGRES:
        raise RuntimeError(
            "init_db() is SQLite-only — call ensure_schema() instead, "
            "which works for both engines."
        )
    ensure_schema()


def log_audit(actor, action, target, details="", ip_address=None):
    """Best-effort audit logging. Deliberately swallows its own
    exceptions — a database hiccup on the audit trail must never be
    able to crash the actual request (e.g. admin login) that
    triggered it. Failures are printed to stderr so they're still
    visible in host logs."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                _q("""INSERT INTO audit_log (timestamp, actor, action, target, details, ip_address)
                      VALUES (?, ?, ?, ?, ?, ?)"""),
                (datetime.now(timezone.utc).isoformat(), actor, action, target, details, ip_address or ""),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"WARNING: audit log write failed (action={action}, target={target}): {e}")


# ===============================
# BAND ID / VALIDATION HELPERS
# ===============================

BAND_ID_RE = re.compile(r"^EB(\d+)$")
BATCH_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{2,39}$")
PARTNER_NAME_RE = re.compile(r"^[A-Za-z0-9 &.,'\-]{2,80}$")

MAX_BULK_QUANTITY = 2000


def _existing_csv_band_ids(customers_csv_path="customers.csv"):
    """Band IDs already used by the legacy CSV-based customer system —
    checked so a bulk batch can never collide with an existing
    activated (or manually added) profile."""
    ids = set()
    try:
        with open(customers_csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bid = (row.get("band_id") or "").strip().upper()
                if bid:
                    ids.add(bid)
    except FileNotFoundError:
        pass
    return ids


def get_next_band_number(customers_csv_path="customers.csv"):
    """Scan both customers.csv (legacy/manually-added profiles) and
    the bulk `bands` table for the highest existing EB number, and
    return the next one. Mirrors the existing /next-band-id logic in
    app.py, but also accounts for bulk-provisioned bands."""
    highest = 0

    for bid in _existing_csv_band_ids(customers_csv_path):
        m = BAND_ID_RE.match(bid)
        if m:
            highest = max(highest, int(m.group(1)))

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT band_id FROM bands")
        for row in _dict_rows(cur):
            m = BAND_ID_RE.match(row["band_id"])
            if m:
                highest = max(highest, int(m.group(1)))
    finally:
        conn.close()

    return highest + 1


# ===============================
# BULK GENERATION
# ===============================

def create_bulk_batch(quantity, partner_org, batch_number, starting_number=None,
                       base_url="https://empowerbands.org", actor="unknown", ip_address=None):
    """Create `quantity` new bands, all status='unassigned', for one
    partner/batch. Validates everything up front and inserts in a
    single transaction — either the whole batch is created, or none
    of it is (no partially-created batches on a bad request)."""

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise BulkGenerationError("Quantity must be a whole number.")
    if quantity < 1 or quantity > MAX_BULK_QUANTITY:
        raise BulkGenerationError(f"Quantity must be between 1 and {MAX_BULK_QUANTITY}.")

    partner_org = (partner_org or "").strip()
    if not PARTNER_NAME_RE.match(partner_org):
        raise BulkGenerationError(
            "Partner organization name must be 2-80 characters "
            "(letters, numbers, spaces, and & . , ' - only)."
        )

    batch_number = (batch_number or "").strip().upper()
    if not BATCH_NUMBER_RE.match(batch_number):
        raise BulkGenerationError(
            "Batch number must be 3-40 characters: letters, numbers, and "
            "hyphens only (e.g. PYP-2026-001)."
        )

    if starting_number is not None and str(starting_number).strip():
        try:
            start = int(starting_number)
        except (TypeError, ValueError):
            raise BulkGenerationError("Starting Band ID number must be a whole number.")
        if start < 1:
            raise BulkGenerationError("Starting Band ID number must be positive.")
    else:
        start = get_next_band_number()

    end = start + quantity - 1
    candidate_ids = [f"EB{n:03d}" for n in range(start, end + 1)]

    # Reject up front against the legacy CSV system
    csv_collisions = [bid for bid in candidate_ids if bid in _existing_csv_band_ids()]
    if csv_collisions:
        raise BulkGenerationError(
            f"{len(csv_collisions)} of the requested Band IDs already exist in the "
            f"customer database (e.g. {csv_collisions[0]}). Leave 'Starting Band ID' "
            "blank to auto-continue from the next available ID."
        )

    created = []
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(_q("SELECT COUNT(*) FROM bands WHERE batch_number = ?"), (batch_number,))
        existing_batch_count = cur.fetchone()[0]
        if existing_batch_count > 0:
            raise BulkGenerationError(
                f"Batch number '{batch_number}' already has {existing_batch_count} bands. "
                "Use a new/unique batch number for a new order."
            )

        placeholders = ",".join(["?"] * len(candidate_ids))
        cur.execute(_q(f"SELECT band_id FROM bands WHERE band_id IN ({placeholders})"), candidate_ids)
        db_collisions = [r[0] for r in cur.fetchall()]
        if db_collisions:
            raise BulkGenerationError(
                f"{len(db_collisions)} of the requested Band IDs already exist "
                f"(e.g. {db_collisions[0]}). Leave 'Starting Band ID' blank to "
                "auto-continue from the next available ID."
            )

        now = datetime.now(timezone.utc).isoformat()
        tokens_used = set()
        rows_to_insert = []
        for band_id in candidate_ids:
            token = secrets.token_urlsafe(24)
            while token in tokens_used:
                token = secrets.token_urlsafe(24)
            tokens_used.add(token)
            nfc_url = f"{base_url.rstrip('/')}/{band_id}"
            rows_to_insert.append((band_id, partner_org, batch_number, token, now, nfc_url, nfc_url))
            created.append({
                "band_id": band_id, "partner_org": partner_org, "batch_number": batch_number,
                "status": "unassigned", "activation_token": token, "date_created": now,
                "date_activated": None, "assigned_customer_id": None,
                "nfc_url": nfc_url, "qr_url": nfc_url,
                "qc_status": "pending", "qc_tested_nfc": 0, "qc_tested_qr": 0,
            })

        cur.executemany(
            _q("""INSERT INTO bands
                  (band_id, partner_org, batch_number, status, activation_token,
                   date_created, nfc_url, qr_url, qc_status, qc_tested_nfc, qc_tested_qr)
                  VALUES (?, ?, ?, 'unassigned', ?, ?, ?, ?, 'pending', 0, 0)"""),
            rows_to_insert,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log_audit(
        actor, "bulk_generate", batch_number,
        f"Created {quantity} bands ({created[0]['band_id']}\u2013{created[-1]['band_id']}) "
        f"for partner '{partner_org}'",
        ip_address,
    )
    return created


# ===============================
# LOOKUPS
# ===============================

def get_band(band_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bands WHERE band_id = ?"), (band_id.strip().upper(),))
        rows = _dict_rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def get_band_by_token(token):
    token = (token or "").strip()
    if not token:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bands WHERE activation_token = ?"), (token,))
        rows = _dict_rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def list_bands(band_id=None, batch_number=None, partner_org=None, status=None, limit=500):
    """Inventory search — any combination of filters, all optional."""
    clauses, params = [], []
    if band_id:
        clauses.append("band_id LIKE ?")
        params.append(f"%{band_id.strip().upper()}%")
    if batch_number:
        clauses.append("batch_number LIKE ?")
        params.append(f"%{batch_number.strip().upper()}%")
    if partner_org:
        clauses.append("partner_org LIKE ?")
        params.append(f"%{partner_org.strip()}%")
    if status:
        clauses.append("status = ?")
        params.append(status.strip())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q(f"SELECT * FROM bands {where} ORDER BY id DESC LIMIT ?"), params + [limit])
        return _dict_rows(cur)
    finally:
        conn.close()


def list_batches():
    """Distinct batches with counts, for the batch report / bulk-bands landing page."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT batch_number, partner_org, COUNT(*) AS total,
                   MIN(date_created) AS date_created
            FROM bands
            GROUP BY batch_number, partner_org
            ORDER BY date_created DESC
        """)
        return _dict_rows(cur)
    finally:
        conn.close()


def partner_stats():
    """Aggregate counts per partner for the partner dashboard."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT partner_org, status, COUNT(*) AS n FROM bands GROUP BY partner_org, status")
        rows = _dict_rows(cur)
    finally:
        conn.close()

    stats = {}
    for r in rows:
        p = stats.setdefault(r["partner_org"], {
            "total": 0, "unassigned": 0, "active": 0, "lost": 0, "replaced": 0,
        })
        p["total"] += r["n"]
        if r["status"] in p:
            p[r["status"]] += r["n"]

    for p in stats.values():
        p["activation_pct"] = round((p["active"] / p["total"]) * 100, 1) if p["total"] else 0.0

    return stats


# ===============================
# STATE CHANGES
# ===============================

def activate_band(band_id, actor="customer", ip_address=None):
    """Flip a band from 'unassigned' to 'active' and record who/when.
    Only succeeds if the band is currently 'unassigned' — prevents
    re-activating an already-active band or racing two activations
    for the same band."""
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            _q("""UPDATE bands SET status = 'active', date_activated = ?,
                  assigned_customer_id = ? WHERE band_id = ? AND status = 'unassigned'"""),
            (now, band_id, band_id),
        )
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "activate_band", band_id, "Customer completed activation", ip_address)
    return bool(updated)


def update_qc(band_id, qc_status, tested_nfc, tested_qr, actor="admin", ip_address=None):
    if qc_status not in ("pending", "passed", "failed"):
        raise BulkGenerationError("Invalid QC status.")
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            _q("UPDATE bands SET qc_status = ?, qc_tested_nfc = ?, qc_tested_qr = ? WHERE band_id = ?"),
            (qc_status, int(bool(tested_nfc)), int(bool(tested_qr)), band_id),
        )
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "qc_update", band_id,
                   f"qc_status={qc_status} nfc_tested={bool(tested_nfc)} qr_tested={bool(tested_qr)}",
                   ip_address)
    return bool(updated)


def update_status(band_id, new_status, actor="admin", ip_address=None):
    if new_status not in ("unassigned", "active", "lost", "replaced"):
        raise BulkGenerationError("Invalid status.")
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("UPDATE bands SET status = ? WHERE band_id = ?"), (new_status, band_id))
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "status_update", band_id, f"status={new_status}", ip_address)
    return bool(updated)
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("BULK_DB_PATH", "empowerbands_bulk.db")

_USING_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if _USING_POSTGRES:
    import psycopg2  # requires psycopg2-binary — see requirements.txt


class BulkGenerationError(ValueError):
    """Raised for any invalid bulk-provisioning request (bad quantity,
    duplicate batch number, colliding band IDs, etc). Callers in
    app.py should catch this and show request.form-friendly error
    text instead of a stack trace."""


def get_connection():
    """Return a DB-API connection: PostgreSQL in production if
    DATABASE_URL is set, otherwise a local SQLite file."""
    if _USING_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _q(sql):
    """Translate '?' placeholders to psycopg2's '%s' style when
    running against Postgres; passes through unchanged for SQLite."""
    return sql.replace("?", "%s") if _USING_POSTGRES else sql


def _dict_rows(cursor):
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS bands (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    band_id               TEXT UNIQUE NOT NULL,
    partner_org           TEXT NOT NULL,
    batch_number          TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'unassigned',
    activation_token      TEXT UNIQUE NOT NULL,
    date_created          TEXT NOT NULL,
    date_activated        TEXT,
    assigned_customer_id  TEXT,
    nfc_url               TEXT NOT NULL,
    qr_url                TEXT NOT NULL,
    qc_status             TEXT NOT NULL DEFAULT 'pending',
    qc_tested_nfc         INTEGER NOT NULL DEFAULT 0,
    qc_tested_qr          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bands_batch   ON bands(batch_number);
CREATE INDEX IF NOT EXISTS idx_bands_partner ON bands(partner_org);
CREATE INDEX IF NOT EXISTS idx_bands_status  ON bands(status);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    details     TEXT,
    ip_address  TEXT
);
"""


def init_db():
    """Create the SQLite schema if it doesn't exist yet. For
    PostgreSQL, use migrate_to_db.py instead, which applies
    schema_postgres.sql (proper SERIAL/TIMESTAMPTZ/CHECK-constraint
    DDL rather than the SQLite dialect below)."""
    if _USING_POSTGRES:
        raise RuntimeError(
            "init_db() is SQLite-only. DATABASE_URL points at Postgres — "
            "run `python migrate_to_db.py` instead, which applies "
            "schema_postgres.sql."
        )
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQLITE)
        conn.commit()
    finally:
        conn.close()


def log_audit(actor, action, target, details="", ip_address=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            _q("""INSERT INTO audit_log (timestamp, actor, action, target, details, ip_address)
                  VALUES (?, ?, ?, ?, ?, ?)"""),
            (datetime.now(timezone.utc).isoformat(), actor, action, target, details, ip_address or ""),
        )
        conn.commit()
    finally:
        conn.close()


# ===============================
# BAND ID / VALIDATION HELPERS
# ===============================

BAND_ID_RE = re.compile(r"^EB(\d+)$")
BATCH_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{2,39}$")
PARTNER_NAME_RE = re.compile(r"^[A-Za-z0-9 &.,'\-]{2,80}$")

MAX_BULK_QUANTITY = 2000


def _existing_csv_band_ids(customers_csv_path="customers.csv"):
    """Band IDs already used by the legacy CSV-based customer system —
    checked so a bulk batch can never collide with an existing
    activated (or manually added) profile."""
    ids = set()
    try:
        with open(customers_csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bid = (row.get("band_id") or "").strip().upper()
                if bid:
                    ids.add(bid)
    except FileNotFoundError:
        pass
    return ids


def get_next_band_number(customers_csv_path="customers.csv"):
    """Scan both customers.csv (legacy/manually-added profiles) and
    the bulk `bands` table for the highest existing EB number, and
    return the next one. Mirrors the existing /next-band-id logic in
    app.py, but also accounts for bulk-provisioned bands."""
    highest = 0

    for bid in _existing_csv_band_ids(customers_csv_path):
        m = BAND_ID_RE.match(bid)
        if m:
            highest = max(highest, int(m.group(1)))

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT band_id FROM bands")
        for row in _dict_rows(cur):
            m = BAND_ID_RE.match(row["band_id"])
            if m:
                highest = max(highest, int(m.group(1)))
    finally:
        conn.close()

    return highest + 1


# ===============================
# BULK GENERATION
# ===============================

def create_bulk_batch(quantity, partner_org, batch_number, starting_number=None,
                       base_url="https://empowerbands.org", actor="unknown", ip_address=None):
    """Create `quantity` new bands, all status='unassigned', for one
    partner/batch. Validates everything up front and inserts in a
    single transaction — either the whole batch is created, or none
    of it is (no partially-created batches on a bad request)."""

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise BulkGenerationError("Quantity must be a whole number.")
    if quantity < 1 or quantity > MAX_BULK_QUANTITY:
        raise BulkGenerationError(f"Quantity must be between 1 and {MAX_BULK_QUANTITY}.")

    partner_org = (partner_org or "").strip()
    if not PARTNER_NAME_RE.match(partner_org):
        raise BulkGenerationError(
            "Partner organization name must be 2-80 characters "
            "(letters, numbers, spaces, and & . , ' - only)."
        )

    batch_number = (batch_number or "").strip().upper()
    if not BATCH_NUMBER_RE.match(batch_number):
        raise BulkGenerationError(
            "Batch number must be 3-40 characters: letters, numbers, and "
            "hyphens only (e.g. PYP-2026-001)."
        )

    if starting_number is not None and str(starting_number).strip():
        try:
            start = int(starting_number)
        except (TypeError, ValueError):
            raise BulkGenerationError("Starting Band ID number must be a whole number.")
        if start < 1:
            raise BulkGenerationError("Starting Band ID number must be positive.")
    else:
        start = get_next_band_number()

    end = start + quantity - 1
    candidate_ids = [f"EB{n:03d}" for n in range(start, end + 1)]

    # Reject up front against the legacy CSV system
    csv_collisions = [bid for bid in candidate_ids if bid in _existing_csv_band_ids()]
    if csv_collisions:
        raise BulkGenerationError(
            f"{len(csv_collisions)} of the requested Band IDs already exist in the "
            f"customer database (e.g. {csv_collisions[0]}). Leave 'Starting Band ID' "
            "blank to auto-continue from the next available ID."
        )

    created = []
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(_q("SELECT COUNT(*) FROM bands WHERE batch_number = ?"), (batch_number,))
        existing_batch_count = cur.fetchone()[0]
        if existing_batch_count > 0:
            raise BulkGenerationError(
                f"Batch number '{batch_number}' already has {existing_batch_count} bands. "
                "Use a new/unique batch number for a new order."
            )

        placeholders = ",".join(["?"] * len(candidate_ids))
        cur.execute(_q(f"SELECT band_id FROM bands WHERE band_id IN ({placeholders})"), candidate_ids)
        db_collisions = [r[0] for r in cur.fetchall()]
        if db_collisions:
            raise BulkGenerationError(
                f"{len(db_collisions)} of the requested Band IDs already exist "
                f"(e.g. {db_collisions[0]}). Leave 'Starting Band ID' blank to "
                "auto-continue from the next available ID."
            )

        now = datetime.now(timezone.utc).isoformat()
        tokens_used = set()
        rows_to_insert = []
        for band_id in candidate_ids:
            token = secrets.token_urlsafe(24)
            while token in tokens_used:
                token = secrets.token_urlsafe(24)
            tokens_used.add(token)
            nfc_url = f"{base_url.rstrip('/')}/{band_id}"
            rows_to_insert.append((band_id, partner_org, batch_number, token, now, nfc_url, nfc_url))
            created.append({
                "band_id": band_id, "partner_org": partner_org, "batch_number": batch_number,
                "status": "unassigned", "activation_token": token, "date_created": now,
                "date_activated": None, "assigned_customer_id": None,
                "nfc_url": nfc_url, "qr_url": nfc_url,
                "qc_status": "pending", "qc_tested_nfc": 0, "qc_tested_qr": 0,
            })

        cur.executemany(
            _q("""INSERT INTO bands
                  (band_id, partner_org, batch_number, status, activation_token,
                   date_created, nfc_url, qr_url, qc_status, qc_tested_nfc, qc_tested_qr)
                  VALUES (?, ?, ?, 'unassigned', ?, ?, ?, ?, 'pending', 0, 0)"""),
            rows_to_insert,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log_audit(
        actor, "bulk_generate", batch_number,
        f"Created {quantity} bands ({created[0]['band_id']}\u2013{created[-1]['band_id']}) "
        f"for partner '{partner_org}'",
        ip_address,
    )
    return created


# ===============================
# LOOKUPS
# ===============================

def get_band(band_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bands WHERE band_id = ?"), (band_id.strip().upper(),))
        rows = _dict_rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def get_band_by_token(token):
    token = (token or "").strip()
    if not token:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bands WHERE activation_token = ?"), (token,))
        rows = _dict_rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def list_bands(band_id=None, batch_number=None, partner_org=None, status=None, limit=500):
    """Inventory search — any combination of filters, all optional."""
    clauses, params = [], []
    if band_id:
        clauses.append("band_id LIKE ?")
        params.append(f"%{band_id.strip().upper()}%")
    if batch_number:
        clauses.append("batch_number LIKE ?")
        params.append(f"%{batch_number.strip().upper()}%")
    if partner_org:
        clauses.append("partner_org LIKE ?")
        params.append(f"%{partner_org.strip()}%")
    if status:
        clauses.append("status = ?")
        params.append(status.strip())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q(f"SELECT * FROM bands {where} ORDER BY id DESC LIMIT ?"), params + [limit])
        return _dict_rows(cur)
    finally:
        conn.close()


def list_batches():
    """Distinct batches with counts, for the batch report / bulk-bands landing page."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT batch_number, partner_org, COUNT(*) AS total,
                   MIN(date_created) AS date_created
            FROM bands
            GROUP BY batch_number, partner_org
            ORDER BY date_created DESC
        """)
        return _dict_rows(cur)
    finally:
        conn.close()


def partner_stats():
    """Aggregate counts per partner for the partner dashboard."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT partner_org, status, COUNT(*) AS n FROM bands GROUP BY partner_org, status")
        rows = _dict_rows(cur)
    finally:
        conn.close()

    stats = {}
    for r in rows:
        p = stats.setdefault(r["partner_org"], {
            "total": 0, "unassigned": 0, "active": 0, "lost": 0, "replaced": 0,
        })
        p["total"] += r["n"]
        if r["status"] in p:
            p[r["status"]] += r["n"]

    for p in stats.values():
        p["activation_pct"] = round((p["active"] / p["total"]) * 100, 1) if p["total"] else 0.0

    return stats


# ===============================
# STATE CHANGES
# ===============================

def activate_band(band_id, actor="customer", ip_address=None):
    """Flip a band from 'unassigned' to 'active' and record who/when.
    Only succeeds if the band is currently 'unassigned' — prevents
    re-activating an already-active band or racing two activations
    for the same band."""
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            _q("""UPDATE bands SET status = 'active', date_activated = ?,
                  assigned_customer_id = ? WHERE band_id = ? AND status = 'unassigned'"""),
            (now, band_id, band_id),
        )
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "activate_band", band_id, "Customer completed activation", ip_address)
    return bool(updated)


def update_qc(band_id, qc_status, tested_nfc, tested_qr, actor="admin", ip_address=None):
    if qc_status not in ("pending", "passed", "failed"):
        raise BulkGenerationError("Invalid QC status.")
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            _q("UPDATE bands SET qc_status = ?, qc_tested_nfc = ?, qc_tested_qr = ? WHERE band_id = ?"),
            (qc_status, int(bool(tested_nfc)), int(bool(tested_qr)), band_id),
        )
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "qc_update", band_id,
                   f"qc_status={qc_status} nfc_tested={bool(tested_nfc)} qr_tested={bool(tested_qr)}",
                   ip_address)
    return bool(updated)


def update_status(band_id, new_status, actor="admin", ip_address=None):
    if new_status not in ("unassigned", "active", "lost", "replaced"):
        raise BulkGenerationError("Invalid status.")
    band_id = band_id.strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("UPDATE bands SET status = ? WHERE band_id = ?"), (new_status, band_id))
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if updated:
        log_audit(actor, "status_update", band_id, f"status={new_status}", ip_address)
    return bool(updated)
