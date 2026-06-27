from flask import Flask, request, redirect, session, Response
from twilio.rest import Client
import os
import time
import sqlite3
import smtplib
from email.mime.text import MIMEText
import qrcode
from io import BytesIO

# ---------------- APP SETUP ----------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

ALERT_EMAIL = os.environ.get("ALERT_EMAILS", "")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD", "")

DB_FILE = "empowerbands.db"

# ---------------- DATABASE INIT ----------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            band_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT,
            emergency_phones TEXT,
            emergency_emails TEXT,
            age_group TEXT,
            condition TEXT,
            instructions TEXT,
            medical_notes TEXT,
            pin TEXT,
            address TEXT,
            race TEXT,
            gender TEXT,
            photo_url TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id TEXT,
            name TEXT,
            time TEXT,
            scan_type TEXT,
            ip TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------

def log_scan(band_id, name, scan_type, ip):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO scans (band_id, name, time, scan_type, ip)
        VALUES (?, ?, ?, ?, ?)
    """, (band_id, name, time.strftime("%Y-%m-%d %H:%M:%S"), scan_type, ip))

    conn.commit()
    conn.close()


def send_alert(name, phones, emails, band_id):
    message = f"EmpowerBands Alert\n{name}\n{BASE_URL}/band/{band_id}"

    success = False

    # SMS (Twilio)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            for p in (phones or "").split(","):
                p = p.strip()
                if p:
                    client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=p
                    )
            success = True
        except:
            pass

    # Email
    if ALERT_EMAIL and ALERT_EMAIL_PASSWORD:
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Alert: {name}"
            msg["From"] = ALERT_EMAIL
            msg["To"] = ",".join(emails.split(",")) if emails else ""

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(ALERT_EMAIL, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAIL, emails.split(","), msg.as_string())
            server.quit()

            success = True
        except:
            pass

    return success

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return "<h1>EmpowerBands Online</h1><a href='/admin'>Admin</a>"


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        return "Wrong password"

    return """
    <form method="POST">
        <input name="password" type="password" placeholder="Admin Password">
        <button>Login</button>
    </form>
    """


@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT band_id, name FROM customers")
    rows = c.fetchall()
    conn.close()

    html = "<h1>Dashboard</h1><a href='/add'>Add</a><hr>"

    for r in rows:
        html += f"""
        <div>
            <b>{r[0]}</b> - {r[1]}
            <a href="/band/{r[0]}">View</a>
        </div><hr>
        """

    return html


@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute("""
            INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form["band_id"].upper(),
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form.get("emergency_phones", ""),
            request.form.get("emergency_emails", ""),
            request.form.get("age_group", ""),
            request.form.get("condition", ""),
            request.form.get("instructions", ""),
            request.form.get("medical_notes", ""),
            request.form.get("pin", "1234"),
            request.form.get("address", ""),
            request.form.get("race", ""),
            request.form.get("gender", ""),
            ""
        ))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return """
    <form method="POST">
        <input name="band_id" placeholder="Band ID">
        <input name="name" placeholder="Name">
        <input name="phone" placeholder="Phone">
        <input name="email" placeholder="Email">
        <button>Save</button>
    </form>
    """


@app.route("/band/<band_id>")
def band(band_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT * FROM customers WHERE band_id=?", (band_id.upper(),))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Not found"

    return f"""
    <h1>{row[1]}</h1>
    <p>{row[7]}</p>
    <a href='/'>Home</a>
    """


@app.route("/qr/<band_id>")
def qr(band_id):
    img = qrcode.make(f"{BASE_URL}/band/{band_id}")
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/scans")
def scans():
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM scans ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    return f"<pre>{rows}</pre>"


@app.route("/privacy")
def privacy():
    return "<h1>Privacy Policy</h1>"


@app.route("/terms")
def terms():
    return "<h1>Terms</h1>"


@app.route("/sms-opt-in")
def sms():
    return "<h1>SMS Opt-In Page</h1>"            band_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT,
            emergency_phones TEXT,
            emergency_emails TEXT,
            age_group TEXT,
            condition TEXT,
            instructions TEXT,
            medical_notes TEXT,
            pin TEXT,
            address TEXT,
            race TEXT,
            gender TEXT,
            photo_url TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_id TEXT,
            name TEXT,
            time TEXT,
            scan_type TEXT,
            ip TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------

def log_scan(band_id, name, scan_type, ip):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO scans (band_id, name, time, scan_type, ip)
        VALUES (?, ?, ?, ?, ?)
    """, (band_id, name, time.strftime("%Y-%m-%d %H:%M:%S"), scan_type, ip))

    conn.commit()
    conn.close()


def send_alert(name, phones, emails, band_id):
    message = f"EmpowerBands Alert\n{name}\n{BASE_URL}/band/{band_id}"

    success = False

    # SMS (Twilio)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            for p in (phones or "").split(","):
                p = p.strip()
                if p:
                    client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=p
                    )
            success = True
        except:
            pass

    # Email
    if ALERT_EMAIL and ALERT_EMAIL_PASSWORD:
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Alert: {name}"
            msg["From"] = ALERT_EMAIL
            msg["To"] = ",".join(emails.split(",")) if emails else ""

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(ALERT_EMAIL, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAIL, emails.split(","), msg.as_string())
            server.quit()

            success = True
        except:
            pass

    return success

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return "<h1>EmpowerBands Online</h1><a href='/admin'>Admin</a>"


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        return "Wrong password"

    return """
    <form method="POST">
        <input name="password" type="password" placeholder="Admin Password">
        <button>Login</button>
    </form>
    """


@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT band_id, name FROM customers")
    rows = c.fetchall()
    conn.close()

    html = "<h1>Dashboard</h1><a href='/add'>Add</a><hr>"

    for r in rows:
        html += f"""
        <div>
            <b>{r[0]}</b> - {r[1]}
            <a href="/band/{r[0]}">View</a>
        </div><hr>
        """

    return html


@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute("""
            INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form["band_id"].upper(),
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form.get("emergency_phones", ""),
            request.form.get("emergency_emails", ""),
            request.form.get("age_group", ""),
            request.form.get("condition", ""),
            request.form.get("instructions", ""),
            request.form.get("medical_notes", ""),
            request.form.get("pin", "1234"),
            request.form.get("address", ""),
            request.form.get("race", ""),
            request.form.get("gender", ""),
            ""
        ))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return """
    <form method="POST">
        <input name="band_id" placeholder="Band ID">
        <input name="name" placeholder="Name">
        <input name="phone" placeholder="Phone">
        <input name="email" placeholder="Email">
        <button>Save</button>
    </form>
    """


@app.route("/band/<band_id>")
def band(band_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT * FROM customers WHERE band_id=?", (band_id.upper(),))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Not found"

    return f"""
    <h1>{row[1]}</h1>
    <p>{row[7]}</p>
    <a href='/'>Home</a>
    """


@app.route("/qr/<band_id>")
def qr(band_id):
    img = qrcode.make(f"{BASE_URL}/band/{band_id}")
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/scans")
def scans():
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM scans ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    return f"<pre>{rows}</pre>"


@app.route("/privacy")
def privacy():
    return "<h1>Privacy Policy</h1>"


@app.route("/terms")
def terms():
    return "<h1>Terms</h1>"


@app.route("/sms-opt-in")
def sms():
    return "<h1>SMS Opt-In Page</h1>"
