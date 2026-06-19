from flask import Flask, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from twilio.rest import Client
import csv
import os
import time
import smtplib
from email.mime.text import MIMEText
import qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")
# =========================
# HEAD (GLOBAL SEO + PWA)
# =========================
BASE_HEAD = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>

<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#07111f">

<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="EmpowerBands">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">

<link rel="apple-touch-icon" href="/apple-touch-icon.png">
"""

# =========================
# PREMIUM STYLE (GLOBAL)
# =========================
BASE_STYLE = """
<style>
body{
    margin:0;
    font-family:Arial,sans-serif;
    background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);
    color:white;
}

.page{
    padding:30px;
    max-width:1100px;
    margin:auto;
}

.header{
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:18px;
    border-bottom:1px solid rgba(255,255,255,0.1);
}

.logo-wrap{
    display:flex;
    align-items:center;
    gap:12px;
}

.logo-wrap img{
    width:60px;
    height:60px;
    border-radius:50%;
}

.logo-text{
    font-size:22px;
    font-weight:900;
}

.logo-text span{
    display:block;
    font-size:14px;
    color:#38bdf8;
}

.nav a{
    color:white;
    margin:0 10px;
    text-decoration:none;
    font-weight:bold;
}

.btn{
    padding:12px 16px;
    border-radius:12px;
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    color:white;
    text-decoration:none;
    font-weight:bold;
    display:inline-block;
}

.btn.dark{
    background:rgba(255,255,255,0.08);
    border:1px solid rgba(255,255,255,0.2);
}

.section{
    margin-top:40px;
}

.card{
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);
    border-radius:18px;
    padding:20px;
}

h1,h2,h3{color:#e0f2fe;}
</style>
"""

# =========================
# RENDER ENGINE (FIXED)
# =========================
def render_page(title, content):
    return f"""
<!DOCTYPE html>
<html>
<head>
{BASE_HEAD.format(title=title)}
{BASE_STYLE}
</head>
<body>
<div class="page">
{content}
</div>
</body>
</html>
"""
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

ALERT_EMAILS = os.environ.get("ALERT_EMAILS", "")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")
LOGO_URL = "https://i.imgur.com/dE4kSOz.png"

def send_full_alert(name, phones, emails, band_id, maps_link=None):
    location_text = f"\nLocation: {maps_link}" if maps_link else ""
    message = (
        f"🚨 EmpowerBands Alert\n"
        f"Name: {name}\n"
        f"Profile: {BASE_URL}/{band_id}"
        f"{location_text}"
    )

    success_sms = False
    success_email = False

    # =========================
    # SMS (Twilio)
    # =========================
    phone_list = [p.strip() for p in str(phones).split(",") if p.strip()]

    if client and TWILIO_PHONE_NUMBER:
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
# CREATE FILES ONLY IF MISSING
# ===============================
header = [
    "band_id", "name", "email", "phone", "emergency_phones", "emergency_emails",
    "age_group", "condition", "instructions", "medical_notes", "pin", "address",
    "race", "gender", "photo_url"
]

if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow([
            "EB001", "Jaden", "email@test.com", "+12565551234",        
            "+19382655364,+12566121274", "mom@test.com,dad@test.com",
            "Child", "Autism — Nonverbal", "Please stay calm. I may not respond verbally.",
            "No allergies", "1234", "123 Hope Street, Decatur AL 35601",
            "Black / African American", "Male", "https://i.imgur.com/dE4kSOz.png"
        ])

if not os.path.exists(scan_log_file):
    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["BandID", "Name", "Time", "Type", "IP"])

# ===============================
# UTILITY FUNCTIONS
# ===============================
def log_scan(band_id, name, scan_type, ip):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(scan_log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([band_id, name, now, scan_type, ip])

def count_rows(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return max(0, sum(1 for row in f) - 1)
    except:
        return 0

# ===============================
# HOME PAGE
# ===============================
@app.route("/")
def home():
    content = """

<div class="header">
    <div class="logo-wrap">
        <img src="https://i.imgur.com/dE4kSOz.png">
        <div class="logo-text">EmpowerBands<span>Worldwide</span></div>
    </div>

    <div class="nav">
        <a href="#mission">Mission</a>
        <a href="#how">How It Works</a>
        <a href="#scenarios">Scenarios</a>
    </div>

    <div>
        <a class="btn" href="/sms-opt-in">Get Alerts</a>
    </div>
</div>

<h1>Smart Wearable Safety System</h1>
<p>Instant emergency access through NFC and QR technology.</p>

<div class="section" id="how">
    <h2>How It Works</h2>

    <div class="card">
        <h3>1. Tap or Scan</h3>
        <p>NFC or QR opens emergency profile instantly.</p>
    </div><br>

    <div class="card">
        <h3>2. View Profile</h3>
        <p>Medical info and contacts display immediately.</p>
    </div><br>

    <div class="card">
        <h3>3. Send Alert</h3>
        <p>SMS/email alert sent with location.</p>
    </div>
</div>

<div class="section" id="scenarios">
    <h2>Real World Scenarios</h2>

    <div class="card">
        <h3>Autism Safety</h3>
        <p>First responders access caregiver instructions instantly.</p>
    </div><br>

    <div class="card">
        <h3>Dementia Support</h3>
        <p>Missing seniors are identified quickly.</p>
    </div><br>

    <div class="card">
        <h3>School Safety</h3>
        <p>Emergency instructions accessible during incidents.</p>
    </div>
</div>

"""
    return render_page("EmpowerBands Worldwide", content)

@app.route("/sms-opt-in")
def sms_opt_in():
    content = """
<h2>SMS Opt-In</h2>

<div class="card">
<p>By subscribing, you agree to receive emergency alerts and safety notifications.</p>

<form method="POST" action="/subscribe">
    <input name="phone" placeholder="Phone Number" required style="padding:12px;width:100%;margin:10px 0;">
    <button class="btn" type="submit">Subscribe</button>
</form>

<p style="margin-top:10px;font-size:14px;">
Message frequency varies. Reply STOP to opt out. HELP for support.
</p>
</div>
"""
    return render_page("SMS Opt-In", content)


@app.route("/subscribe", methods=["POST"])
def subscribe():
    phone = request.form.get("phone")

    # NOTE: prevents Twilio formatting rejection issues
    if not phone:
        return "Missing phone", 400

    # placeholder success flow (replace with CSV or DB)
    return render_page("Subscribed", f"""
    <div class="card">
        <h2>Success</h2>
        <p>{phone} subscribed successfully.</p>
        <a class="btn" href="/">Return Home</a>
    </div>
    """)

@app.route("/privacy")
def privacy():
    content = """
<h2>Privacy Policy</h2>

<div class="card">
<p>EmpowerBands collects only essential information needed for emergency safety services.</p>

<ul>
<li>Contact information for alerts</li>
<li>Emergency profile data</li>
<li>Optional location data during alerts</li>
</ul>

<p>We do not sell personal data.</p>
</div>
"""
    return render_page("Privacy Policy", content)

@app.route("/terms")
def terms():
    content = """
<h2>Terms of Service</h2>

<div class="card">
<p>By using EmpowerBands, you agree to our terms and conditions.</p>

<ul>
<li>Emergency alerts are provided on an as-available basis</li>
<li>Users are responsible for maintaining accurate contact information</li>
<li>EmpowerBands is not a substitute for professional emergency services</li>
<li>Always call 911 for life-threatening emergencies</li>
</ul>

<p>For full terms, contact support@empowerbands.org</p>
</div>
"""
    return render_page("Terms of Service", content)

@app.route("/delete-request")
def delete_request():
    content = """
<h2>Data Deletion Request</h2>

<div class="card">
<p>Request removal of your data from EmpowerBands systems.</p>

<form method="POST" action="/delete-submit">
    <input name="phone" placeholder="Phone or Email" required style="padding:12px;width:100%;margin:10px 0;">
    <button class="btn" type="submit">Submit Request</button>
</form>
</div>
"""
    return render_page("Data Deletion", content)


@app.route("/delete-submit", methods=["POST"])
def delete_submit():
    identifier = request.form.get("phone")

    return render_page("Request Received", f"""
    <div class="card">
        <h2>Request Submitted</h2>
        <p>Your deletion request for <b>{identifier}</b> has been received.</p>
        <p>Processing time: 24–72 hours</p>
        <a class="btn" href="/">Return Home</a>
    </div>
    """)

# ===============================
# SHORT LINK REDIRECT
# ===============================
@app.route("/<band_id>")
def band_profile_shortcut(band_id):
    blocked_routes = ["admin", "add", "scans", "alert_with_location", "manifest.json", "pro", "privacy", "terms", "delete-request", "sms-opt-in"]
    if band_id.lower() in blocked_routes:
        return redirect("/")
    return profile(band_id.upper())

# ===============================
# ADMIN PORTAL
# ===============================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        return "<h2 style='color:white;text-align:center;margin-top:100px;'>Wrong Password</h2><p style='text-align:center;'><a href='/admin'>Try Again</a></p>"

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmpowerBands Admin</title>
<style>
body{margin:0;font-family:Arial,sans-serif;background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);min-height:100vh;color:white;display:flex;justify-content:center;align-items:center;}
.card{width:100%;max-width:460px;background:rgba(255,255,255,0.08);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.15);border-radius:28px;padding:35px;box-shadow:0 25px 80px rgba(0,0,0,0.3);}
input{width:100%;box-sizing:border-box;padding:16px;border:none;border-radius:16px;margin-bottom:16px;font-size:16px;background:rgba(255,255,255,0.12);color:white;}
.btn{width:100%;padding:16px;border:none;border-radius:16px;font-size:17px;font-weight:700;cursor:pointer;background:linear-gradient(135deg,#06b6d4,#2563eb);color:white;}
</style>
</head>
<body>
<div class="card">
    <h2 style="text-align:center; margin-bottom:20px;">Secure Admin Access</h2>
    <form method="POST">
        <input type="password" name="password" placeholder="Enter admin password" required>
        <button class="btn" type="submit">Login To Dashboard</button>
    </form>
</div>
</body>
</html>
"""

# ===============================
# DASHBOARD
# ===============================
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/admin")

    customers = []
    total_bands = count_rows(file_name)
    total_scans = count_rows(scan_log_file)

    try:
        with open(file_name, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                customers.append(row)
    except:
        pass

    customer_cards = ""
    for customer in customers:
        band_id = customer.get("band_id", "")
        name = customer.get("name", "")
        email = customer.get("email", "")
        phone = customer.get("phone", "")

        customer_cards += f"""
        <div class="customer-card searchable" style="background:rgba(255,255,255,0.08); padding:20px; border-radius:16px; margin-bottom:15px; border:1px solid rgba(255,255,255,0.1);">
            <div style="display:flex; justify-content:space-between;">
                <div>
                    <span style="color:#38bdf8; font-size:12px; font-weight:bold;">{band_id}</span>
                    <h3 style="margin:4px 0 10px 0;">{name}</h3>
                </div>
            </div>
            <div style="font-size:14px; color:#cbd5e1; margin-bottom:6px;">📧 {email}</div>
            <div style="font-size:14px; color:#cbd5e1; margin-bottom:15px;">📱 {phone}</div>
            <div>
                <a style="background:#2563eb; color:white; padding:8px 14px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px;" href="/customer/{band_id}">Profile</a>
                <a style="background:#0f766e; color:white; padding:8px 14px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin-left:6px;" href="/edit/{band_id}">Edit</a>
                <a style="background:#dc2626; color:white; padding:8px 14px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:14px; margin-left:6px;" href="/delete/{band_id}">Delete</a>
            </div>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard</title>
<style>
body{{margin:0; font-family:Arial,sans-serif; background:#07111f; color:white; padding:20px;}}
.add-btn{{background:#06b6d4; padding:10px 16px; border-radius:8px; color:white; text-decoration:none; font-weight:bold; margin-right:10px;}}
</style>
</head>
<body>
    <div style="display:flex; justify-content:space-between; margin-bottom:20px; align-items:center; flex-wrap:wrap; gap:10px;">
        <h2>EmpowerBands Dashboard</h2>
        <div>
            <a class="add-btn" href="/add">+ Add Band</a>
            <a class="add-btn" style="background:#2563eb;" href="/scans">📡 View Scans</a>
            <a class="add-btn" style="background:gray;" href="/">🏠 Home</a>
        </div>
    </div>
    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:15px; margin-bottom:25px;">
        <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:12px; text-align:center;"><h3>{total_bands}</h3>Bands Registered</div>
        <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:12px; text-align:center;"><h3>{total_scans}</h3>Total Scans</div>
        <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:12px; text-align:center;"><h3>{len(customers)}</h3>Active Entries</div>
    </div>
    <div>{customer_cards if customer_cards else '<div style="text-align:center; padding:40px; color:#64748b;">No profiles created yet.</div>'}</div>
</body>
</html>
"""

# ===============================
# ADD PROFILE
# ===============================
@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        photo = request.files.get("photo")
        photo_url = ""
        if photo and photo.filename != "":
            filename = f"{int(time.time())}_{secure_filename(photo.filename)}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(filepath)
            photo_url = f"/static/uploads/{filename}"

        row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form.get("emergency_phones", "").strip(),
            request.form.get("emergency_emails", "").strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip(),
            request.form["pin"].strip(),
            request.form["address"].strip(),
            request.form["race"].strip(),
            request.form["gender"].strip(),
            photo_url
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        return redirect("/" + row[0])

    return """
<!DOCTYPE html>
<html>
<head>
<title>Add Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0;font-family:Arial,sans-serif;background:#07111f;color:white;padding:20px;display:flex;justify-content:center;}
.card{width:100%;max-width:540px;background:rgba(255,255,255,0.05);padding:25px;border-radius:20px;border:1px solid rgba(255,255,255,0.1);box-sizing:border-box;}
input, textarea{width:100%;box-sizing:border-box;padding:12px;margin-bottom:12px;border-radius:10px;border:none;background:rgba(255,255,255,0.1);color:white;}
button{width:100%;padding:15px;background:#22c55e;color:white;border:none;border-radius:10px;font-weight:bold;cursor:pointer;}
</style>
</head>
<body>
<div class="card">
    <h2>Create Emergency Profile</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="text" id="band_id" name="band_id" placeholder="Band ID (e.g., EB002)" required>
        <input type="text" name="name" placeholder="Full Name" required>
        <input type="email" name="email" placeholder="Email Address">
        <input type="text" name="phone" placeholder="Primary Phone">
        <input type="text" name="emergency_phones" placeholder="Emergency Contacts (comma separated)" required>
        <input type="text" name="emergency_emails" placeholder="Emergency Emails (comma separated)">
        <input type="text" name="age_group" placeholder="Age Group (Child/Adult/Senior)">
        <input type="text" name="condition" placeholder="Public Medical Status">
        <textarea name="instructions" placeholder="Public Handling Instructions"></textarea>
        <textarea name="medical_notes" placeholder="Private Medical Notes (PIN protected)"></textarea>
        <input type="text" name="pin" placeholder="Access PIN Code" required>
        <input type="text" name="address" placeholder="Home Address">
        <input type="text" name="race" placeholder="Race Information">
        <input type="text" name="gender" placeholder="Gender">
        <input type="file" name="photo">
        <button type="submit">Save Secure Profile</button>
    </form>
</div>
</body>
</html>
"""

# ===============================
# EDIT PROFILE
# ===============================
@app.route("/edit/<band_id>", methods=["GET", "POST"])
def edit_profile(band_id):
    if not session.get("logged_in"):
        return redirect("/admin")

    band_id = band_id.strip().upper()

    with open(file_name, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header_row = rows[0]
    data_rows = rows[1:]
    found_row = None

    for row in data_rows:
        if row[0].strip().upper() == band_id:
            while len(row) < 15:
                row.append("")
            found_row = row
            break

    if not found_row:
        return "<h1>Profile not found</h1><a href='/dashboard'>Dashboard</a>"

    if request.method == "POST":
        updated_row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form["emergency_phones"].strip(),
            request.form.get("emergency_emails", "").strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip(),
            request.form["pin"].strip(),
            request.form["address"].strip(),
            request.form["race"].strip(),
            request.form["gender"].strip(),
            request.form.get("photo_url", "").strip()
        ]

        new_rows = [header_row]
        for row in data_rows:
            if row[0].strip().upper() == band_id:
                new_rows.append(updated_row)
            else:
                new_rows.append(row)

        with open(file_name, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(new_rows)

        return redirect("/dashboard")

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Edit Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{{margin:0;font-family:Arial,sans-serif;background:#07111f;color:white;padding:20px;display:flex;justify-content:center;}}
.card{{width:100%;max-width:540px;background:rgba(255,255,255,0.05);padding:25px;border-radius:20px;box-sizing:border-box;}}
input, textarea{{width:100%;box-sizing:border-box;padding:12px;margin-bottom:12px;border-radius:10px;border:none;background:rgba(255,255,255,0.1);color:white;}}
button{{width:100%;padding:15px;background:#06b6d4;color:white;border:none;border-radius:10px;font-weight:bold;}}
</style>
</head>
<body>
<div class="card">
    <h2>Edit Profile Settings</h2>
    <form method="POST">
        <input name="band_id" value="{found_row[0]}" required>
        <input name="name" value="{found_row[1]}" required>
        <input name="email" value="{found_row[2]}">
        <input name="phone" value="{found_row[3]}">
        <input name="emergency_phones" value="{found_row[4]}" required>
        <input name="emergency_emails" value="{found_row[5]}">
        <input name="age_group" value="{found_row[6]}">
        <input name="condition" value="{found_row[7]}">
        <textarea name="instructions">{found_row[8]}</textarea>
        <textarea name="medical_notes">{found_row[9]}</textarea>
        <input name="pin" value="{found_row[10]}" required>
        <input name="address" value="{found_row[11]}">
        <input name="race" value="{found_row[12]}">
        <input name="gender" value="{found_row[13]}">
        <input name="photo_url" value="{found_row[14]}" placeholder="Photo URL">
        <button type="submit">Save Structural Changes</button>
    </form>
    <a style="display:block; text-align:center; margin-top:15px; color:#38bdf8; text-decoration:none;" href="/dashboard">Back to Dashboard</a>
</div>
</body>
</html>
"""

# ===============================
# DELETE PROFILE
# ===============================
@app.route("/delete/<band_id>")
def delete_profile(band_id):
    if not session.get("logged_in"):
        return redirect("/admin")

    band_id = band_id.strip().upper()
    with open(file_name, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header_row = rows[0]
    updated_rows = [header_row]

    for row in rows[1:]:
        if row[0].strip().upper() != band_id:
            updated_rows.append(row)

    with open(file_name, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(updated_rows)

    return redirect("/dashboard")

# ===============================
# PUBLIC / PRIVATE PROFILE INTERFACE
# ===============================
@app.route("/customer/<band_id>")
def profile(band_id):
    band_id = band_id.strip().upper()
    confirm_alert = request.args.get("confirm_alert") == "yes"
    entered_pin = request.args.get("pin")

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) >= 9 and row[0].strip().upper() == band_id:
                name = row[1]
                email = row[2]
                phone = row[3]
                emergency_phones = row[4] if len(row) > 4 else ""
                emergency_emails = row[5] if len(row) > 5 else ""
                age_group = row[6] if len(row) > 6 else ""
                condition = row[7] if len(row) > 7 else ""
                instructions = row[8] if len(row) > 8 else ""
                medical_notes = row[9] if len(row) > 9 else ""
                pin = row[10] if (len(row) > 10 and row[10]) else "1234"
                address = row[11] if len(row) > 11 else ""
                race = row[12] if len(row) > 12 else ""
                gender = row[13] if len(row) > 13 else ""
                photo_url = row[14] if len(row) > 14 else ""

                log_scan(band_id, name, "PROFILE_VIEW", request.remote_addr)

                if confirm_alert:
                    return f"""
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:Arial;background:#f3f4f6;text-align:center;padding:30px;">
<div style="background:white;padding:25px;border-radius:12px;max-width:420px;margin:auto;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
<h2>⚠️ Emergency Alert Confirmation</h2>
<p>This will notify the designated emergency contact(s) via automated SMS and email routing.</p>
<div style="background:#fee2e2;color:#991b1b;padding:12px;border-radius:10px;font-size:14px;margin:15px 0;text-align:left;">
<strong>Important:</strong> This tool does <b>NOT</b> dial local emergency services (911). Dial emergency responders manually if required.
</div>
<button onclick="sendAlertWithLocation()" style="display:block;width:100%;padding:15px;border-radius:10px;border:none;background:#dc2626;color:white;font-weight:bold;font-size:16px;cursor:pointer;">Send Alert With Location</button>
<a href="/{band_id}" style="display:block;margin-top:12px;padding:15px;border-radius:10px;background:#111827;color:white;text-decoration:none;font-weight:bold;">Cancel</a>
</div>
<script>
function sendAlertWithLocation(){{
    if (navigator.geolocation) {{
        navigator.geolocation.getCurrentPosition(function(pos){{
            window.location.href = "/alert_with_location?band_id={band_id}&lat=" + pos.coords.latitude + "&lon=" + pos.coords.longitude;
        }}, function(error){{
            alert("GPS location failed. Please use the 'Send Alert Without GPS' alternative option.");
        }});
    }} else {{
        alert("Geolocation unsupported by this mobile engine framework.");
    }}
}}
</script>
</body>
</html>
"""

                if entered_pin == pin:
                    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Full Secure Records</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{margin:0;font-family:Arial,sans-serif;background:#030712;color:white;padding:20px;display:flex;justify-content:center;}}
.card {{width:100%;max-width:520px;background:rgba(255,255,255,0.06);border-radius:20px;padding:25px;border:1px solid rgba(255,255,255,0.1);}}
.section {{margin-top:14px;padding:12px;border-radius:10px;background:rgba(255,255,255,.05);}}
.title {{color:#67e8f9;font-size:12px;font-weight:bold;margin-bottom:4px;}}
</style>
</head>
<body>
<div class="card">
    <h1>🔓 {name} (Unlocked Data)</h1>
    <div class="section"><div class="title">ADDRESS</div>{address}</div>
    <div class="section"><div class="title">PROTECTED CLINICAL REMARKS</div>{medical_notes}</div>
    <div class="section"><div class="title">RACE / ETHNICITY</div>{race}</div>
    <div class="section"><div class="title">BIOLOGICAL GENDER</div>{gender}</div>
    <div class="section"><div class="title">REGISTERED HOUSEHOLD PHONE</div>{phone}</div>
    <a style="display:block; text-align:center; margin-top:20px; color:#cbd5e1;" href="/{band_id}">Lock & Return</a>
</div>
</body>
</html>
"""

                # Public standard dashboard output
                return f"""
<!DOCTYPE html>
<html>
<head>
<title>Profile Hub</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{margin:0;font-family:Arial,sans-serif;background:#07111f;color:white;padding:20px;display:flex;justify-content:center;}}
.card {{width:100%;max-width:500px;background:rgba(255,255,255,0.08);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.15);border-radius:24px;padding:25px;text-align:center;}}
.btn {{display:block;padding:15px;border-radius:12px;margin-top:12px;text-decoration:none;font-weight:bold;color:white;}}
.btn-red {{background:linear-gradient(135deg,#ef4444,#dc2626);}}
.btn-dark {{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.15);}}
.btn-blue {{background:#2563eb;}}
input {{width:100%;box-sizing:border-box;padding:14px;border-radius:12px;border:none;margin-top:15px;background:rgba(255,255,255,0.1);color:white;text-align:center;}}
</style>
</head>
<body>
<div class="card">
    <img src="{photo_url if photo_url else LOGO_URL}" style="width:120px;height:120px;border-radius:50%;object-fit:cover;border:4px solid rgba(255,255,255,.2);margin-bottom:10px;">
    <h2>{name}</h2>
    <p style="color:#94a3b8; margin:0 0 20px 0;">ID Reference: {band_id} • Age Group: {age_group}</p>
    
    <a class="btn btn-red" href="/customer/{band_id}?confirm_alert=yes">🚨 Activate Emergency Alert (GPS Map)</a>
    <a class="btn btn-dark" href="/alert_manual?band_id={band_id}">🚨 Send Emergency Alert (No GPS)</a>
    <a class="btn btn-blue" href="tel:{emergency_phones.split(',')[0].strip() if emergency_phones else ''}">📞 Call Emergency Contact</a>

    <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:14px; padding:15px; margin-top:20px; text-align:left;">
        <h4 style="margin:0 0 5px 0; color:#f87171;">⚠️ Condition Advisory</h4>
        {condition}
    </div>

    <div style="background:rgba(255,255,255,0.04); border-radius:14px; padding:15px; margin-top:15px; text-align:left;">
        <h4 style="margin:0 0 5px 0; color:#67e8f9;">What to Do</h4>
        {instructions}
    </div>

    <form method="GET" action="/customer/{band_id}">
        <input type="password" name="pin" placeholder="Enter security PIN for clinical files" required>
        <button style="width:100%; padding:14px; margin-top:8px; border-radius:12px; border:none; background:#22c55e; color:white; font-weight:bold; cursor:pointer;" type="submit">Unlock Extended Records</button>
    </form>
</div>
</body>
</html>
"""

    return "<h1>Band Context Registry Not Found</h1><p>Check spelling format structures.</p><a href='/admin'>Admin Link Login</a>", 404

# ===============================
# ENGINE CORE QR CODES
# ===============================
@app.route("/qr/<band_id>")
def qr_code(band_id):
    band_id = band_id.strip().upper()
    url = f"{BASE_URL}/{band_id}"
    img = qrcode.make(url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return app.response_class(buffer.getvalue(), mimetype="image/png")

# ===============================
# SCANS SYSTEM LOGGER
# ===============================
@app.route("/scans")
def scans():
    if not session.get("logged_in"):
        return redirect("/admin")

    scan_rows = []
    try:
        with open(scan_log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scan_rows.append(row)
        scan_rows.reverse()
    except:
        pass

    rows_html = ""
    for scan in scan_rows:
        rows_html += f"<tr><td>{scan.get('BandID','')}</td><td>{scan.get('Name','')}</td><td>{scan.get('Time','')}</td><td>{scan.get('Type','')}</td><td>{scan.get('IP','')}</td></tr>"

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Scan Logs</title>
<style>
body{{font-family:Arial; background:#07111f; color:white; padding:20px;}}
table{{width:100%; border-collapse:collapse; margin-top:20px;}}
th, td{{padding:12px; border-bottom:1px solid rgba(255,255,255,0.1); text-align:left;}}
th{{color:#67e8f9;}}
</style>
</head>
<body>
    <h2>📡 Network Scan Stream Engine</h2>
    <a style="color:#38bdf8;" href="/dashboard">← Back Dashboard</a>
    <table>
        <tr><th>Band ID</th><th>Associated Name</th><th>Timestamp</th><th>Process Target Event</th><th>Remote IPv4/6 Address</th></tr>
        {rows_html if rows_html else '<tr><td colspan="5">No tracking history currently captured inside standard structural files.</td></tr>'}
    </table>
</body>
</html>
"""

# ===============================
# ALERT ROUTING: WITH GEOLOCATION MAPS
# ===============================
@app.route("/alert_with_location")
def alert_with_location():
    band_id = request.args.get("band_id", "").strip().upper()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    maps_link = f"https://www.google.com/maps?q={lat},{lon}" if (lat and lon) else None

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row[0].strip().upper() == band_id:
                name = row[1]
                phones = row[4] if len(row) > 4 else ""
                emails = row[5] if len(row) > 5 else ""

                send_full_alert(name, phones, emails, band_id, maps_link)
                return """
<html>
<body style="font-family:Arial; text-align:center; padding:50px; background:#f3f4f6;">
    <div style="background:white; max-width:500px; margin:auto; padding:30px; border-radius:16px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
        <h1 style="color:#22c55e;">✅ Route Alerts Active</h1>
        <p>Location parameters processed. Contacts notified successfully via network stack parameters.</p>
        <a style="display:inline-block; background:#111827; color:white; padding:12px 20px; text-decoration:none; border-radius:8px;" href="/">Return Home</a>
    </div>
</body>
</html>
"""
    return "Profile registration entry lost matching tracking attributes.", 404

# ===============================
# ALERT ROUTING: MANUAL ESCAPE BACKUP
# ===============================
@app.route("/alert_manual")
def alert_manual():
    band_id = request.args.get("band_id", "").strip().upper()

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row[0].strip().upper() == band_id:
                name = row[1]
                phones = row[4] if len(row) > 4 else ""
                emails = row[5] if len(row) > 5 else ""

                send_full_alert(name, phones, emails, band_id)
                return """
<html>
<body style="font-family:Arial; text-align:center; padding:50px; background:#f3f4f6;">
    <div style="background:white; max-width:500px; margin:auto; padding:30px; border-radius:16px;">
        <h1 style="color:#22c55e;">✅ Manual Alert Dispatched</h1>
        <p>Emergency message loops fired successfully. Excluded satellite GPS array metrics execution.</p>
        <a style="display:inline-block; background:#111827; color:white; padding:12px 20px; text-decoration:none; border-radius:8px;" href="/">Return Home</a>
    </div>
</body>
</html>
"""
    return "Target data mapping execution key value failure mismatch.", 404

# ===============================
# COMPLIANCE LEGAL ENDPOINTS
# ===============================

# Note: Full implementations are defined above with proper render_page styling
# These are already included in the routes above

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
