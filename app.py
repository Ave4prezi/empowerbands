from flask import Flask, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from twilio.rest import Client
from io import BytesIO
from email.mime.text import MIMEText
import csv
import os
import time
import smtplib
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")

# ---------------- TWILIO ----------------
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

EMAIL_USER = os.environ.get("ALERT_EMAIL")
EMAIL_PASS = os.environ.get("ALERT_EMAIL_PASSWORD")

# ---------------- FILE SETUP ----------------
header = [
    "band_id","name","email","phone",
    "emergency_phones","emergency_emails",
    "age_group","condition","instructions",
    "medical_notes","pin","address",
    "race","gender","photo_url"
]

if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)

if not os.path.exists(scan_log_file):
    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["BandID","Name","Time","Type","IP"])


# ---------------- HELPERS ----------------
def log_scan(band_id, name, scan_type, ip):
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(scan_log_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([band_id, name, now, scan_type, ip])
    except Exception as e:
        print("log_scan error:", e)


def send_full_alert(name, phones, emails, band_id, maps_link=None):
    if not client or not TWILIO_PHONE_NUMBER:
        print("Twilio not configured")
        return False

    msg = f"""🚨 EmpowerBands Alert
Name: {name}
Profile: {BASE_URL}/{band_id}
"""

    if maps_link:
        msg += f"Location: {maps_link}"

    success = False

    # SMS
    phone_list = [p.strip() for p in str(phones).split(",") if p.strip()]
    for p in phone_list:
        try:
            client.messages.create(
                body=msg,
                from_=TWILIO_PHONE_NUMBER,
                to=p
            )
            success = True
        except Exception as e:
            print("SMS error:", e)

    # EMAIL
    email_list = [e.strip() for e in str(emails).split(",") if e.strip()]

    if EMAIL_USER and EMAIL_PASS and email_list:
        try:
            mail = MIMEText(msg)
            mail["Subject"] = f"Emergency Alert: {name}"
            mail["From"] = EMAIL_USER
            mail["To"] = ", ".join(email_list)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, email_list, mail.as_string())
            server.quit()
        except Exception as e:
            print("Email error:", e)

    return success


# ---------------- HOME ----------------
@app.route("/")
def home():
    return "<h1>EmpowerBands Running</h1>"


# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        return "Wrong password"

    return """
    <form method="POST">
        <input name="password" type="password">
        <button>Login</button>
    </form>
    """


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/admin")

    return "<h1>Dashboard OK</h1>"


# ---------------- ADD PROFILE ----------------
@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        row = [
            request.form.get("band_id","").upper(),
            request.form.get("name",""),
            request.form.get("email",""),
            request.form.get("phone",""),
            request.form.get("emergency_phones",""),
            request.form.get("emergency_emails",""),
            request.form.get("age_group",""),
            request.form.get("condition",""),
            request.form.get("instructions",""),
            request.form.get("medical_notes",""),
            request.form.get("pin",""),
            request.form.get("address",""),
            request.form.get("race",""),
            request.form.get("gender",""),
            ""
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        return redirect("/dashboard")

    return "<form method='POST'>Add Profile</form>"


# ---------------- SCAN LOGS (FIXED) ----------------
@app.route("/scans")
def scans():
    if not session.get("logged_in"):
        return redirect("/admin")

    scan_list = []

    try:
        with open(scan_log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                scan_list.append({
                    "BandID": r.get("BandID",""),
                    "Name": r.get("Name",""),
                    "Time": r.get("Time",""),
                    "Type": r.get("Type",""),
                    "IP": r.get("IP","")
                })
        scan_list.reverse()

    except Exception as e:
        print("scan error:", e)

    rows = ""
    for s in scan_list:
        rows += f"<tr><td>{s['BandID']}</td><td>{s['Name']}</td><td>{s['Time']}</td><td>{s['Type']}</td><td>{s['IP']}</td></tr>"

    return f"""
    <h1>Scan Logs</h1>
    <table border="1">
        <tr><th>ID</th><th>Name</th><th>Time</th><th>Type</th><th>IP</th></tr>
        {rows if rows else "<tr><td colspan='5'>No scans</td></tr>"}
    </table>
    """


# ---------------- SAFE BAND ROUTE ----------------
@app.route("/<band_id>")
def band(band_id):
    blocked = ["admin","add","scans","dashboard","privacy","terms","alert_with_location"]

    if band_id.lower() in blocked:
        return redirect("/")

    return f"<h1>Profile {band_id}</h1>"


# ---------------- ALERT ROUTE ----------------
@app.route("/alert_with_location")
def alert():
    band_id = request.args.get("band_id","").upper()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    maps = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else None

    try:
        with open(file_name, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)

            for r in reader:
                if r[0].upper() == band_id:
                    send_full_alert(r[1], r[4], r[5], band_id, maps)
                    return "Alert sent"
    except Exception as e:
        return f"Error: {e}"

    return "Not found", 404


# ---------------- SMS TEST ----------------
@app.route("/test_sms")
def test_sms():
    try:
        if not client:
            return "Twilio not configured"

        msg = client.messages.create(
            body="Test SMS",
            from_=TWILIO_PHONE_NUMBER,
            to="+10000000000"
        )
        return msg.sid
    except Exception as e:
        return str(e)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
