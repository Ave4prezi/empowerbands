"""Isolated Key Finder schema and public lookup. No Safety ID table access.

Activation is intentionally not exposed until card ownership verification and
customer authentication are finalized.
"""
import os
import secrets
import hashlib
import hmac
import urllib.error
import time
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
            cur.execute("ALTER TABLE key_finder_devices ADD COLUMN IF NOT EXISTS failed_claims INTEGER NOT NULL DEFAULT 0")
            cur.execute("ALTER TABLE key_finder_devices ADD COLUMN IF NOT EXISTS claim_locked_until TIMESTAMPTZ")
            cur.execute("""CREATE TABLE IF NOT EXISTS key_finder_claim_limits (
                actor_hash TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL DEFAULT 0,
                window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                locked_until TIMESTAMPTZ
            )""")
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
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#081324">
<title>My Key Finders | EmpowerBands</title>
<style>
:root{color-scheme:dark;--bg:#07111f;--panel:#111f31;--border:#2b3b51;--text:#f3f7fd;--muted:#acbdd2;--accent:#56d7d1}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0%,#173957 0%,transparent 43%),var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--accent)}.shell{width:min(1100px,calc(100% - 36px));margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:24px 0;border-bottom:1px solid var(--border)}
.brand{font-weight:850;letter-spacing:.035em;color:white;text-decoration:none;font-size:1.12rem}.brand span{color:var(--accent)}.back{text-decoration:none;font-size:.9rem;color:var(--muted)}
.hero{padding:56px 0 32px;max-width:740px}.eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:.76rem;font-weight:800;color:var(--accent)}
h1{font-size:clamp(2.25rem,5vw,4rem);line-height:1.08;letter-spacing:-.045em;margin:12px 0 18px}h2{font-size:1.35rem;letter-spacing:-.025em;margin:0 0 8px}p{color:var(--muted);margin:0 0 22px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin:18px 0 56px}.panel,.device{background:linear-gradient(145deg,rgba(24,43,65,.95),rgba(12,26,43,.96));border:1px solid var(--border);border-radius:20px;padding:26px;box-shadow:0 16px 40px #0002}
.panel-head{display:flex;align-items:center;gap:12px;margin-bottom:18px}.step{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:#173e4a;color:#8bf3e5;font-weight:800}
label{display:block;color:#d5e1ef;font-weight:650;font-size:.9rem;margin:16px 0 6px}input:not([type=checkbox]){width:100%;background:#081827;color:white;border:1px solid #42566c;border-radius:11px;padding:13px 14px;font:inherit;outline:none}
input:focus{border-color:var(--accent);box-shadow:0 0 0 3px #56d7d126}input::placeholder{color:#7d90a7}
button{width:100%;background:var(--accent);color:#05232b;border:0;border-radius:11px;padding:13px 18px;font:inherit;font-weight:800;cursor:pointer;margin-top:20px}button:hover{background:#8cf0e7}button.secondary{width:auto;margin:0;background:transparent;color:#e3eef9;border:1px solid #546780;padding:9px 16px}
small,.hint{color:var(--muted);font-size:.85rem}.signed{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;padding:18px 22px;border:1px solid #2d625f;background:#10312f;border-radius:14px;margin:8px 0 26px}.signed strong{color:white}
.section-heading{margin:32px 0 18px}.device-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:64px}.device{padding:24px}.device-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.serial{font-size:.78rem;color:var(--muted);word-break:break-all}.pill{white-space:nowrap;border:1px solid #426b70;background:#153b43;border-radius:99px;padding:5px 10px;font-size:.73rem;font-weight:800;color:#a1efe7}.pill.lost{border-color:#936f43;background:#483321;color:#ffce91}
.check{display:flex;align-items:flex-start;gap:11px;font-size:.89rem;font-weight:500;margin:18px 0;color:#dbe6f4}.check input{accent-color:var(--accent);margin-top:5px;width:17px;height:17px;flex:none}
.empty{border:1px dashed #4a6077;border-radius:18px;text-align:center;padding:40px 22px;margin-bottom:60px}.empty strong{display:block;margin-bottom:8px}.empty p{margin:0}.footer{border-top:1px solid var(--border);padding:22px 0 35px;color:var(--muted);font-size:.8rem}
@media(max-width:700px){.grid,.device-grid{grid-template-columns:1fr}.hero{padding-top:38px}.panel,.device{padding:20px}.top{padding:18px 0}}
</style>
</head>
<body><div class="shell">
<header class="top"><a class="brand" href="/key-finder">EMPOWER<span>BANDS</span></a><a class="back" href="/key-finder">← Back to Key Finder</a></header>
<section class="hero"><div class="eyebrow">EmpowerBands • Smart recovery</div>
<h1>{% if email %}Your essentials. One place.{% else %}Keep what matters close.{% endif %}</h1>
<p>{% if email %}Activate, personalize and manage your Key Finders from your secure dashboard.{% else %}Sign in securely with a one-time email code to activate and manage your Key Finders. No password needed.{% endif %}</p></section>
{% if not email %}
<div class="grid">
<section class="panel"><div class="panel-head"><span class="step">01</span><h2>Get your sign-in code</h2></div>
<p>We'll email a six-digit code to verify it's you.</p>
<form method="post" action="/key-finder/send-code"><input type="hidden" name="csrf" value="{{ csrf }}">
<label for="send-email">Email address</label><input id="send-email" type="email" name="email" autocomplete="email" placeholder="you@example.com" required maxlength="254">
<button type="submit">Send verification code →</button></form>
</section>
<section class="panel"><div class="panel-head"><span class="step">02</span><h2>Verify and continue</h2></div>
<p>Enter the code from your inbox. It expires after 10 minutes.</p>
<form method="post" action="/key-finder/verify-code"><input type="hidden" name="csrf" value="{{ csrf }}">
<label for="verify-email">Email address</label><input id="verify-email" type="email" name="email" autocomplete="email" placeholder="Same email as above" required maxlength="254">
<label for="verify-code">Six-digit code</label><input id="verify-code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" placeholder="000000" required>
<button type="submit">Verify & sign in →</button></form>
</section></div>
{% else %}
<div class="signed"><div><small>Securely signed in as</small><div><strong>{{ email }}</strong></div></div>
<form method="post" action="/key-finder/logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="secondary" type="submit">Sign out</button></form></div>
<div class="grid" style="grid-template-columns:minmax(0,1fr)">
<section class="panel"><div class="panel-head"><span class="step">+</span><h2>Activate a new Key Finder</h2></div>
<p>Use the serial number and hidden activation code printed on your activation card.</p>
<form method="post" action="/key-finder/claim"><input type="hidden" name="csrf" value="{{ csrf }}">
<label for="serial">Activation card serial</label><input id="serial" name="serial" required maxlength="27" autocomplete="off" placeholder="KF-XXXXXXXX">
<label for="activation">Hidden activation code</label><input id="activation" name="activation_code" required maxlength="64" autocomplete="off" placeholder="Enter your 24-character code">
<button type="submit">Activate Key Finder →</button></form></section></div>
<div class="section-heading"><div class="eyebrow">Your collection</div><h2>My Key Finders</h2></div>
{% if devices %}<div class="device-grid">{% for d in devices %}
<section class="device"><div class="device-top"><div><h2>{{ d[1] or "My Key Finder" }}</h2><div class="serial">{{ d[0] }}</div></div><span class="pill {% if d[2] %}lost{% endif %}">{% if d[2] %}Reported lost{% else %}Active{% endif %}</span></div>
<form method="post" action="/key-finder/update"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="serial" value="{{ d[0] }}">
<label>Item name</label><input name="label" maxlength="80" value="{{ d[1] or '' }}" placeholder="e.g. House keys">
<label>Recovery contact email</label><input type="email" name="contact_email" maxlength="254" value="{{ d[4] or '' }}" placeholder="Contact email">
<label class="check"><input type="checkbox" name="visible" {% if d[3] %}checked{% endif %}><span>Show my recovery email on the public finder page</span></label>
<label class="check"><input type="checkbox" name="lost" {% if d[2] %}checked{% endif %}><span>Mark this item as lost</span></label>
<button type="submit">Save changes</button></form></section>
{% endfor %}</div>{% else %}
<div class="empty"><strong>No Key Finders activated yet</strong><p>Activate your first device above to see it here.</p></div>
{% endif %}
{% endif %}
<footer class="footer">EmpowerBands · Protect What Matters Most</footer>
</div></body></html>
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


def _claim_digest(value):
    pepper = os.environ.get("KEY_FINDER_ACTIVATION_PEPPER", "")
    if len(pepper) < 32:
        raise RuntimeError("Key Finder activation security is not configured")
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


@key_finder_api.post("/key-finder/claim")
def key_finder_claim():
    """Verified-email owner + printed serial + separate one-time hidden code."""
    if not _csrf_ok() or not session.get("kf_email"):
        return "Sign in required", 403
    serial = request.form.get("serial", "").strip().upper()
    code = request.form.get("activation_code", "").strip().upper()
    # Reject malformed input without revealing inventory membership.
    if not SERIAL_RE.fullmatch(serial) or not re.fullmatch(r"[A-Z0-9]{24}", code):
        return "Invalid activation details", 400
    email = session["kf_email"]
    # Hash the IP to avoid retaining raw IP addresses in the rate-limit table.
    actor = _claim_digest("ip:" + (request.remote_addr or "unknown"))
    account = _claim_digest("account:" + email)
    serial_key = _claim_digest("serial:" + serial)
    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                # Lock rate-limit rows in stable order to serialize concurrent attempts.
                for key in sorted([actor, account, serial_key]):
                    cur.execute("""INSERT INTO key_finder_claim_limits(actor_hash)
                        VALUES (%s) ON CONFLICT DO NOTHING""", (key,))
                    cur.execute("""SELECT attempts, window_start, locked_until
                        FROM key_finder_claim_limits WHERE actor_hash=%s FOR UPDATE""", (key,))
                    attempts, window_start, locked_until = cur.fetchone()
                    now = datetime.now(timezone.utc)
                    if locked_until and locked_until > now:
                        return "Too many attempts. Try again later.", 429
                    if window_start < now - timedelta(hours=1):
                        attempts = 0
                        cur.execute("""UPDATE key_finder_claim_limits SET attempts=0,
                            window_start=NOW(), locked_until=NULL WHERE actor_hash=%s""", (key,))
                    attempts += 1
                    cur.execute("""UPDATE key_finder_claim_limits SET attempts=%s,
                        locked_until=CASE WHEN %s >= 5 THEN NOW() + INTERVAL '1 hour'
                        ELSE NULL END WHERE actor_hash=%s""", (attempts, attempts, key))
                cur.execute("""SELECT activation_secret_hash, activated_at, claim_locked_until
                    FROM key_finder_devices WHERE serial=%s FOR UPDATE""", (serial,))
                device = cur.fetchone()
                expected = _claim_digest("activation:" + serial + ":" + code)
                valid = bool(device and device[1] is None and
                    (device[2] is None or device[2] <= datetime.now(timezone.utc)) and
                    hmac.compare_digest(device[0], expected))
                if not valid:
                    conn.commit()  # persist failed-attempt counters
                    return "Invalid or already used activation details", 400
                cur.execute("""UPDATE key_finder_devices
                    SET owner_email=%s, activated_at=NOW(), activation_secret_hash=%s
                    WHERE serial=%s AND activated_at IS NULL RETURNING serial""",
                    (email, _claim_digest("used:" + serial + ":" + secrets.token_hex(16)), serial))
                if not cur.fetchone():
                    conn.commit()
                    return "Invalid or already used activation details", 400
            conn.commit()
    except (psycopg.Error, RuntimeError, KeyError):
        return "Activation service unavailable", 503
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
