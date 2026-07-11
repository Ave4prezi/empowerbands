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
# HOME PAGE
# ===============================

@app.route("/")
def home():
    import urllib.request as _hw_ur, json as _hw_json

    # Visitor counter
    _vc_file = "visit_count.txt"
    try:
        _vc = int(open(_vc_file).read().strip()) if os.path.exists(_vc_file) else 0
        _vc += 1
        open(_vc_file, "w").write(str(_vc))
        visit_count = f"{_vc:,}"
    except:
        visit_count = "—"

    spotlight_html = ""
    try:
        import json as _sp_json
        with open("family_spotlight.json", "r") as _sp_f:
            _sp = _sp_json.load(_sp_f)
        if _sp.get("active") and _sp.get("story"):
            _sp_photo = _sp.get("photo_url") or LOGO_URL
            _sp_month = _sp.get("month", "")
            spotlight_html = f"""<div style="
                background:linear-gradient(135deg,rgba(34,197,94,0.14),rgba(14,165,233,0.12));
                border:1px solid rgba(134,239,172,0.3);
                border-radius:20px;
                padding:26px;
                margin:24px auto;
                max-width:680px;
                text-align:center;
                font-family:Arial,sans-serif;
                color:white;
            ">
                <div style="font-size:13px;font-weight:700;letter-spacing:.05em;color:#86efac;text-transform:uppercase;margin-bottom:10px;">
                    💚 {_sp_month} Family We're Blessing
                </div>
                <img src="{_sp_photo}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,.2);margin-bottom:14px;">
                <p style="font-size:15px;line-height:1.7;color:#e5e7eb;max-width:560px;margin:0 auto;">
                    {_sp.get("story","")}
                </p>
                <a href="/donate" style="display:inline-block;margin-top:16px;padding:12px 24px;border-radius:12px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;text-decoration:none;font-weight:700;">
                    ❤️ Help Bless Next Month's Family
                </a>
            </div>"""
    except:
        spotlight_html = ""

    whats_new_html = ""
    try:
        _hw_req = _hw_ur.Request(
            "https://api.github.com/repos/Ave4prezi/Empowerbands/commits?per_page=1",
            headers={"Authorization": f"token {os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN','')}",
                     "Accept": "application/vnd.github.v3+json", "User-Agent": "EmpowerBands-App"}
        )
        with _hw_ur.urlopen(_hw_req, timeout=5) as _hw_r:
            _hw_commits = _hw_json.loads(_hw_r.read().decode())
        if _hw_commits:
            _hw_c = _hw_commits[0]
            _hw_msg = _hw_c.get("commit",{}).get("message","").split("\n")[0]
            _hw_date = _hw_c.get("commit",{}).get("author",{}).get("date","")[:10]
            _hw_url = _hw_c.get("html_url","#")
            whats_new_html = f"""<div style="
                background:linear-gradient(135deg,rgba(14,165,233,0.18),rgba(37,99,235,0.14));
                border:1px solid rgba(103,232,249,0.25);
                border-radius:14px;
                padding:14px 20px;
                margin:20px auto;
                max-width:680px;
                display:flex;
                align-items:center;
                gap:12px;
                font-family:Arial,sans-serif;
                font-size:13px;
                color:#e5e7eb;
                flex-wrap:wrap;
            ">
                <span style="font-size:18px;">✨</span>
                <span><strong style="color:#67e8f9;">What\'s new</strong> &nbsp;{_hw_date} — {_hw_msg}</span>
                <a href="/history" style="margin-left:auto;color:#67e8f9;text-decoration:none;font-size:12px;white-space:nowrap;">See all changes →</a>
            </div>"""
    except:
        pass
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmpowerBands Worldwide</title>

<style>
body{{
    margin:0;
    font-family:Arial,sans-serif;
    background:#020817;
    color:white;
}}

.header{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:18px 6%;
    border-bottom:1px solid rgba(255,255,255,0.1);
    background:#020817;
}}

.logo-wrap{{
    display:flex;
    align-items:center;
    gap:14px;
}}

.logo-wrap img{{
    width:70px;
    height:70px;
    border-radius:50%;
    object-fit:cover;
    box-shadow:0 0 25px rgba(14,165,233,0.8);
}}

.logo-text{{
    font-size:24px;
    font-weight:900;
}}

.logo-text span{{
    display:block;
    color:#38bdf8;
    font-size:16px;
}}

.nav{{
    display:flex;
    gap:28px;
    align-items:center;
}}

.nav a{{
    color:white;
    text-decoration:none;
    font-weight:bold;
}}

.nav .active{{
    color:#38bdf8;
    border-bottom:2px solid #38bdf8;
    padding-bottom:8px;
}}

.top-buttons{{
    display:flex;
    gap:12px;
}}

.btn{{
    display:inline-block;
    padding:14px 22px;
    border-radius:10px;
    text-decoration:none;
    color:white;
    font-weight:800;
    background:linear-gradient(135deg,#06b6d4,#2563eb);
    box-shadow:0 0 25px rgba(37,99,235,0.4);
}}

.btn.dark{{
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.25);
    box-shadow:none;
}}

.hero{{
    padding:60px 6% 35px;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:35px;
    align-items:center;
    background:
        radial-gradient(circle at right,#0b4cff 0%,rgba(2,8,23,0.8) 35%,#020817 75%);
}}

.hero h1{{
    font-size:66px;
    line-height:1.05;
    margin:0;
}}

.hero h1 span{{
    display:block;
    background:linear-gradient(135deg,#06b6d4,#4f46e5);
    -webkit-background-clip:text;
    color:transparent;
}}

.hero h3{{
    color:#0ea5e9;
    font-size:24px;
    margin-bottom:12px;
}}

.hero p{{
    color:#dbeafe;
    line-height:1.6;
    max-width:620px;
}}

.hero-logo{{
    width:100%;
    max-width:520px;
    display:block;
    margin-bottom:25px;
    filter:drop-shadow(0 0 18px rgba(14,165,233,0.6));
}}

.hero-visual{{
    text-align:center;
}}

.hero-visual img{{
    width:100%;
    max-width:460px;
    border-radius:30px;
    filter:drop-shadow(0 0 45px rgba(37,99,235,0.8));
}}

.trust{{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
    gap:14px;
    margin-top:28px;
}}

.trust-card{{
    border:1px solid rgba(56,189,248,0.25);
    border-radius:10px;
    padding:14px;
    background:rgba(255,255,255,0.04);
}}

.section{{
    padding:30px 6%;
}}

.section h2{{
    text-align:center;
    font-size:34px;
    margin-bottom:22px;
}}

.grid{{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
    gap:18px;
}}

.card{{
    background:rgba(255,255,255,0.04);
    border:1px solid rgba(56,189,248,0.25);
    border-radius:16px;
    padding:24px;
    text-align:center;
    box-shadow:0 0 25px rgba(37,99,235,0.15);
}}

.card .num{{
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
}}

.card h3{{
    margin:8px 0;
}}

.card p{{
    color:#cbd5e1;
    line-height:1.5;
}}

.cta{{
    margin:30px 6%;
    padding:28px;
    border-radius:18px;
    border:1px solid #2563eb;
    box-shadow:0 0 35px rgba(37,99,235,0.4);
    display:grid;
    grid-template-columns:100px 1fr 1.3fr;
    gap:25px;
    align-items:center;
}}

.cta img{{
    width:85px;
    height:85px;
    border-radius:50%;
    box-shadow:0 0 30px rgba(14,165,233,0.8);
}}

.cta-buttons{{
    display:flex;
    gap:14px;
    flex-wrap:wrap;
    justify-content:flex-end;
}}

.footer{{
    padding:30px 6%;
    border-top:1px solid rgba(255,255,255,0.1);
    color:#94a3b8;
    display:flex;
    justify-content:space-between;
    gap:20px;
    flex-wrap:wrap;
}}

.footer a{{
    color:#cbd5e1;
    text-decoration:none;
    margin:0 8px;
}}

@media(max-width:850px){{
    .header,.nav,.top-buttons{{
        flex-direction:column;
        gap:16px;
    }}

    .hero{{
        grid-template-columns:1fr;
        text-align:center;
    }}

    .hero h1{{
        font-size:44px;
    }}

    .hero-logo{{
        margin:0 auto 25px;
    }}

    .cta{{
        grid-template-columns:1fr;
        text-align:center;
    }}

    .cta img{{
        margin:auto;
    }}

    .cta-buttons{{
        justify-content:center;
    }}

    .btn{{
        width:100%;
        box-sizing:border-box;
        text-align:center;
    }}
}}
</style>
</head>

<body>

<div class="header">
    

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



<div class="hero-banner">
    <img
        src="https://i.imgur.com/bSUxUXa.jpeg"
        alt="EmpowerBands Worldwide"
    >
</div>

<style>
.hero-banner {{
    grid-column:1 / -1;
    width:calc(100% + 12vw);
    margin-left:-6vw;
    overflow:hidden;
    padding:0;
}}

.hero-banner img {{
    display:block;
    width:100%;
    height:320px;
    object-fit:cover;
    object-position:center;
}}

@media(max-width:768px) {{
    .hero-banner img {{
        height:190px;
    }}
}}
</style>

    <h1>EmpowerBands <span>Worldwide</span></h1>

    <h3>Smart Wearable Safety Technology</h3>

    <p>
        EmpowerBands Worldwide is committed to safety inclusion,
        and rapid emergency response through smart wearable technology....
    </p>
</div>

</section>

</section>

<section id="about" class="section">
    <h2>About Us</h2>

    <p>
        EmpowerBands Worldwide is a safety technology company focused on helping
        individuals, families, caregivers, and communities access critical
        emergency information when it matters most.
    </p>

    <p>
        Through NFC-enabled wearable technology, EmpowerBands makes it easier
        for first responders, caregivers, and trusted contacts to quickly view
        important information during an emergency without requiring a special app.
    </p>

    <p>
        Our goal is to create simple, inclusive, and reliable safety solutions
        that give people greater peace of mind at home, at school, while traveling,
        and throughout everyday life.
    </p>
</section>

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
    <img src="https://i.imgur.com/RpBUbHd.png">

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

{spotlight_html}

<div class="footer">
    <div>
        <strong>EmpowerBands Worldwide</strong><br>
        Protect What Matters Most
    </div>

    <div>
        Decatur, Alabama<br>
        support@empowerbands.org
    </div>

    <div>
        <a href="/blessing-boxes">💛 Blessing Boxes</a> |
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

{whats_new_html}

<div style="
    text-align:center;
    padding:18px 20px 10px;
    font-family:Arial,sans-serif;
    font-size:13px;
    color:rgba(255,255,255,0.45);
">
    👁 <strong style="color:rgba(255,255,255,0.7);">{visit_count}</strong> visitors and counting
</div>

</body>
</html>
    <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>
"""



# IMPORTANT: Specific routes must be defined BEFORE the catch-all /<band_id> route above



SECTION A — I'M SAFE ROUTE
==========================

@app.route("/im_safe/<band_id>")
def im_safe(band_id):
    band_id = band_id.strip().upper()
    
    # Check rate limit - prevent spam
    if not can_send_safe_notification(band_id):
        return """
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body style="font-family:Arial;background:#f3f4f6;text-align:center;padding:40px;">
            <div style="background:white;padding:30px;border-radius:12px;max-width:420px;margin:auto;">
                <h2>⏱️ Too Many Safe Alerts</h2>
                <p style="color:#666;">You can only send one Safe alert every 5 minutes to prevent spam.</p>
                <p style="margin-top:20px;"><a href="/{band_id}" style="display:inline-block;padding:12px 24px;background:#111827;color:white;text-decoration:none;border-radius:10px;font-weight:bold;">Go Back</a></p>
            </div>
        </body>
        </html>
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
                <html>
                <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
                <body style="font-family:Arial;background:#f3f4f6;text-align:center;padding:40px;">
                    <div style="background:white;padding:30px;border-radius:12px;max-width:420px;margin:auto;">
                        <h2>✅ Marked as Safe</h2>
                        <p>Your emergency contacts have been notified that this was a false alarm or the situation is resolved.</p>
                        <p style="margin-top:20px;"><a href="/{band_id}" style="display:inline-block;padding:12px 24px;background:#111827;color:white;text-decoration:none;border-radius:10px;font-weight:bold;">Go Back</a></p>
                    </div>
                </body>
                </html>
                """
    return """
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="font-family:Arial;background:#f3f4f6;text-align:center;padding:40px;">
        <div style="background:white;padding:30px;border-radius:12px;max-width:420px;margin:auto;">
            <h2>Band Not Found</h2>
            <p><a href="/" style="display:inline-block;padding:12px 24px;background:#111827;color:white;text-decoration:none;border-radius:10px;font-weight:bold;">Home</a></p>
        </div>
    </body>
    </html>
    """

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

    # Read visitor counter
    _vc_file = "visit_count.txt"
    try:
        _dash_vc = int(open(_vc_file).read().strip()) if os.path.exists(_vc_file) else 0
        dash_visit_count = f"{_dash_vc:,}"
    except:
        dash_visit_count = "—"

    # Fetch last GitHub commit + detect new changes since login
    import urllib.request as _ur, json as _json
    last_updated_str = "Unavailable"
    new_changes_badge = ""
    new_changes_count = 0
    try:
        _req = _ur.Request(
            "https://api.github.com/repos/Ave4prezi/Empowerbands/commits?per_page=10",
            headers={"Authorization": f"token {os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN','')}",
                     "Accept": "application/vnd.github.v3+json", "User-Agent": "EmpowerBands-App"}
        )
        with _ur.urlopen(_req, timeout=5) as _r:
            _commits = _json.loads(_r.read().decode())
        if _commits:
            _c = _commits[0]
            _msg = _c.get("commit",{}).get("message","").split("\n")[0]
            _date = _c.get("commit",{}).get("author",{}).get("date","")[:10]
            last_updated_str = f"{_date} — {_msg}"
            # Count commits since last login
            last_seen = session.get("last_seen_sha","")
            if last_seen:
                for _i, _commit in enumerate(_commits):
                    if _commit.get("sha","") == last_seen:
                        new_changes_count = _i
                        break
                else:
                    new_changes_count = len(_commits)
            if new_changes_count > 0:
                new_changes_badge = f"""
                <div style="
                    background:linear-gradient(135deg,#f59e0b,#d97706);
                    color:white;
                    border-radius:14px;
                    padding:14px 20px;
                    margin:0 auto 20px;
                    max-width:700px;
                    display:flex;
                    align-items:center;
                    gap:12px;
                    font-size:14px;
                    font-weight:600;
                    box-shadow:0 4px 20px rgba(245,158,11,0.3);
                ">
                    <span style="font-size:20px;">🔔</span>
                    <span>{new_changes_count} new change{{'s' if new_changes_count != 1 else ''}} since your last login</span>
                    <a href="/history" style="margin-left:auto;background:rgba(0,0,0,0.2);color:white;text-decoration:none;padding:6px 14px;border-radius:8px;font-size:13px;">View →</a>
                    <a href="/dashboard/mark-seen" style="background:rgba(0,0,0,0.15);color:white;text-decoration:none;padding:6px 14px;border-radius:8px;font-size:13px;">Dismiss</a>
                </div>"""
    except:
        pass

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

        <a class="add-btn" href="/history">
            📋 Edit History
</a>

        <a class="add-btn" href="/admin/blessing-box-needs">
            📦 Update Box Needs
</a>

        <a class="add-btn" href="/admin/volunteers">
            👥 Volunteers
</a>

        <a class="add-btn" href="/admin/spotlight">
            💚 Family Spotlight
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

{new_changes_badge}

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

        <div class="stat-card">
            <div class="stat-number">{dash_visit_count}</div>
            <div class="stat-label">Site Visitors</div>
        </div>

    </div>

    <div style="
        background:rgba(255,255,255,0.06);
        border:1px solid rgba(255,255,255,0.1);
        border-radius:14px;
        padding:14px 20px;
        margin:0 auto 24px;
        max-width:700px;
        font-size:13px;
        color:#94a3b8;
        display:flex;
        align-items:center;
        gap:10px;
    ">
        <span style="color:#67e8f9;font-size:16px;">🕒</span>
        <span><strong style="color:white;">Last updated:</strong> {last_updated_str}</span>
        <a href="/history" style="margin-left:auto;color:#67e8f9;text-decoration:none;font-size:12px;">View all →</a>
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

</html
    <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>.
"""

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
                pin = row[10] if (len(row) > 10 and row[10]) else "1234"
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

    
                
SECTION C — ALERT RESULT WITH I'M SAFE BUTTON
=============================================

                entered_pin = request.args.get("pin")

                if alert_mode:
                    success = send_full_alert(
                        name,
                        emergency_phones,
                        emergency_emails,
                        band_id
                    )

                    if success:
                        return f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <title>Alert Sent</title>
                        </head>
                        <body style="font-family:Arial;background:#07111f;color:white;text-align:center;padding:40px;">
                            <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);padding:30px;border-radius:18px;max-width:460px;margin:auto;">
                                <h1>✅ Alert Sent</h1>
                                <p>Emergency contact(s) have been notified.</p>

                                <a href="/im_safe/{band_id}"
                                   style="display:block;margin-top:18px;padding:16px 22px;border-radius:12px;background:#16a34a;color:white;text-decoration:none;font-weight:bold;">
                                    ✅ I'm Safe — Mark Alert Resolved
                                </a>

                                <a href="/{band_id}"
                                   style="display:block;margin-top:14px;padding:14px 22px;border-radius:12px;background:#111827;color:white;text-decoration:none;font-weight:bold;">
                                    Go Back
                                </a>
                            </div>
                        </body>
                        </html>
                        """
                    else:
                        return f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <title>Alert Failed</title>
                        </head>
                        <body style="font-family:Arial;background:#07111f;color:white;text-align:center;padding:40px;">
                            <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);padding:30px;border-radius:18px;max-width:460px;margin:auto;">
                                <h1>❌ Alert Failed</h1>
                                <p>There was a problem sending the alert.</p>
                                <p>Call the emergency contact or 911 if this is life-threatening.</p>

                                <a href="/{band_id}"
                                   style="display:block;margin-top:14px;padding:14px 22px;border-radius:12px;background:#111827;color:white;text-decoration:none;font-weight:bold;">
                                    Go Back
                                </a>
                            </div>
                        </body>
                        </html>
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

                            <button onclick="sendAlertWithLocation()" style="display:block;width:100%;padding:15px;border-radius:10px;border:none;background:#dc2626;color:white;font-weight:bold;cursor:pointer;">
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

.btn-red {{
    background:linear-gradient(135deg,#ef4444,#dc2626);
    color:white;
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
{emergency_phones}
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


<a class="btn btn-blue" href="tel:{emergency_phones.split(',')[0].strip()}">
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
    padding-top:95px
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

.btn-dark {{
    background:rgba(255,255,255,.12);
    color:white;
    border:1px solid rgba(255,255,255,.15);
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

.sticky-alert{{
    position:fixed;
    top:0;
    left:0;
    width:100%;
    z-index:9999;
    background:white;
    padding:10px;
    box-shadow:0 2px 8px rgba(0,0,0,.2);
}}

.sticky-alert button{{
    width:100%;
    background:#dc2626;
    color:white;
    font-size:24px;
    font-weight:bold;
    padding:18px;
    border:none;
    border-radius:12px;
    cursor:pointer;
}}

body{{
    padding-top:95px;
}}
</style>
</head>

<body>

<div class="sticky-alert">
<form action="/{band_id}" method="GET">
    <input type="hidden" name="confirm_alert" value="yes">
    <button type="submit">🚨 SEND EMERGENCY ALERT</button>
</form>
</div>

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

<a class="btn btn-blue" href="tel:{emergency_phones.split(',')[0].strip() if emergency_phones else ''}">
📞 Call Emergency Contact
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
    <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>
"""


    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/admin">Admin Login</a></p>
    """

@app.route("/donate")
def donate():
    return redirect("https://www.paypal.com/ncp/payment/6ZT5B9XMXD3K6")

@app.route("/qr/<band_id>")
def qr_code(band_id):
    band_id = band_id.strip().upper()
    url = f"{BASE_URL}/{band_id}"

    img = qrcode.make(url)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")

# ===============================
# PUBLIC BAND SHORT LINK
# Keep this below every other route.
# ===============================

@app.route("/<band_id>")
def band_profile_shortcut(band_id):
    band_id = band_id.strip().upper()

    # Only allow valid EmpowerBand-style IDs
    if not band_id.startswith("EB"):
        return redirect("/")

    if not band_id[2:].isdigit():
        return redirect("/")

    return profile(band_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
