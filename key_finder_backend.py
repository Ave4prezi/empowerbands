"""Isolated Key Finder schema and public lookup. No Safety ID table access.

Activation is intentionally not exposed until card ownership verification and
customer authentication are finalized.
"""
import os
import re
from flask import render_template_string
import psycopg
from flask import Blueprint, jsonify, request

key_finder_api = Blueprint("key_finder_api", __name__)
SERIAL_RE = re.compile(r"^KF-[A-Z0-9]{8,24}$")


def initialize_key_finders():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS key_finder_devices (
                    serial TEXT PRIMARY KEY,
                    recovery_identifier TEXT UNIQUE,
                    activation_secret_hash TEXT NOT NULL,
                    owner_email TEXT,
                    owner_pin_hash TEXT,
                    item_label TEXT,
                    public_contact_email TEXT,
                    contact_visible BOOLEAN NOT NULL DEFAULT FALSE,
                    lost BOOLEAN NOT NULL DEFAULT FALSE,
                    activated_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT key_finder_serial_format CHECK (serial ~ '^KF-[A-Z0-9]{8,24}$'),
                    CONSTRAINT key_finder_contact_opt_in CHECK (
                        NOT contact_visible OR public_contact_email IS NOT NULL
                    )
                )
            """)
            cur.execute("ALTER TABLE key_finder_devices ADD COLUMN IF NOT EXISTS recovery_identifier TEXT")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS key_finder_recovery_identifier_idx ON key_finder_devices(recovery_identifier)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS key_finder_events (
                    id BIGSERIAL PRIMARY KEY,
                    serial TEXT NOT NULL REFERENCES key_finder_devices(serial),
                    event_type TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()


@key_finder_api.get("/api/key-finder/public/<serial>")
def public_key_finder(serial):
    """Only disclose owner-approved contact information for activated devices."""
    serial = serial.strip().upper()
    if not SERIAL_RE.fullmatch(serial):
        return jsonify(error="Invalid Key Finder serial."), 400
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return jsonify(error="Service unavailable."), 503
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT activated_at IS NOT NULL, lost, contact_visible,
                           public_contact_email
                    FROM key_finder_devices WHERE serial = %s
                """, (serial,))
                row = cur.fetchone()
    except psycopg.Error:
        return jsonify(error="Service unavailable."), 503
    if not row or not row[0]:
        return jsonify(error="Key Finder not found."), 404
    return jsonify(
        product_type="key_finder",
        lost=bool(row[1]),
        contact_email=row[3] if row[2] else None,
        message="Contact the owner only using the information they chose to share."
    )


RECOVERY_RE = re.compile(r"^[A-Z0-9]{20}$")


@key_finder_api.get("/k/<identifier>")
def public_recovery_page(identifier):
    """Public tag URL; never includes activation-card serial or private Safety ID."""
    identifier = identifier.strip().upper()
    if not RECOVERY_RE.fullmatch(identifier):
        return "Recovery link not found", 404
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return "Recovery service temporarily unavailable", 503
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT activated_at IS NOT NULL, lost, contact_visible,
                           public_contact_email
                    FROM key_finder_devices WHERE recovery_identifier = %s
                """, (identifier,))
                record = cur.fetchone()
    except psycopg.Error:
        return "Recovery service temporarily unavailable", 503
    if record is None:
        return "Recovery link not found", 404
    active, lost, visible, email = record
    return render_template_string("""
        <!doctype html><html lang="en"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>EmpowerBands Key Finder Recovery</title>
        <main style="max-width:38rem;margin:5rem auto;padding:1.5rem;font:1.1rem system-ui">
        <h1>EmpowerBands Key Finder</h1>
        {% if not active %}
          <p>This Key Finder has not been activated yet.</p>
        {% elif lost %}
          <p>This item has been reported lost.</p>
        {% else %}
          <p>You've scanned an EmpowerBands Key Finder.</p>
        {% endif %}
        {% if active and visible and email %}
          <p>Owner-approved recovery email: <a href="mailto:{{ email|e }}">{{ email|e }}</a></p>
        {% else %}
          <p>No owner contact details are publicly available.</p>
        {% endif %}
        <p><a href="/key-finder">About EmpowerBands Key Finder</a></p>
        </main></html>
    """, active=active, lost=lost, visible=visible, email=email)
