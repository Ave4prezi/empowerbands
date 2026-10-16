"""Isolated Key Finder schema and public lookup. No Safety ID table access.

Activation is intentionally not exposed until card ownership verification and
customer authentication are finalized.
"""
import os
import secrets
import hashlib
import hmac
import urllib.error
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
import re
from flask import render_template_string
import psycopg
from flask import Blueprint, jsonify, request, session, redirect, render_template_string

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
            cur.execute("""CREATE TABLE IF NOT EXISTS key_finder_email_challenges (
                email TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
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

# Customer session is isolated from Safety ID data and never uses serial as a login credential.
EMAIL_RE = re.compile(r"^[^\\s@]{1,64}@[^\\s@]{1,190}\\.[^\\s@]{2,}$")


def _csrf_ok():
    origin = request.headers.get("Origin", "")
    return bool(origin) and origin.rstrip("/") == request.host_url.rstrip("/") and request.form.get("csrf") == session.get("kf_csrf")


def _csrf():
    if "kf_csrf" not in session:
        session["kf_csrf"] = secrets.token_urlsafe(32)
    return session["kf_csrf"]


def _email_code(email, code):
    """Send one-time sign-in codes via Resend's HTTPS API."""
    import json
    import urllib.request
    key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("KEY_FINDER_EMAIL_FROM", "EmpowerBands <support@empowerbands.org>")
    if not key:
        raise RuntimeError("Resend API key is not configured")
    payload = json.dumps({
        "from": sender,
        "to": [email],
        "subject": "EmpowerBands Key Finder sign-in code",
        "text": "Your one-time code is " + code + ". It expires in 10 minutes. Do not share it."
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status not in (200, 201):
            raise RuntimeError("Resend rejected the email")


def _code_digest(email, code):
    pepper = os.environ.get("KEY_FINDER_ACTIVATION_PEPPER", "")
    if len(pepper) < 32:
        raise RuntimeError("Key Finder security configuration missing")
    return hmac.new(pepper.encode(), (email + ":" + code).encode(), hashlib.sha256).hexdigest()


@key_finder_api.get("/key-finder/account")
def key_finder_account():
    email = session.get("kf_email")
    devices = []
    if email and os.environ.get("DATABASE_URL"):
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT serial, item_label, lost, contact_visible, public_contact_email
                    FROM key_finder_devices WHERE owner_email = %s AND activated_at IS NOT NULL
                    ORDER BY activated_at DESC""", (email,))
                devices = cur.fetchall()
    return render_template_string("""
        <!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Key Finder account | EmpowerBands</title>
        <main style="font:1rem system-ui;max-width:38rem;margin:2rem auto;padding:1rem">
        <h1>EmpowerBands Key Finder</h1><p><a href="/key-finder">Back to Key Finder</a></p>
        {% if not email %}
          <form method="post" action="/key-finder/send-code"><input type="hidden" name="csrf" value="{{ csrf }}">
          <label>Email <input type="email" name="email" required maxlength="254"></label>
          <button>Send sign-in code</button></form>
          <form method="post" action="/key-finder/verify-code"><input type="hidden" name="csrf" value="{{ csrf }}">
          <label>Email <input type="email" name="email" required maxlength="254"></label>
          <label>Six-digit code <input name="code" pattern="[0-9]{6}" required></label>
          <button>Verify and sign in</button></form>
        {% else %}
          <p>Signed in as {{ email }}</p>
          <form method="post" action="/key-finder/logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button>Sign out</button></form>
          <h2>Activate a Key Finder</h2>
          <form method="post" action="/key-finder/claim"><input type="hidden" name="csrf" value="{{ csrf }}">
          <label>Activation card serial <input name="serial" required maxlength="27"></label><button>Activate</button></form>
          <h2>My Key Finders</h2>
          {% for d in devices %}
            <section style="border:1px solid #ccc;padding:1rem;margin:1rem 0">
              <strong>{{ d[1] or "Key Finder" }}</strong> — {{ d[0] }}
              <form method="post" action="/key-finder/update"><input type="hidden" name="csrf" value="{{ csrf }}">
              <input type="hidden" name="serial" value="{{ d[0] }}">
              <label>Item label <input name="label" maxlength="80" value="{{ d[1] or '' }}"></label>
              <label>Recovery email <input type="email" name="contact_email" maxlength="254" value="{{ d[4] or '' }}"></label>
              <label><input type="checkbox" name="visible" {% if d[3] %}checked{% endif %}> Publicly display recovery email</label>
              <label><input type="checkbox" name="lost" {% if d[2] %}checked{% endif %}> Report lost</label>
              <button>Save changes</button></form>
            </section>
          {% else %}<p>No activated Key Finders yet.</p>{% endfor %}
        {% endif %}
        </main></html>
    """, email=email, devices=devices, csrf=_csrf())


@key_finder_api.post("/key-finder/send-code")
def key_finder_send_code():
    if not _csrf_ok():
        return "Invalid request", 403
    email = request.form.get("email", "").strip().lower()
    if not EMAIL_RE.fullmatch(email) or not os.environ.get("DATABASE_URL"):
        return "Unable to send code", 400
    code = f"{secrets.randbelow(1000000):06d}"
    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO key_finder_email_challenges(email, code_hash, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '10 minutes')
                    ON CONFLICT (email) DO UPDATE SET
                    code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at,
                    attempts = 0, last_sent_at = NOW()
                    WHERE key_finder_email_challenges.last_sent_at < NOW() - INTERVAL '60 seconds'
                    RETURNING email""", (email, _code_digest(email, code)))
                if not cur.fetchone():
                    return "Please wait before requesting another code", 429
            conn.commit()
        _email_code(email, code)
    except (psycopg.Error, RuntimeError, OSError, urllib.error.URLError):
        return "Unable to send code right now", 503
    return "Check your email for the six-digit code, then return to the account page."


@key_finder_api.post("/key-finder/verify-code")
def key_finder_verify_code():
    if not _csrf_ok():
        return "Invalid request", 403
    email = request.form.get("email", "").strip().lower()
    code = request.form.get("code", "")
    if not EMAIL_RE.fullmatch(email) or not re.fullmatch(r"[0-9]{6}", code):
        return "Invalid code", 400
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE key_finder_email_challenges SET attempts = attempts + 1
                WHERE email=%s AND attempts < 5 AND expires_at > NOW()
                RETURNING code_hash""", (email,))
            record = cur.fetchone()
            if record and hmac.compare_digest(record[0], _code_digest(email, code)):
                cur.execute("DELETE FROM key_finder_email_challenges WHERE email=%s", (email,))
                conn.commit()
                session.clear()
                session["kf_email"] = email
                session["kf_csrf"] = secrets.token_urlsafe(32)
                return redirect("/key-finder/account", code=303)
        conn.commit()
    return "Invalid or expired code", 400


@key_finder_api.post("/key-finder/logout")
def key_finder_logout():
    if not _csrf_ok():
        return "Invalid request", 403
    session.clear()
    return redirect("/key-finder/account", code=303)


@key_finder_api.post("/key-finder/claim")
def key_finder_claim():
    if not _csrf_ok() or not session.get("kf_email"):
        return "Sign in required", 403
    serial = request.form.get("serial", "").strip().upper()
    if not SERIAL_RE.fullmatch(serial):
        return "Invalid serial", 400
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE key_finder_devices SET owner_email=%s, activated_at=NOW()
                WHERE serial=%s AND activated_at IS NULL RETURNING serial""",
                (session["kf_email"], serial))
            found = cur.fetchone()
        conn.commit()
    if not found:
        return "Serial unavailable or already activated", 409
    return redirect("/key-finder/account", code=303)


@key_finder_api.post("/key-finder/update")
def key_finder_update():
    if not _csrf_ok() or not session.get("kf_email"):
        return "Sign in required", 403
    serial = request.form.get("serial", "").strip().upper()
    label = request.form.get("label", "").strip()[:80]
    contact = request.form.get("contact_email", "").strip().lower()
    visible = request.form.get("visible") == "on"
    lost = request.form.get("lost") == "on"
    if not SERIAL_RE.fullmatch(serial) or (contact and not EMAIL_RE.fullmatch(contact)) or (visible and not contact):
        return "Invalid details", 400
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE key_finder_devices SET item_label=%s,
                public_contact_email=%s, contact_visible=%s, lost=%s
                WHERE serial=%s AND owner_email=%s AND activated_at IS NOT NULL
                RETURNING serial""",
                (label, contact or None, visible, lost, serial, session["kf_email"]))
            updated = cur.fetchone()
        conn.commit()
    if not updated:
        return "Key Finder not found", 404
    return redirect("/key-finder/account", code=303)
