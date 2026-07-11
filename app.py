from flask import Flask, request, redirect, session, send_file, jsonify
import hmac
import hashlib
from twilio.rest import Client
import csv
import os
import time
import smtplib
from email.mime.text import MIMEText
import qrcode
from io import BytesIO
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

ALERT_EMAILS = os.environ.get("ALERT_EMAILS", "")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

LOGO_URL = "https://i.imgur.com/bSUxUXa.jpeg"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===============================
# RATE LIMITING FOR SAFE ALERTS
# ===============================
safe_notification_cooldown = {}
SAFE_COOLDOWN_SECONDS = 300  # 5 minutes

def can_send_safe_notification(band_id):
    """Check if enough time has passed since last safe notification"""
    now = datetime.now()
    last_time = safe_notification_cooldown.get(band_id)
    
    if last_time and (now - last_time) < timedelta(seconds=SAFE_COOLDOWN_SECONDS):
        return False
    
    safe_notification_cooldown[band_id] = now
    return True

# ===============================
# CREATE FILES
# ===============================

header = [
    "band_id",
    "name",
    "email",
    "phone",
    "emergency_phones",
    "emergency_emails",
    "age_group",
    "condition",
    "instructions",
    "medical_notes",
    "pin",
    "address",
    "race",
    "gender",
    "photo_url"
]

# Create customers.csv only if missing
if not os.path.exists(file_name):

    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(header)

        # Optional demo profile
        writer.writerow([
    "EB001",
    "Jaden",
    "email@test.com",
    "+12565551234",
    "+19382655364,+12566121274",
    "mom@test.com,dad@test.com",
    "Child",
    "Autism – Nonverbal",
    "Please stay calm. I may not respond verbally. Call emergency contacts immediately.",
    "No allergies",
    "1234",
    "123 Hope Street, Decatur AL 35601",
    "Black / African American",
    "Male",
    "https://i.imgur.com/7A4KvOJ.jpeg"
])

# Create family spotlight file if missing
_spotlight_file = "family_spotlight.json"
if not os.path.exists(_spotlight_file):
    with open(_spotlight_file, "w") as _sf:
        import json as _spotlight_init_json
        _spotlight_init_json.dump({"active": False, "month": "", "story": "", "photo_url": ""}, _sf)

# Create volunteer sign-ups file if missing
_vol_file = "bb_volunteers.csv"
if not os.path.exists(_vol_file):
    with open(_vol_file, "w", newline="", encoding="utf-8") as _vf:
        import csv as _csv_init
        _csv_init.writer(_vf).writerow(["Name","Email","Phone","Availability","Message","Submitted"])

# Create blessing box needs file if missing
_bb_needs_file = "blessing_box_needs.json"
if not os.path.exists(_bb_needs_file):
    import json as _bb_json_init
    _bb_defaults = [
        {"emoji": "🥫", "label": "Canned Food"},
        {"emoji": "🍞", "label": "Shelf-Stable Snacks"},
        {"emoji": "🧴", "label": "Shampoo & Conditioner"},
        {"emoji": "🪥", "label": "Toothbrush & Toothpaste"},
        {"emoji": "🧼", "label": "Soap & Body Wash"},
        {"emoji": "🧻", "label": "Toilet Paper"},
        {"emoji": "👕", "label": "Socks & Underwear"},
        {"emoji": "🩹", "label": "First Aid Supplies"},
        {"emoji": "🌡️", "label": "Cold Medicine"},
        {"emoji": "👶", "label": "Baby Supplies"},
        {"emoji": "🐾", "label": "Pet Food"},
        {"emoji": "📦", "label": "Other Essentials"}
    ]
    with open(_bb_needs_file, "w") as _f:
        _bb_json_init.dump(_bb_defaults, _f)

# Create scan log only if missing
if not os.path.exists(scan_log_file):

    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "BandID",
            "Name",
            "Time",
            "Type",
            "IP"
        ])

# ===============================
# FUNCTIONS
# ===============================

def log_scan(band_id, name, scan_type, ip):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(scan_log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([band_id, name, now, scan_type, ip])


def send_safe_notification(name, phones, emails, band_id):
    message = (
        f"EmpowerBands Update\n\n"
        f"{name} has marked their emergency alert as SAFE / RESOLVED.\n"
        f"This may have been triggered by accident, or the situation has been handled.\n"
        f"No further action is needed at this time."
    )

    success_sms = False
    success_email = False

    phone_list = [p.strip() for p in str(phones).split(",") if p.strip()]
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        for phone in phone_list:
            try:
                client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=phone)
                success_sms = True
            except Exception as e:
                print("Safe SMS failed:", e)

    email_list = [e.strip() for e in str(emails).split(",") if e.strip()]
    if ALERT_EMAIL_PASSWORD and email_list:
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Safe / Resolved Update: {name}"
            msg["From"] = ALERT_EMAILS
            msg["To"] = ", ".join(email_list)
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(ALERT_EMAILS, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAILS, email_list, msg.as_string())
            server.quit()
            success_email = True
        except Exception as e:
            print("Safe email failed:", e)

    log_scan(band_id, name, "SAFE_ALERT", request.remote_addr if request else "unknown")
    return success_sms or success_email


def send_full_alert(name, phones, emails, band_id, maps_link=None):
    profile_url = f"{BASE_URL}/{band_id}"
    location_text = f"\nLocation:\n{maps_link}" if maps_link else ""
    
    message = (
        f"EmpowerBands Emergency Alert\n\n"
        f"{name}'s emergency profile was accessed.\n\n"
        f"Profile:\n{profile_url}"
        f"{location_text}\n\n"
        f"This person may need assistance"
    )

    success_sms = False
    success_email = False

    # =========================
    # SMS (Twilio)
    # =========================
    phone_list = [p.strip() for p in str(phones).split(",") if p.strip()]

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        for phone in phone_list:
            try:
                client.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=phone
                )
                print("SMS sent:", phone)
                success_sms = True
            except Exception as e:
                print("SMS failed:", e)

    # =========================
    # EMAIL (SMTP)
    # =========================
    email_list = [e.strip() for e in str(emails).split(",") if e.strip()]

    if ALERT_EMAIL_PASSWORD and email_list:
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Emergency Alert: {name}"
            msg["From"] = ALERT_EMAILS
            msg["To"] = ", ".join(email_list)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(ALERT_EMAILS, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAILS, email_list, msg.as_string())
            server.quit()

            print("Emails sent")
            success_email = True
        except Exception as e:
            print("Email failed:", e)

    print("Alert result -> SMS:", success_sms, "EMAIL:", success_email)
    return success_sms or success_email


# ===============================
# SPECIFIC ROUTES FIRST (MUST COME BEFORE CATCH-ALL /<band_id>)
# ===============================

@app.route("/im_safe/<band_id>")
def im_safe(band_id):
    band_id = band_id.strip().upper()
    
    # Check rate limit - prevent spam
    if not can_send_safe_notification(band_id):
        return """
        <h2>⏱️ Too Many Safe Alerts</h2>
        <p>You can only send one Safe alert every 5 minutes to prevent spam.</p>
        <p><a href="/">Go Back</a></p>
        """
    
    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 9 and row[0].strip().upper() == band_id:
                name = row[1]
                emergency_phones = row[4] if len(row) > 4 else ""
                emergency_emails = row[5] if len(row) > 5 else ""
                send_safe_notification(name, emergency_phones, emergency_emails, band_id)
                return f"""
                <h1>✅ Marked as Safe</h1>
                <p>Your emergency contacts have been notified that this was a false alarm or the situation is resolved.</p>
                <p><a href="/{band_id}">Go Back</a></p>
                """
    return """
    <h1>Band Not Found</h1>
    <p><a href="/">Home</a></p>
    """

@app.route("/qr/<band_id>")
def qr_code(band_id):
    band_id = band_id.strip().upper()
    url = f"{BASE_URL}/{band_id}"

    img = qrcode.make(url)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")

@app.route("/donate")
def donate():
    return redirect("https://www.paypal.com/ncp/payment/6ZT5B9XMXD3K6")

# ===============================
# CATCH-ALL BAND PROFILE ROUTE (COMES LAST)
# ===============================
@app.route("/<band_id>")
def band_profile_shortcut(band_id):

    blocked_routes = [
        "admin",
        "add",
        "scans",   
        "alert_with_location",
        "manifest.json",
        "pro",
        "privacy",
        "terms",
        "delete-request",
        "sms-opt-in",
        "donate",
        "im_safe",
        "qr"
    ]

    if band_id.lower() in blocked_routes:
        return redirect("/")

    return profile(band_id.upper())
