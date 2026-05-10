from flask import Flask, request, redirect, session
from twilio.rest import Client
import csv
import os
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.onrender.com")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

LOGO_URL = "https://i.imgur.com/dE4kSOz.png"


# ===============================
# CREATE FILES
# ===============================

demo_row = [
    "EB001",
    "Jaden",
    "email@test.com",
    "+19382655364,+12566121274",
    "Child",
    "Autism – Nonverbal",
    "Please stay calm. I may not respond verbally. Call my emergency contact(s) immediately.",
    "No allergies",
    "1234"
]

header = [
    "band_id", "name", "email", "phone", "age_group",
    "condition", "instructions", "medical_notes", "pin"
]

rows = []

if os.path.exists(file_name):
    with open(file_name, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

clean_rows = [header]
demo_exists = False

for row in rows[1:]:
    if len(row) >= 9:
        if row[0].strip().upper() == "EB001":
            clean_rows.append(demo_row)
            demo_exists = True
        else:
            clean_rows.append(row)

if not demo_exists:
    clean_rows.append(demo_row)

with open(file_name, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(clean_rows)

if not os.path.exists(scan_log_file):
    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["BandID", "Name", "Time", "Type", "IP"])


# ===============================
# FUNCTIONS
# ===============================

def log_scan(band_id, name, scan_type, ip):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(scan_log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([band_id, name, now, scan_type, ip])


def send_alert_text(name, phones, band_id):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        print("Twilio not configured.")
        return False

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    message = (
        f"🚨 EmpowerBands Alert: {name}'s band was scanned in ALERT MODE. "
        f"They may be lost, confused, or unable to communicate. "
        f"Profile: {BASE_URL}/customer/{band_id}"
    )

    phone_list = [p.strip() for p in phones.split(",") if p.strip()]

    for phone in phone_list:
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=phone
            )
            print(f"Alert sent to {phone}")
        except Exception as e:
            print(f"Twilio error for {phone}: {e}")

    return True


# ===============================
# HOME PAGE
# ===============================

# ===============================
# HOME PAGE
# ===============================

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>EmpowerBands</title>
        <link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0a58ca">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="EmpowerBands">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: linear-gradient(180deg, #eaf3ff 0%, #ffffff 100%);
                color: #102033;
            }

            .page {
                max-width: 520px;
                margin: 0 auto;
                padding: 30px 20px;
                text-align: center;
            }

            .logo {
                width: 150px;
                margin-bottom: 15px;
            }

            .badge {
                background: #dcebff;
                color: #0a58ca;
                padding: 8px 14px;
                border-radius: 999px;
                font-size: 13px;
                font-weight: bold;
                display: inline-block;
                margin-bottom: 15px;
            }

            h1 {
                font-size: 34px;
                margin: 10px 0;
                color: #0a58ca;
            }

            .lead {
                font-size: 17px;
                color: #445;
                margin-bottom: 25px;
            }

            .btn {
                display: block;
                padding: 16px;
                margin: 10px auto;
                max-width: 340px;
                border-radius: 14px;
                text-decoration: none;
                font-weight: bold;
                background: #0a58ca;
                color: white;
            }

            .btn.dark {
                background: #111827;
            }

            .card {
                background: white;
                border-radius: 20px;
                padding: 20px;
                margin-top: 25px;
                text-align: left;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            }

            .item {
                margin: 10px 0;
            }

            .footer {
                margin-top: 20px;
                font-size: 13px;
                color: #666;
            }
        </style>
    </head>

    <body>
        <div class="page">

            <img class="logo" src="https://i.imgur.com/dE4kSOz.png">

            <div class="badge">Emergency Support Wearable</div>

            <h1>EmpowerBands</h1>

            <p class="lead">
                Tap the band to instantly access emergency support info,
                contact caregivers, and send alerts with location.
            </p>

            <a class="btn" href="/customer/EB001">View Live Demo</a>
            <a class="btn dark" href="/admin">Admin Login</a>

            <div class="card">
                <div class="item">🔵 Tap band with phone</div>
                <div class="item">🔵 View instructions instantly</div>
                <div class="item">🔵 Call caregiver fast</div>
                <div class="item">🔵 Send emergency alert + location</div>
            </div>

            <div class="footer">
                Built for families, caregivers, and emergency responders
            </div>

        </div>
    </body>
    </html>
    """


# ===============================
# SHORT LINK REDIRECT
# ===============================

@app.route("/<band_id>")
def old_band_link(band_id):
    blocked_routes = ["admin", "add", "alert_with_location", "customer"]

    if band_id.lower() in blocked_routes:
        return redirect("/")

    return redirect(f"/customer/{band_id}")

# ===============================
# ADMIN LOGIN
# ===============================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/add")

        return """
        <h2>Wrong password</h2>
        <p><a href='/admin'>Try again</a></p>
        """

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>EmpowerBands Admin</title>

<style>

body{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);
    min-height:100vh;
    color:white;
    overflow:hidden;
}

.bg-glow{
    position:absolute;
    width:500px;
    height:500px;
    background:#06b6d4;
    filter:blur(140px);
    opacity:.15;
    top:-120px;
    right:-120px;
}

.page{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
    position:relative;
    z-index:2;
}

.card{
    width:100%;
    max-width:460px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:35px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}

.logo{
    text-align:center;
    font-size:38px;
    font-weight:800;
    margin-bottom:6px;
    letter-spacing:.5px;
}

.logo span{
    color:#38bdf8;
}

.subtitle{
    text-align:center;
    color:#cbd5e1;
    margin-bottom:28px;
    font-size:15px;
}

input{
    width:100%;
    box-sizing:border-box;
    padding:16px;
    border:none;
    outline:none;
    border-radius:16px;
    margin-bottom:16px;
    font-size:16px;
    background:rgba(255,255,255,0.12);
    color:white;
}

input::placeholder{
    color:#cbd5e1;
}

.btn{
    width:100%;
    padding:16px;
    border:none;
    border-radius:16px;
    font-size:17px;
    font-weight:700;
    cursor:pointer;
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    color:white;
    transition:.25s;
}

.btn:hover{
    transform:translateY(-2px);
    opacity:.95;
}

.footer{
    text-align:center;
    margin-top:22px;
    color:#94a3b8;
    font-size:12px;
    line-height:1.5;
}

.shield{
    width:80px;
    height:80px;
    margin:0 auto 20px;
    border-radius:50%;
    background:rgba(56,189,248,.12);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:34px;
    border:1px solid rgba(255,255,255,.12);
}

</style>
</head>

<body>

<div class="bg-glow"></div>

<div class="page">

<div class="card">

<div class="shield">
🛡️
</div>

<div class="logo">
Empower<span>Bands</span>
</div>

<div class="subtitle">
Secure Admin Access Portal
</div>

<form method="POST">

<input
type="password"
name="password"
placeholder="Enter admin password"
required
>

<button class="btn" type="submit">
Login To Dashboard
</button>

</form>

<div class="footer">
Protected access for authorized personnel only.<br>
EmpowerBands Emergency System
</div>

</div>

</div>

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
        row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip(),
            request.form["pin"].strip()
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        return redirect("/customer/" + row[0])

    return """
<!DOCTYPE html>
<html>
<head>
<title>Add EmpowerBand Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>

body{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);
    min-height:100vh;
    color:white;
}

.page{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
}

.card{
    width:100%;
    max-width:560px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:30px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}

h1{
    margin:0;
    font-size:34px;
    font-weight:800;
    text-align:center;
}

.subtitle{
    text-align:center;
    color:#cbd5e1;
    margin:10px 0 25px;
}

input, textarea{
    width:100%;
    box-sizing:border-box;
    padding:15px;
    border:none;
    outline:none;
    border-radius:16px;
    background:rgba(255,255,255,.1);
    color:white;
    margin-bottom:14px;
    font-size:16px;
}

textarea{
    min-height:90px;
    resize:vertical;
}

input::placeholder,
textarea::placeholder{
    color:#cbd5e1;
}

button{
    width:100%;
    padding:16px;
    border:none;
    border-radius:16px;
    background:linear-gradient(135deg,#22c55e,#06b6d4);
    color:white;
    font-weight:bold;
    font-size:17px;
    cursor:pointer;
}

.footer{
    text-align:center;
    margin-top:18px;
    color:#94a3b8;
    font-size:12px;
}

</style>
</head>

<body>

<div class="page">

<div class="card">

<h1>Add Profile</h1>

<div class="subtitle">
Create a secure EmpowerBand emergency profile
</div>

<form method="POST">

<input name="band_id" placeholder="Band ID example: EB002" required>

<input name="name" placeholder="Full Name" required>

<input name="email" placeholder="Email">

<input name="phone" placeholder="Emergency Phone Number" required>

<input name="age_group" placeholder="Child / Adult / Senior">

<input name="condition" placeholder="Public condition example: Autism - Nonverbal">

<textarea name="instructions" placeholder="Public instructions"></textarea>

<textarea name="medical_notes" placeholder="Private medical notes"></textarea>

<input name="pin" placeholder="PIN example: 1234" required>

<button type="submit">
Save Profile
</button>

</form>

<div class="footer">
EmpowerBands Admin System
</div>

</div>

</div>

</body>
</html>
"""


# ===============================
# BAND PROFILE
# ===============================

@app.route("/<band_id>")
def customer_page(band_id):
    band_id = band_id.strip().upper()
    confirm_alert = request.args.get("confirm_alert") == "yes"
    alert_mode = request.args.get("alert") == "yes"

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) >= 9 and row[0].strip().upper() == band_id:
                name = row[1]
                email = row[2]
                phone = row[3]
                age_group = row[4]
                condition = row[5]
                instructions = row[6]
                medical_notes = row[7]
                pin = row[8] if row[8] else "1234"
                entered_pin = request.args.get("pin")

                log_scan(band_id, name, "scan", request.remote_addr)

                if alert_mode:
                    success = send_alert_text(name, phone, band_id)

                    if success:
                        return f"""
                        <h1>✅ Alert Sent</h1>
                        <p>Emergency contact(s) have been notified.</p>
                        <p><a href="/customer/{band_id}">Go Back</a></p>
                        """
                    else:
                        return f"""
                        <h1>❌ Alert Failed</h1>
                        <p>There was a problem sending the alert.</p>
                        <p><a href="/customer/{band_id}">Go Back</a></p>
                        """

                if confirm_alert:
                    return f"""
                    <html>
                    <head>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                    </head>
                    <body style="font-family:Arial;background:#f3f4f6;text-align:center;padding:30px;">
                        <div style="background:white;padding:25px;border-radius:12px;max-width:420px;margin:auto;">
                            <h2>⚠️ Emergency Alert</h2>
                            <p>This will notify the designated emergency contact(s) on file.</p>

                            <div style="background:#fee2e2;color:#991b1b;padding:12px;border-radius:10px;font-size:14px;margin:15px 0;text-align:left;">
                                <strong>Important:</strong><br>
                                This system does <b>NOT contact 911 or emergency services</b>.<br><br>
                                If this is a life-threatening emergency, please call <b>911 immediately</b>.
                            </div>

                            <button onclick="sendAlertWithLocation()" style="display:block;width:100%;padding:15px;border-radius:10px;border:none;background:#dc2626;color:white;font-weight:bold;font-size:16px;">
                                🚨 Send Alert With Location
                            </button>

                            <a href="/customer/{band_id}" style="display:block;margin-top:12px;padding:15px;border-radius:10px;background:#111827;color:white;text-decoration:none;font-weight:bold;">
                                Cancel
                            </a>
                        </div>

                        <script>
                        function sendAlertWithLocation(){{
                            if (navigator.geolocation) {{
                                navigator.geolocation.getCurrentPosition(function(pos){{
                                    let lat = pos.coords.latitude;
                                    let lon = pos.coords.longitude;
                                    window.location.href = "/alert_with_location?band_id={band_id}&lat=" + lat + "&lon=" + lon;
                                }}, function(){{
                                    window.location.href = "/customer/{band_id}?alert=yes";
                                }});
                            }} else {{
                                window.location.href = "/customer/{band_id}?alert=yes";
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
<title>Full Emergency Info</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>

body {{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#22c55e 0%,#07111f 28%,#030712 100%);
    min-height:100vh;
    color:white;
}}

.page {{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
}}

.card {{
    width:100%;
    max-width:560px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:30px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}}

.badge {{
    display:inline-block;
    background:rgba(34,197,94,.15);
    color:#86efac;
    padding:8px 14px;
    border-radius:999px;
    font-size:13px;
    font-weight:bold;
    margin-bottom:18px;
}}

h1 {{
    margin:0;
    font-size:36px;
    font-weight:800;
}}

.info {{
    color:#cbd5e1;
    margin-top:8px;
    margin-bottom:22px;
}}

.section {{
    margin-top:18px;
    padding:16px;
    border-radius:18px;
    background:rgba(255,255,255,.07);
    border:1px solid rgba(255,255,255,.1);
}}

.section-title {{
    color:#67e8f9;
    font-size:13px;
    font-weight:bold;
    margin-bottom:7px;
}}

.section-text {{
    color:#e5e7eb;
    line-height:1.6;
}}

.btn {{
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    padding:16px;
    border-radius:16px;
    margin-top:16px;
    text-decoration:none;
    font-weight:700;
    font-size:16px;
}}

.btn-blue {{
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    color:white;
}}

.btn-dark {{
    background:rgba(255,255,255,.12);
    color:white;
    border:1px solid rgba(255,255,255,.15);
}}

.footer {{
    margin-top:25px;
    text-align:center;
    color:#94a3b8;
    font-size:12px;
}}

</style>
</head>

<body>

<div class="page">

<div class="card">

<div class="badge">
Unlocked Full Emergency Info
</div>

<h1>{name}</h1>

<div class="info">
{age_group} • ID: {band_id}
</div>

<div class="section">
<div class="section-title">
EMAIL
</div>

<div class="section-text">
{email}
</div>
</div>

<div class="section">
<div class="section-title">
EMERGENCY CONTACT
</div>

<div class="section-text">
{phone}
</div>
</div>

<div class="section">
<div class="section-title">
CONDITION
</div>

<div class="section-text">
{condition}
</div>
</div>

<div class="section">
<div class="section-title">
INSTRUCTIONS
</div>

<div class="section-text">
{instructions}
</div>
</div>

<div class="section">
<div class="section-title">
PRIVATE MEDICAL NOTES
</div>

<div class="section-text">
{medical_notes}
</div>
</div>

<a class="btn btn-blue" href="tel:{phone.split(',')[0].strip()}">
📞 Call Emergency Contact
</a>

<a class="btn btn-dark" href="/customer/{band_id}">
Back to Public View
</a>

<div class="footer">
PIN verified • EmpowerBands Emergency Response System
</div>

</div>

</div>

</body>
</html>
"""
                return f"""
<!DOCTYPE html>
<html>
<head>
<title>EmpowerBand {band_id}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>

body {{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);
    min-height:100vh;
    color:white;
}}

.page {{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
}}

.card {{
    width:100%;
    max-width:520px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:30px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}}

.badge {{
    display:inline-block;
    background:rgba(56,189,248,.12);
    color:#7dd3fc;
    padding:8px 14px;
    border-radius:999px;
    font-size:13px;
    font-weight:bold;
    margin-bottom:18px;
}}

h1 {{
    margin:0;
    font-size:38px;
    font-weight:800;
}}

.info {{
    color:#cbd5e1;
    margin-top:8px;
    margin-bottom:25px;
}}

.alert-box {{
    background:rgba(250,204,21,.12);
    border:1px solid rgba(250,204,21,.35);
    border-radius:18px;
    padding:18px;
    margin-bottom:20px;
}}

.section {{
    margin-top:22px;
}}

.section-title {{
    color:#67e8f9;
    font-size:14px;
    font-weight:bold;
    margin-bottom:8px;
}}

.section-text {{
    color:#e5e7eb;
    line-height:1.6;
}}

.btn {{
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    padding:16px;
    border-radius:16px;
    margin-top:16px;
    text-decoration:none;
    font-weight:700;
    font-size:16px;
}}

.btn-red {{
    background:linear-gradient(135deg,#ef4444,#dc2626);
    color:white;
}}

.btn-blue {{
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    color:white;
}}

.pin-box {{
    margin-top:25px;
}}

input {{
    width:100%;
    box-sizing:border-box;
    padding:15px;
    border:none;
    outline:none;
    border-radius:16px;
    background:rgba(255,255,255,.1);
    color:white;
    margin-bottom:14px;
    font-size:16px;
}}

input::placeholder {{
    color:#cbd5e1;
}}

.unlock-btn {{
    width:100%;
    padding:15px;
    border:none;
    border-radius:16px;
    background:linear-gradient(135deg,#22c55e,#06b6d4);
    color:white;
    font-weight:bold;
    font-size:16px;
    cursor:pointer;
}}

.footer {{
    margin-top:25px;
    text-align:center;
    color:#94a3b8;
    font-size:12px;
}}

</style>
</head>

<body>

<div class="page">

<div class="card">

<div class="badge">
EmpowerBands Emergency Profile
</div>

<h1>{name}</h1>

<div class="info">
{age_group} • ID: {band_id}
</div>

<div class="alert-box">
⚠️ <strong>{condition}</strong>
</div>

<div class="section">
<div class="section-title">
WHAT TO DO
</div>

<div class="section-text">
{instructions}
</div>
</div>

<div class="section">
<div class="section-title">
MEDICAL NOTES
</div>

<div class="section-text">
Protected — enter PIN to view
</div>
</div>

<a class="btn btn-red" href="/customer/{band_id}?confirm_alert=yes">
🚨 Activate Emergency Alert
</a>

<a class="btn btn-blue" href="tel:{phone.split(',')[0].strip()}">
📞 Call Emergency Contact
</a>

<a class="btn secondary" href="linktr.ee/EmpowerBandsWorldwide">
    🔗 More EmpowerBands Links
</a>



<div class="pin-box">

<form method="GET" action="/customer/{band_id}">

<input
type="password"
name="pin"
placeholder="Enter PIN to unlock full info"
required
>

<button class="unlock-btn" type="submit">
Unlock Full Info
</button>

</form>

</div>

<div class="footer">
EmpowerBands Emergency Response System
</div>

</div>

</div>

</body>
</html>
"""


    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/admin">Admin Login</a></p>
    """

# ===============================
# GPS ALERT ROUTE
# ===============================

@app.route("/alert_with_location")
def alert_with_location():
    band_id = request.args.get("band_id", "").strip().upper()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) >= 9 and row[0].strip().upper() == band_id:
                name = row[1]
                phones = row[3]
                location_link = f"https://maps.google.com/?q={lat},{lon}"

                if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

                    for phone in phones.split(","):
                        phone = phone.strip()
                        if phone:
                            client.messages.create(
                                body=(
                                    f"🚨 EmpowerBands Alert: {name} may need help.\n"
                                    f"📍 Location: {location_link}\n"
                                    f"Profile: {BASE_URL}/customer/{band_id}"
                                ),
                                from_=TWILIO_PHONE_NUMBER,
                                to=phone
                            )

                return f"""
                <h1>✅ Alert Sent</h1>
                <p>Location and profile were sent to emergency contact(s).</p>
                <p><a href="/customer/{band_id}">Go Back</a></p>
                """

    return "<h1>Error sending alert</h1>"


# ===============================
# APP MANIFEST
# ===============================

@app.route("/manifest.json")
def manifest():
    return {
        "name": "EmpowerBands",
        "short_name": "EmpowerBands",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0a58ca",
        "icons": [
            {
                "src": LOGO_URL,
                "sizes": "192x192",
                "type": "image/png"
            }
        ]
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
