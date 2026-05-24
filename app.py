from flask import Flask, request, redirect, session
from werkzeug.utils import secure_filename
from twilio.rest import Client
import csv
import os
import time
import smtplib
from email.mime.text import MIMEText
import qrcode
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

ALERT_EMAILS = os.environ.get("ALERT_EMAILS", "")
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
    "Autism — Nonverbal",
    "Please stay calm. I may not respond verbally.",
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


def send_alert_text(name, phones, band_id, maps_link=None):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        print("Twilio not configured.")
        return False

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    location_text = f"\nLocation: {maps_link}" if maps_link else ""

    message = (
        f"🚨 EmpowerBands Alert: {name}'s band was scanned in ALERT MODE. "
        f"They may be lost, confused, or unable to communicate. "
        f"Profile: {BASE_URL}/{band_id}"
        f"{location_text}"
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


def send_email_alert(name, email, band_id, maps_link=None):
    sender_email = os.environ.get("ALERT_EMAIL")
    sender_password = os.environ.get("ALERT_EMAIL_PASSWORD")

    email_list = [e.strip() for e in ALERT_EMAILS.split(",") if e.strip()]

    if not sender_email or not sender_password:
        print("Email credentials missing")
        return False

    if not email_list:
        print("No recipient emails configured")
        return False

    maps_url = maps_link if maps_link else "Not available"

    subject = f"🚨 EmpowerBands Emergency Alert for {name}"

    body = f"""
🚨 EmpowerBands Alert

{name}'s emergency profile was accessed.

Profile:
{BASE_URL}/{band_id}

Location:
{maps_url}

This person may need assistance.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(email_list)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        server.login(sender_email, sender_password)

        server.sendmail(
            sender_email,
            email_list,
            msg.as_string()
        )

        server.quit()

        print("Email alert sent")
        return True

    except Exception as e:
        print(f"Email failed: {e}")
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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmpowerBands Worldwide</title>

<style>
body{
    margin:0;
    font-family:Arial,sans-serif;
    background:#020817;
    color:white;
}

.header{
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:18px 6%;
    border-bottom:1px solid rgba(255,255,255,0.1);
    background:#020817;
}

.logo-wrap{
    display:flex;
    align-items:center;
    gap:14px;
}

.logo-wrap img{
    width:70px;
    height:70px;
    border-radius:50%;
    object-fit:cover;
    box-shadow:0 0 25px rgba(14,165,233,0.8);
}

.logo-text{
    font-size:24px;
    font-weight:900;
}

.logo-text span{
    display:block;
    color:#38bdf8;
    font-size:16px;
}

.nav{
    display:flex;
    gap:28px;
    align-items:center;
}

.nav a{
    color:white;
    text-decoration:none;
    font-weight:bold;
}

.nav .active{
    color:#38bdf8;
    border-bottom:2px solid #38bdf8;
    padding-bottom:8px;
}

.top-buttons{
    display:flex;
    gap:12px;
}

.btn{
    display:inline-block;
    padding:14px 22px;
    border-radius:10px;
    text-decoration:none;
    color:white;
    font-weight:800;
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    box-shadow:0 0 25px rgba(37,99,235,0.4);
}

.btn.dark{
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.25);
    box-shadow:none;
}

.hero{
    padding:60px 6% 35px;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:35px;
    align-items:center;
    background:
        radial-gradient(circle at right,#0b4cff 0%,rgba(2,8,23,0.8) 35%,#020817 75%);
}

.hero h1{
    font-size:66px;
    line-height:1.05;
    margin:0;
}

.hero h1 span{
    display:block;
    background:linear-gradient(135deg,#06b6d4,#4f46e5);
    -webkit-background-clip:text;
    color:transparent;
}

.hero h3{
    color:#0ea5e9;
    font-size:24px;
    margin-bottom:12px;
}

.hero p{
    color:#dbeafe;
    line-height:1.6;
    max-width:620px;
}

.hero-logo{
    width:100%;
    max-width:520px;
    display:block;
    margin-bottom:25px;
    filter:drop-shadow(0 0 18px rgba(14,165,233,0.6));
}

.hero-visual{
    text-align:center;
}

.hero-visual img{
    width:100%;
    max-width:460px;
    border-radius:30px;
    filter:drop-shadow(0 0 45px rgba(37,99,235,0.8));
}

.trust{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
    gap:14px;
    margin-top:28px;
}

.trust-card{
    border:1px solid rgba(56,189,248,0.25);
    border-radius:10px;
    padding:14px;
    background:rgba(255,255,255,0.04);
}

.section{
    padding:30px 6%;
}

.section h2{
    text-align:center;
    font-size:34px;
    margin-bottom:22px;
}

.grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
    gap:18px;
}

.card{
    background:rgba(255,255,255,0.04);
    border:1px solid rgba(56,189,248,0.25);
    border-radius:16px;
    padding:24px;
    text-align:center;
    box-shadow:0 0 25px rgba(37,99,235,0.15);
}

.card .num{
    width:45px;
    height:45px;
    border-radius:50%;
    background:#2563eb;
    display:flex;
    align-items:center;
    justify-content:center;
    margin:0 auto 14px;
    font-weight:900;
    box-shadow:0 0 20px rgba(37,99,235,0.8);
}

.card h3{
    margin:8px 0;
}

.card p{
    color:#cbd5e1;
    line-height:1.5;
}

.cta{
    margin:30px 6%;
    padding:28px;
    border-radius:18px;
    border:1px solid #2563eb;
    box-shadow:0 0 35px rgba(37,99,235,0.4);
    display:grid;
    grid-template-columns:100px 1fr 1.3fr;
    gap:25px;
    align-items:center;
}

.cta img{
    width:85px;
    height:85px;
    border-radius:50%;
    box-shadow:0 0 30px rgba(14,165,233,0.8);
}

.cta-buttons{
    display:flex;
    gap:14px;
    flex-wrap:wrap;
    justify-content:flex-end;
}

.footer{
    padding:30px 6%;
    border-top:1px solid rgba(255,255,255,0.1);
    color:#94a3b8;
    display:flex;
    justify-content:space-between;
    gap:20px;
    flex-wrap:wrap;
}

.footer a{
    color:#cbd5e1;
    text-decoration:none;
    margin:0 8px;
}

@media(max-width:850px){
    .header,.nav,.top-buttons{
        flex-direction:column;
        gap:16px;
    }

    .hero{
        grid-template-columns:1fr;
        text-align:center;
    }

    .hero h1{
        font-size:44px;
    }

    .hero-logo{
        margin:0 auto 25px;
    }

    .cta{
        grid-template-columns:1fr;
        text-align:center;
    }

    .cta img{
        margin:auto;
    }

    .cta-buttons{
        justify-content:center;
    }

    .btn{
        width:100%;
        box-sizing:border-box;
        text-align:center;
    }
}
</style>
</head>

<body>

<div class="header">
    <div class="logo-wrap">
        <img src="https://i.imgur.com/dE4kSOz.png">
        <div class="logo-text">
            EmpowerBands
            <span>Worldwide</span>
        </div>
    </div>

    <div class="nav">
        <a class="active" href="/">Home</a>
        <a href="#how">How It Works</a>
        <a href="#about">About Us</a>
        <a href="#mission">Mission</a>
        <a href="mailto:support@empowerbands.org">Contact</a>
    </div>

    <div class="top-buttons">
        <a class="btn" href="/EB001">🚀 View Demo</a>
        <a class="btn dark" href="/admin">🔒 Admin Login</a>
    </div>
</div>

<section class="hero">
    <div>
        <img class="hero-logo" src="https://i.imgur.com/RpBUbHd.png">

        <h1>EmpowerBands <span>Worldwide</span></h1>

        <h3>Smart Wearable Safety Technology</h3>

        <p>
            Smart NFC and QR wearable safety technology designed to help children,
            seniors, caregivers, schools, and individuals with disabilities communicate
            faster during emergencies.
        </p>

        <div style="margin-top:25px;">
            <a class="btn" href="/EB001">🚀 View Live Demo</a>
            <a class="btn dark" href="mailto:support@empowerbands.org">❤️ Support Our Mission</a>
            <a class="btn dark" href="mailto:support@empowerbands.org">🛡️ Partner With Us</a>
        </div>

        <div class="trust">
            <div class="trust-card">📡 NFC + QR Technology</div>
            <div class="trust-card">♿ Accessibility Focused</div>
            <div class="trust-card">❤️ Nonprofit Organization</div>
            <div class="trust-card">🏫 School & Caregiver Ready</div>
        </div>
    </div>

    <div class="hero-visual">
        <img src="https://i.imgur.com/dE4kSOz.png">
    </div>
</section>

<section class="section" id="how">
    <h2>How EmpowerBands Works</h2>

    <div class="grid">
        <div class="card">
            <div class="num">1</div>
            <h3>Tap The Band</h3>
            <p>A smartphone taps the NFC wearable or scans the QR code.</p>
        </div>

        <div class="card">
            <div class="num">2</div>
            <h3>View Emergency Profile</h3>
            <p>Important instructions, caregiver contacts, and support details appear instantly.</p>
        </div>

        <div class="card">
            <div class="num">3</div>
            <h3>Send Alerts Fast</h3>
            <p>Emergency contacts can receive alerts and GPS location sharing within seconds.</p>
        </div>

        <div class="card">
            <div class="num">4</div>
            <h3>Improve Safety</h3>
            <p>Supports schools, caregivers, seniors, disabilities, and emergency response situations.</p>
        </div>
    </div>
</section>

<section class="section" id="mission">
    <h2>Real-World Scenarios</h2>

    <div class="grid">
        <div class="card">
            <h3>👦 Child With Autism</h3>
            <p>A nonverbal child becomes separated. Staff scan the band and access caregiver instructions.</p>
        </div>

        <div class="card">
            <h3>👵 Senior With Dementia</h3>
            <p>A senior experiencing confusion can be identified and connected with family quickly.</p>
        </div>

        <div class="card">
            <h3>🏫 School Safety Support</h3>
            <p>Teachers and staff can access emergency instructions during medical or communication situations.</p>
        </div>

        <div class="card">
            <h3>♿ Accessibility Support</h3>
            <p>Individuals with visible or invisible disabilities can communicate support needs quickly.</p>
        </div>
    </div>
</section>

<section class="cta">
    <img src="https://i.imgur.com/dE4kSOz.png">

    <div>
        <h2>Ready To Support The Mission?</h2>
        <p>Partner with EmpowerBands Worldwide to help build safer, more accessible communities.</p>
    </div>

    <div class="cta-buttons">
        <a class="btn" href="mailto:support@empowerbands.org">❤️ Support The Mission</a>
        <a class="btn dark" href="mailto:support@empowerbands.org">🤝 Partner With Us</a>
        <a class="btn dark" href="/EB001">🚀 View Demo</a>
    </div>
</section>

<div class="footer">
    <div>
        <strong>EmpowerBands Worldwide</strong><br>
        One Tap. One Voice. One World.
    </div>

    <div>
        Decatur, Alabama<br>
        support@empowerbands.org
    </div>

    <div>
        <a href="/sms-opt-in">SMS Opt-In</a> |
        <a href="/privacy">Privacy Policy</a> |
        <a href="/terms">Terms of Service</a> |
        <a href="/delete-request">Data Deletion Request</a>
    </div>

    <div style="margin-top:12px;">
        Contact: support@empowerbands.org<br>
        Follow Us:
        <a href="https://linktr.ee/EmpowerBandsWorldwide">Linktree</a>
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
    "delete-request",
    "sms-opt-in"
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
def count_rows(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return max(0, sum(1 for row in f) - 1)
    except:
        return 0

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
        customers = []

    customer_cards = ""
    
    for customer in customers:

        band_id = customer.get("band_id", "")
        name = customer.get("name", "")
        email = customer.get("email", "")
        phone = customer.get("phone", "")

        customer_cards += f"""

        <div class="customer-card searchable">

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

    <a class="btn delete"
       href="/delete/{band_id}"
       onclick="return confirm('Delete this band permanently?')">
       Delete
    </a>

</div>
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
    gap:10px;
    flex-wrap:wrap;
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

.edit{{
    background:#0f766e;
    margin-left:8px;
}}

.delete{{
    background:#dc2626;
    margin-left:8px;
}} 
.empty{{ 
    text-align:center;
    padding:80px 20px;
    color:#94a3b8;
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

        <a class="add-btn" href="/">
            🏠 Home
</a>

</div>

<div style="margin-bottom:25px; max-width:700px; margin-left:auto; margin-right:auto;">

<input
type="text"
id="searchInput"
placeholder="🔍 Search by name, band ID, or phone..."
style="
width:100%;
padding:16px;
border:none;
border-radius:16px;
background:rgba(255,255,255,0.1);
color:white;
font-size:16px;
box-sizing:border-box;
outline:none;
"
onkeyup="filterBands()"
>

</div>

<div class="stats">

        <div class="stat-card">
            <div class="stat-number">{total_bands}</div>
            <div class="stat-label">Total Bands</div>
        </div>

        <div class="stat-card">
            <div class="stat-number">{total_scans}</div>
            <div class="stat-label">Total Scans</div>
        </div>

        <div class="stat-card">
            <div class="stat-number">{len(customers)}</div>
            <div class="stat-label">Active Bands</div>
        </div>

    </div>

    {customer_cards if customer_cards else '<div class="empty">No bands added yet.</div>'}

</div>

<script>
function filterBands(){{
    let input = document.getElementById("searchInput").value.toLowerCase();
    let cards = document.getElementsByClassName("searchable");

    for(let i = 0; i < cards.length; i++){{
        let text = cards[i].innerText.toLowerCase();

        if(text.includes(input)){{
            cards[i].style.display = "block";
        }}else{{
            cards[i].style.display = "none";
        }}
    }}
}}
</script>

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

        photo = request.files.get("photo")
        photo_url = ""

        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)
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

.form-label{
    display:block;
    margin-top:18px;
    margin-bottom:8px;
    color:white;
    font-size:15px;
    font-weight:600;
    letter-spacing:.4px;
}

.helper-text{
    display:block;
    margin-top:4px;
    color:rgba(255,255,255,0.65);
    font-size:12px;
    line-height:1.4;
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

<form method="POST" enctype="multipart/form-data">

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

<label class="form-label">Full Name *</label>

<input
type="text"
name="name"
placeholder="John Smith"
required
>

<input name="email" placeholder="Email">

<label class="form-label">
Emergency Contact Numbers *
</label>

<input
type="text"
name="phone"
placeholder="+12565551234,+12565559876"
inputmode="tel"
required
>

<small class="helper-text">
Separate multiple numbers with commas
</small>
<label class="form-label">
Emergency Contact Emails
</label>

<input
type="text"
name="emergency_emails"
placeholder="mom@email.com,dad@email.com"
>

<small class="helper-text">
Separate multiple emails with commas
</small>

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

<input type="file" name="photo">

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

async function generateBandId(){

    try{

        const response = await fetch("/next-band-id");

        const data = await response.text();

        document.getElementById("band_id").value = data;

    }catch(error){

        alert("Could not generate Band ID");
    }
}

</script>
</body>
</html>
"""
@app.route("/next-band-id")
def next_band_id():

    highest = 0

    try:

        with open(file_name, "r", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                band_id = row.get("band_id", "")

                if band_id.startswith("EB"):

                    try:
                        number = int(band_id.replace("EB", ""))

                        if number > highest:
                            highest = number

                    except:
                        pass

    except:
        pass

    next_id = highest + 1

    return f"EB{next_id:03d}"
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
            while len(row) < 15:
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

<input name="emergency_phones" value="{found_row[4]}" required>

<input name="emergency_emails" value="{found_row[4]}">

<input name="age_group" value="{found_row[5]}">

<input name="condition" value="{found_row[6]}">

<textarea name="instructions">{found_row[7]}</textarea>

<textarea name="medical_notes">{found_row[8]}</textarea>

<input name="pin" value="{found_row[9]}" required>

<input name="address" value="{found_row[10]}">

<input name="race" value="{found_row[11]}">

<input name="gender" value="{found_row[12]}">

<input name="photo_url" value="{found_row[13]}" placeholder="Photo URL">

<button type="submit">Save Changes</button>

</form>

<a class="back" href="/dashboard">Back to Dashboard</a>

</div>
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

    header = rows[0]
    data_rows = rows[1:]

    updated_rows = [header]

    for row in data_rows:
        if row[0].strip().upper() != band_id:
            updated_rows.append(row)

    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(updated_rows)

    return redirect("/dashboard")

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
                emergency_phones = row[4] if len(row) > 4 else ""
                emergency_emails = row[5] if len(row) > 5 else ""
                age_group = row[6] if len(row) > 6 else ""
                condition = row[7] if len(row) > 7 else ""
                instructions = row[8] if len(row) > 8 else ""
                medical_notes = row[9] if len(row) > 9 else ""
                pin = row[10] if len(row) > 10 and row[10] else "1234"
                address = row[11] if len(row) > 11 else ""
                race = row[12] if len(row) > 12 else ""
                gender = row[13] if len(row) > 13 else ""
                photo_url = row[14] if len(row) > 14 else ""


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

            window.location.href =
            "/alert_with_location?band_id={band_id}&lat=" + lat + "&lon=" + lon;

        }}, function(error){{
            alert("GPS permission was denied or unavailable. Please allow location access.");
            window.location.href = "/alert?band_id={band_id}";
        }});
    }} else {{
        alert("This phone/browser does not support GPS location.");
        window.location.href = "/alert?band_id={band_id}";
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
src="{photo_url if photo_url else LOGO_URL}"
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
<img src="/qr/{band_id}" style="width:180px; border-radius:14px; background:white; padding:10px; margin-top:20px;">

<p>Scan QR backup if NFC is unavailable.</p>

<a class="btn btn-blue" href="/qr/{band_id}" download="{band_id}-qr.png">
    ⬇️ Download QR Code
</a>

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

@app.route("/qr/<band_id>")
def qr_code(band_id):
    band_id = band_id.strip().upper()
    url = f"{BASE_URL}/{band_id}"

    img = qrcode.make(url)

    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return app.response_class(buffer.getvalue(), mimetype="image/png")

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

    if lat and lon:
        maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    else:
        maps_link = None

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if row[0].strip().upper() == band_id:

                name = row[1]
                email = row[2]
                phone = row[3]

                sms_success = send_alert_text(name, phone, band_id, maps_link)
                email_success = send_email_alert(name, email, band_id, maps_link)

                print("SMS success:", sms_success)
                print("Email success:", email_success)
                print("MAP LINK:", maps_link)

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

    return "Band ID not found", 404


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

@app.route("/sms-opt-in")
def sms_opt_in():
    return """
<!DOCTYPE html>
<html>
<head>
<title>EmpowerBands SMS Opt-In</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{
    margin:0;
    font-family:Arial,sans-serif;
    background:#0f172a;
    color:white;
    padding:30px;
}
.card{
    max-width:650px;
    margin:auto;
    background:rgba(255,255,255,0.08);
    padding:28px;
    border-radius:20px;
    border:1px solid rgba(255,255,255,0.18);
    box-shadow:0 10px 30px rgba(0,0,0,0.35);
}
input{
    width:100%;
    padding:14px;
    margin:10px 0;
    border-radius:10px;
    border:none;
    font-size:16px;
}
button{
    width:100%;
    padding:15px;
    border:none;
    border-radius:12px;
    background:#22c55e;
    color:white;
    font-size:17px;
    font-weight:bold;
}
a{color:#93c5fd;}
.small{
    font-size:14px;
    color:#cbd5e1;
    line-height:1.6;
}
</style>
</head>
<body>

<div class="card">
    <h1>EmpowerBands SMS Opt-In</h1>

    <p>
        Sign up to receive EmpowerBands text alerts, safety notifications,
        emergency assistance messages, and account-related updates.
    </p>

    <form>
        <input type="text" placeholder="Full Name" required>
        <input type="tel" placeholder="Phone Number" required>

        <label class="small">
            <input type="checkbox" required style="width:auto;">
            I agree to receive SMS/text messages from EmpowerBands Worldwide.
            Message frequency may vary. Message & data rates may apply.
            Reply STOP to opt out. Reply HELP for help.
        </label>

        <br><br>
        <button type="submit">Agree & Opt In</button>
    </form>

    <p class="small">
        By submitting this form, you consent to receive text messages from
        EmpowerBands Worldwide. Consent is not a condition of purchase.
    </p>

    <p class="small">
        Contact: support@empowerbands.org<br>
        Website: empowerbands.org
    </p>

    <p>
        <a href="/privacy">Privacy Policy</a> |
        <a href="/terms">Terms of Service</a>
    </p>
</div>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
