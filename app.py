from flask import Flask, request, redirect, session
from twilio.rest import Client
import csv
import os
import time
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

LOGO_URL = "https://i.imgur.com/dE4kSOz.png"


# ===============================
# CREATE FILES
# ===============================

header = [
    "band_id",
    "name",
    "email",
    "phone",
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
    "+19382655364,+12566121274",
    "Child",
    "Autism – Nonverbal",
    "Please stay calm. I may not respond verbally. Call emergency contacts immediately.",
    "No allergies",
    "1234",
    "123 Hope Street, Decatur AL 35601",
    "Black / African American",
    "Male",
    "https://i.imgur.com/dE4kSOz.png"
])

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


def send_alert_text(name, phones, band_id):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        print("Twilio not configured.")
        return False

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    message = (
        f"🚨 EmpowerBands Alert: {name}'s band was scanned in ALERT MODE. "
        f"They may be lost, confused, or unable to communicate. "
        f"Profile: {BASE_URL}/{band_id}"
    )

    phone_list = [p.strip() for p in phones.split(",") if p.strip()]

    success = False

    for phone in phone_list:
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=phone
            )
            print(f"Alert sent to {phone}")
            success = True

        except Exception as e:
            print(f"SMS failed for {phone}: {e}")

    return success

def send_email_alert(name, email, band_id):

    sender_email = os.environ.get("ALERT_EMAIL")
    sender_password = os.environ.get("ALERT_EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        print("Email credentials missing")
        return False

    subject = f"🚨 EmpowerBands Emergency Alert for {name}"

    body = f"""
EmpowerBands Emergency Alert

{name}'s emergency profile was accessed.

Profile:
{BASE_URL}/{band_id}

This person may need assistance.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()

        print("Email alert sent")
        return True

    except Exception as e:
        print("Email error:", e)
        return False




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
            
            <div class="card">
    <h3>SMS Alert Consent</h3>
    <p>
        By registering or activating an EmpowerBand, users and guardians consent
        to receive SMS emergency alerts, safety notifications, and location-sharing
        messages related to emergency events and authorized safety responses.
    </p>
    <p>
        Message and data rates may apply. Reply STOP to opt out.
    </p>
</div>

<div class="card">
    <h3>About EmpowerBands</h3>

    <p>
        EmpowerBands provides NFC-enabled wearable safety bands designed to help
        schools, families, caregivers, and emergency responders access important
        support information quickly.
    </p>

    <p>
        Each band can connect to a secure emergency profile with instructions,
        medical notes, emergency contacts, and alert options.
    </p>
</div>
<div class="card">

    <h3>Contact & Support</h3>

    <p>
        EmpowerBands Worldwide
    </p>

    <p>
        Support Email:
        support@empowerbands.org
    </p>

    <p>
        Website:
        https://empowerbands.org
    </p>

    <p>
        School safety • Emergency response • NFC wearable technology
    </p>

</div>

<div class="card">

    <h3>How EmpowerBands Works</h3>

    <div class="item">1️⃣ Tap the EmpowerBand with a smartphone</div>

    <div class="item">
        2️⃣ View emergency instructions and support information instantly
    </div>

    <div class="item">
        3️⃣ Contact caregivers or activate emergency alerts with location sharing
    </div>

    <div class="card">

    <h3>Built For Schools & Student Safety</h3>

    <p>
        EmpowerBands supports schools, special education programs,
        athletics, field trips, and student safety initiatives by
        helping staff and emergency contacts respond faster during
        emergencies or medical situations.
    </p>

    <p>
        Designed to support communication, safety awareness,
        and rapid emergency response.
    </p>

</div>

</div>

            <a class="btn" href="/EB001">View Live Demo</a>
            <a class="btn dark" href="/admin">Admin Login</a>

            <div class="card">
                <div class="item">🔵 Tap band with phone</div>
                <div class="item">🔵 View instructions instantly</div>
                <div class="item">🔵 Call caregiver fast</div>
                <div class="item">🔵 Send emergency alert + location</div>
            </div>

            <div class="card">

    <h3>Privacy & Terms</h3>

    <p>
        EmpowerBands only uses contact and profile information to support
        emergency response, caregiver communication, and safety alerts.
    </p>

    <p>
        SMS alerts are only sent for emergency-related notifications connected
        to an activated EmpowerBand profile.
    </p>

    <p>
        <a href="/privacy" style="color:#0a58ca;font-weight:bold;">
            Privacy Policy
        </a>
        |
        <a href="/terms" style="color:#0a58ca;font-weight:bold;">
            Terms of Service
        </a>
    </p>

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
    "delete-request"
]

    if band_id.lower() in blocked_routes:
        return redirect("/")

    return profile(band_id.upper())
# ===============================
# ADMIN LOGIN
# ===============================

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if request.method == "POST":

        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")

        return """
        <h2 style='color:white;text-align:center;margin-top:100px;'>
        Wrong Password
        </h2>

        <p style='text-align:center;'>
        <a href='/admin'>Try Again</a>
        </p>
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

<footer style="text-align:center; padding:20px; font-size:13px; opacity:0.8;">
    <p>
        <a href="/privacy">Privacy Policy</a> |
        <a href="/terms">Terms of Service</a> |
        <a href="/delete-request">Data Deletion Request</a>
    </p>

    <p>
        EmpowerBands is not a replacement for 911, EMS, or professional medical monitoring.
    </p>
</footer>

</div>

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

    try:
        with open(file_name, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                customers.append(row)

    except:
        customers = []

    customer_cards = ""

    for customer in customers:

        band_id = customer.get("band_id", "")
        name = customer.get("name", "")
        email = customer.get("email", "")
        phone = customer.get("phone", "")

        customer_cards += f"""

        <div class="customer-card">

            <div class="top-row">
                <div>
                    <div class="band-id">{band_id}</div>
                    <div class="customer-name">{name}</div>
                </div>

                <div class="status">
                    ACTIVE
                </div>
            </div>

            <div class="info">
                📧 {email}
            </div>

            <div class="info">
                📱 {phone}
            </div>

            <div class="actions">

                <a class="btn view"
                   href="/customer/{band_id}">
                   View Profile
                </a>

                <a class="btn edit"
   href="/edit/{band_id}">
   Edit Profile
</a>

            </div>

        </div>

        """

    return f"""
<!DOCTYPE html>
<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>EmpowerBands Dashboard</title>

<style>

body{{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);
    min-height:100vh;
    color:white;
}}

.page{{
    padding:25px;
}}

.topbar{{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:25px;
}}

.logo{{
    font-size:32px;
    font-weight:800;
}}

.logo span{{
    color:#38bdf8;
}}

.add-btn{{
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    padding:14px 20px;
    border-radius:16px;
    color:white;
    text-decoration:none;
    font-weight:700;
}}

.stats{{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:18px;
    margin-bottom:25px;
}}

.stat-card{{
    background:rgba(255,255,255,0.08);
    border:1px solid rgba(255,255,255,0.12);
    backdrop-filter:blur(20px);
    border-radius:24px;
    padding:22px;
}}

.stat-number{{
    font-size:34px;
    font-weight:800;
}}

.stat-label{{
    color:#cbd5e1;
    margin-top:5px;
}}

.customer-card{{
    background:rgba(255,255,255,0.08);
    border:1px solid rgba(255,255,255,0.12);
    backdrop-filter:blur(20px);
    border-radius:24px;
    padding:22px;
    margin-bottom:18px;
}}

.top-row{{
    display:flex;
    justify-content:space-between;
    align-items:center;
}}

.band-id{{
    color:#38bdf8;
    font-size:14px;
    font-weight:700;
}}

.customer-name{{
    font-size:24px;
    font-weight:700;
    margin-top:4px;
}}

.status{{
    background:#16a34a;
    padding:8px 14px;
    border-radius:999px;
    font-size:13px;
    font-weight:700;
}}

.info{{
    margin-top:14px;
    color:#dbeafe;
}}

.actions{{
    margin-top:20px;
}}

.btn{{
    display:inline-block;
    padding:12px 18px;
    border-radius:14px;
    text-decoration:none;
    color:white;
    font-weight:700;
}}

.view{{
    background:#2563eb;
}}

.empty{{
    text-align:center;
    padding:80px 20px;
    color:#94a3b8;
}}

.edit{{
    background:#0f766e;
    margin-left:8px;
}}

</style>

</head>

<body>

<div class="page">

    <div class="topbar">

        <div class="logo">
            Empower<span>Bands</span>
        </div>

        <a class="add-btn" href="/add">
            + Add Band
        </a>

        <a class="add-btn" href="/scans">
            📡 View Scans
        </a>

    </div>

    <div class="stats">

        <div class="stat-card">
            <div class="stat-number">
                {len(customers)}
            </div>

            <div class="stat-label">
                Active Bands
            </div>
        </div>

    </div>

    {customer_cards if customer_cards else '<div class="empty">No bands added yet.</div>'}

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
        # save profile
        
        row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip(),
            request.form["pin"].strip(),
            request.form["address"].strip(),
            request.form["race"].strip(),
            request.form["gender"].strip(),
            request.form["photo_url"].strip()
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        print(f"PROFILE SAVED: {row[0]}")

        return redirect("/" + row[0])

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




.band-row{
    display:flex;
    gap:12px;
    margin-bottom:16px;
}

.band-row input{
    flex:2;
    min-width:0;
}

.generate-btn{
    width:auto;
    min-width:140px;
    border:none;
    border-radius:16px;
    padding:0 18px;
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    color:white;
    font-weight:700;
    cursor:pointer;
}

@media(max-width:480px){
    .band-row{
        flex-direction:column;
    }

    .generate-btn{
        width:100%;
        padding:16px;
    }
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

<div class="band-row">

<input
type="text"
id="band_id"
name="band_id"
placeholder="Band ID"
required
>

<button
type="button"
class="generate-btn"
onclick="generateBandId()"
>
Generate
</button>

</div>

<input name="name" placeholder="Full Name" required>

<input name="email" placeholder="Email">

<input name="phone" placeholder="Emergency Contacts (comma separated)" required>

<input name="age_group" placeholder="Child / Adult / Senior">

<input name="condition" placeholder="Public condition example: Autism - Nonverbal">

<textarea name="instructions" placeholder="Public instructions"></textarea>

<textarea name="medical_notes" placeholder="Private medical notes"></textarea>

<input name="pin" placeholder="PIN example: 1234" required>
<p style="font-size:12px; opacity:0.8;">
    By providing a phone number, you consent to receive emergency SMS alerts from EmpowerBands.
    Message and data rates may apply. Message frequency varies. Reply STOP to opt out.
</p>

<input name="address" placeholder="Address">

<input name="race" placeholder="Race">

<input name="gender" placeholder="Gender">

<input name="photo_url" placeholder="Photo URL">

<label style="display:block; margin-top:15px; font-size:13px;">
    <input type="checkbox" name="agree_terms" required>
    I agree to the Privacy Policy and Terms of Service.
</label>

<label style="display:block; margin-top:10px; font-size:13px;">
    <input type="checkbox" name="sms_consent" required>
    I consent to receive emergency SMS alerts from EmpowerBands.
</label>
<button type="submit">
Save Profile
</button>

</form>

<div class="footer">
EmpowerBands Admin System
</div>

</div>

</div>

<script>

function generateBandId(){

    const randomNumber =
        Math.floor(1000 + Math.random() * 9000);

    document.getElementById("band_id").value =
        "EB" + randomNumber;
}

</script>
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

    header = rows[0]
    data_rows = rows[1:]

    found_row = None

    for row in data_rows:
        if row[0].strip().upper() == band_id:
            while len(row) < 13:
                row.append("")
            found_row = row
            break

    if not found_row:
        return "<h1>Profile not found</h1><p><a href='/dashboard'>Back to Dashboard</a></p>"

    if request.method == "POST":

        updated_row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip(),
            request.form["pin"].strip(),
            request.form["address"].strip(),
            request.form["race"].strip(),
            request.form["gender"].strip(),
            request.form["photo_url"].strip()
        ]

        new_rows = [header]

        for row in data_rows:
            if row[0].strip().upper() == band_id:
                new_rows.append(updated_row)
            else:
                new_rows.append(row)

        with open(file_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)

        return redirect("/dashboard")

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Edit EmpowerBand Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
body{{
    margin:0;
    font-family:Arial,sans-serif;
    background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);
    min-height:100vh;
    color:white;
}}

.page{{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
}}

.card{{
    width:100%;
    max-width:560px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:30px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}}

h1{{
    text-align:center;
}}

input, textarea{{
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

textarea{{
    min-height:90px;
}}

button{{
    width:100%;
    padding:16px;
    border:none;
    border-radius:16px;
    background:linear-gradient(135deg,#22c55e,#06b6d4);
    color:white;
    font-weight:bold;
    font-size:17px;
}}

.back{{
    display:block;
    text-align:center;
    margin-top:15px;
    color:#7dd3fc;
}}
</style>
</head>

<body>
<div class="page">
<div class="card">

<h1>Edit Profile</h1>

<form method="POST">

<input name="band_id" value="{found_row[0]}" required>
<input name="name" value="{found_row[1]}" required>
<input name="email" value="{found_row[2]}">
<input name="phone" value="{found_row[3]}" required>
<input name="age_group" value="{found_row[4]}">
<input name="condition" value="{found_row[5]}">

<textarea name="instructions">{found_row[6]}</textarea>
<textarea name="medical_notes">{found_row[7]}</textarea>

<input name="pin" value="{found_row[8]}" required>
<input name="address" value="{found_row[9]}">
<input name="race" value="{found_row[10]}">
<input name="gender" value="{found_row[11]}">
<input name="photo_url" value="{found_row[12]}" placeholder="Photo URL">

<button type="submit">Save Changes</button>

</form>

<a class="back" href="/dashboard">Back to Dashboard</a>

</div>
</div>
</body>
</html>
"""


# ===============================
# BAND PROFILE
# ===============================

@app.route("/customer/<band_id>")
def profile(band_id):
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
                address = row[9] if len(row) > 9 else ""
                race = row[10] if len(row) > 10 else ""
                gender = row[11] if len(row) > 11 else ""
                photo_url = row[12] if len(row) > 12 else ""

                visitor_ip = request.remote_addr
                log_scan(
                    band_id,
                    name,
                    "PROFILE_VIEW",
                    visitor_ip
                )

    

                entered_pin = request.args.get("pin")
                if alert_mode:
                    success = send_alert_text(name, phone, band_id)
                    email_success = send_email_alert(name, email, band_id)

                    if success or email_success:
                        return f"""
                        <h1>✅ Alert Sent</h1>
                        <p>Emergency contact(s) have been notified.</p>
                        <p><a href="/{band_id}">Go Back</a></p>
                        """
                    else:
                        return f"""
                        <h1>❌ Alert Failed</h1>
                        <p>There was a problem sending the alert.</p>
                        <p><a href="/{band_id}">Go Back</a></p>
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

                            <a href="/{band_id}" style="display:block;margin-top:12px;padding:15px;border-radius:10px;background:#111827;color:white;text-decoration:none;font-weight:bold;">
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
                                    window.location.href = "/{band_id}?alert=yes";
                                }});
                            }} else {{
                                window.location.href = "/{band_id}?alert=yes";
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

a[href^="tel"] {{
    color:white;
    text-decoration:none;
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
<div class="section">
<div class="section-title">
ADDRESS
</div>

<div class="section-text">
{address}
</div>
</div>

<div class="section">
<div class="section-title">
RACE
</div>

<div class="section-text">
{race}
</div>
</div>

<div class="section">
<div class="section-title">
GENDER
</div>

<div class="section-text">
{gender}
</div>
</div>


<a class="btn btn-blue" href="tel:{phone.split(',')[0].strip()}">
📞 Call Emergency Contact
</a> 

<a class="btn btn-red" href="/{band_id}?confirm_alert=yes">
    🚨 Send Alert
</a>
<p style="font-size:12px; color:#ffcccc; margin-top:10px;">
    EmpowerBands is not 911. In a life-threatening emergency, call 911 immediately.
</p>

<a class="btn btn-dark" href="/{band_id}">
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

a[href^="tel"] {{ 
    color:white;
    text-decoration:none;
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

<img
src="{photo_url}"
style="
width:120px;
height:120px;
border-radius:50%;
object-fit:cover;
border:4px solid rgba(255,255,255,.15);
margin-bottom:20px;
"
>

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

<a class="btn btn-red" href="/{band_id}?confirm_alert=yes">
🚨 Activate Emergency Alert
</a>

<a class="btn btn-blue" href="tel:{phone.split(',')[0].strip()}">
📞 Call Emergency Contact
</a>
<a class="btn btn-dark" href="/pro">
    🔒 Explore EmpowerBands Pro
</a>



<div class="pin-box">

<form method="GET" action="/{band_id}">

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

<footer style="text-align:center; padding:20px; font-size:13px; opacity:0.8;">
    <p>
        <a href="/privacy">Privacy Policy</a> |
        <a href="/terms">Terms of Service</a> |
        <a href="/delete-request">Data Deletion Request</a>
    </p>

    <p>
        EmpowerBands is not a replacement for 911, EMS, or professional medical monitoring.
    </p>
</footer>

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
# SCAN LOGS PAGE
# ===============================

@app.route("/scans")
def scans():

    if not session.get("logged_in"):
        return redirect("/admin")

    scans = []

    try:

        with open(scan_log_file, "r", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:
                scans.append(row)

        scans.reverse()

    except:
        scans = []

    rows_html = ""

    for scan in scans:

        rows_html += f"""

        <tr>
            <td>{scan.get("BandID","")}</td>
            <td>{scan.get("Name","")}</td>
            <td>{scan.get("Time","")}</td>
            <td>{scan.get("Type","")}</td>
            <td>{scan.get("IP","")}</td>
        </tr>

        """

    return f"""
<!DOCTYPE html>
<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Scan Logs</title>

<style>

body{{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);
    color:white;
    min-height:100vh;
}}

.page{{
    padding:25px;
}}

h1{{
    font-size:34px;
    margin-bottom:20px;
}}

.top-btn{{
    display:inline-block;
    margin-bottom:20px;
    padding:14px 18px;
    border-radius:14px;
    background:#2563eb;
    color:white;
    text-decoration:none;
    font-weight:bold;
}}

.table-wrap{{
    overflow-x:auto;
    background:rgba(255,255,255,0.08);
    border-radius:24px;
    padding:20px;
    border:1px solid rgba(255,255,255,0.12);
}}

table{{
    width:100%;
    border-collapse:collapse;
}}

th{{
    text-align:left;
    padding:14px;
    color:#7dd3fc;
    border-bottom:1px solid rgba(255,255,255,0.1);
}}

td{{
    padding:14px;
    border-bottom:1px solid rgba(255,255,255,0.06);
    color:#e5e7eb;
}}

.empty{{
    text-align:center;
    padding:40px;
    color:#94a3b8;
}}

</style>

</head>

<body>

<div class="page">

<h1>📡 Scan Logs</h1>

<a class="top-btn" href="/dashboard">
⬅ Back To Dashboard
</a>

<div class="table-wrap">

<table>

<tr>
    <th>Band ID</th>
    <th>Name</th>
    <th>Time</th>
    <th>Type</th>
    <th>IP</th>
</tr>

{rows_html if rows_html else '<tr><td colspan="5" class="empty">No scans yet</td></tr>'}

</table>

</div>

</div>

</body>
</html>
"""

# ===============================
# PRO PAGE
# ===============================

@app.route("/pro")
def pro():
    return """
    <html>
    <head>
        <title>EmpowerBands Pro</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>

    <body style="
        background:#07111f;
        color:white;
        font-family:Arial;
        text-align:center;
        padding:60px;
    ">

        <h1>🔒 EmpowerBands Pro</h1>

        <p>
        Premium tools for advanced profiles,
        business networking, analytics,
        custom branding, and premium support.
        </p>

        <br>

        <a href="/" style="
            display:inline-block;
            padding:14px 24px;
            background:#0a58ca;
            color:white;
            text-decoration:none;
            border-radius:14px;
            font-weight:bold;
        ">
            ⬅ Go Back
        </a>

    </body>
    </html>
    """

# ===============================
# GPS ALERT ROUTE
# ===============================    

@app.route("/alert_with_location")
def alert_with_location():

    band_id = request.args.get("band_id", "").strip().upper()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    maps_link = f"https://maps.google.com/?q={lat},{lon}"

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if row[0].strip().upper() == band_id:

                name = row[1]
                email = row[2]
                phone = row[3]

                sms_success = send_alert_text(name, phone, band_id)
                email_success = send_email_alert(name, email, band_id)

                print("SMS success:", sms_success)
                print("Email success:", email_success)

                return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Alert Sent</title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f3f4f6;
            text-align: center;
            padding: 40px;
        }}

        .card {{
            background: white;
            padding: 30px;
            border-radius: 18px;
            max-width: 500px;
            margin: auto;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}

        .home-btn {{
            display:inline-block;
            margin-top:20px;
            padding:14px 24px;
            background:#111827;
            color:white;
            text-decoration:none;
            border-radius:12px;
            font-weight:bold;
            box-shadow:0 4px 12px rgba(0,0,0,0.25);
            transition:0.3s;
        }}

        .home-btn:hover {{
            transform:translateY(-2px);
            background:#1f2937;
        }}
    </style>
</head>

<body>
    <div class="card">
        <h1>✅ Alert Sent</h1>
        <p>Emergency contacts have been notified.</p>

        <a href="/" class="home-btn">🏠 Return Home</a>
    </div>
</body>
</html>
"""

    return "<h1>Band not found</h1>"


# ===============================
# APP MANIFEST
# ===============================

@app.route("/manifest.json")
def manifest():
    return { 
        "name": "EmpowerBands Worldwide",
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
                
# ===============================
# PRIVACY POLICY
# ===============================

@app.route("/privacy")
def privacy():
    return """
    <html>
    <head>
        <title>EmpowerBands Privacy Policy</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>

    <body style="font-family:Arial; padding:30px; background:#07111f; color:white; line-height:1.6;">

        <h1>Privacy Policy</h1>

        <p>
        EmpowerBands collects limited profile information to support emergency response,
        caregiver communication, and safety alerts.
        </p>

        <p>
        Information may include name, emergency contacts, medical notes, instructions,
        and optional profile details entered by the user, guardian, school, or caregiver.
        </p>

        <p>
        SMS alerts are used only for emergency-related notifications connected to an
        activated EmpowerBand profile. Message and data rates may apply. Reply STOP to opt out.
        </p>

        <p>
        EmpowerBands does not sell personal information.
        </p>

        <p>
        Contact: support@empowerbands.org
        </p>

        

        <a href="/" style="color:#7dd3fc;">Back to Home</a>

    </body>
    </html>
    """


@app.route("/terms")
def terms():
    return """
    <h1>Terms of Service</h1>
    <p>EmpowerBands is a supplemental safety and communication tool.</p>
    <p>EmpowerBands is not a replacement for 911, emergency medical services, law enforcement, or professional healthcare monitoring.</p>
    <p>Users are responsible for keeping their emergency profile information accurate and updated.</p>
    <p>By using EmpowerBands, users agree to receive emergency-related communication when their band or profile is activated.</p>
    <p><a href="/">Back Home</a></p>
    """

@app.route("/delete-request")
def delete_request():
    return """
    <h1>Data Deletion Request</h1>
    <p>To request removal of your EmpowerBands profile, emergency contact information, scan logs, or related data, contact EmpowerBands support.</p>
    <p>Email: support@empowerbands.org</p>
    <p>Please include your Band ID so we can locate your profile.</p>
    <p><a href="/">Back Home</a></p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
