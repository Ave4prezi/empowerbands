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

LOGO_URL = "https://i.imgur.com/dE4kSOz.png"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    "https://i.imgur.com/dE4kSOz.png"
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
                <a href="/donate" style="display:inline-block;margin-top:16px;padding:12px 24px;border-radius:12px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;text-decoration:none;font-weight:700;font-size:14px;">
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


    <div>
        <img class="hero-logo" src="https://i.imgur.com/RpBUbHd.png" alt="EmpowerBands Logo">

        <h1>EmpowerBands <span>Worldwide</span></h1>

        <h3>Smart Wearable Safety Technology</h3>

        <p>EmpowerBands Worldwide is committed to safety inclusion, and rapid emergency response through smart wearable technology....</p>
    </div>

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
    "sms-opt-in",
    "donate",
    "im_safe"
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
            # Store latest commit SHA at login time so we can detect new changes
            try:
                import urllib.request as _ulr, json as _jj
                _r2 = _ulr.Request(
                    "https://api.github.com/repos/Ave4prezi/Empowerbands/commits?per_page=1",
                    headers={"Authorization": f"token {os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN','')}",
                             "Accept": "application/vnd.github.v3+json", "User-Agent": "EmpowerBands-App"}
                )
                with _ulr.urlopen(_r2, timeout=5) as _rr:
                    _cc = _jj.loads(_rr.read().decode())
                session["last_seen_sha"] = _cc[0]["sha"] if _cc else ""
            except:
                session["last_seen_sha"] = ""
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
   <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>
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

<input name="name" placeholder="Full Name" required>

<input name="email" placeholder="Email">

<input name="phone" placeholder="Primary Phone">

<input name="emergency_phones" placeholder="Emergency Contacts (comma separated)" required>

<input name="emergency_emails" placeholder="Emergency Emails (comma separated)">

<input name="age_group" placeholder="Child / Adult / Senior">

<input name="condition" placeholder="Public condition example: Autism - Nonverbal">

<textarea name="instructions" placeholder="Public instructions"></textarea>

<textarea name="medical_notes" placeholder="Private medical notes"></textarea>

<input name="pin" placeholder="PIN example: 1234" required>

<input name="address" placeholder="Address">

<input name="race" placeholder="Race">

<input name="gender" placeholder="Gender">

<input type="file" name="photo" placeholder="Photo">

<input name="photo_url" placeholder="Photo URL (if not uploading)">

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
            request.form.get("photo_url", "").strip()
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

<button type="submit">Save Changes</button>

</form>

<a class="back" href="/dashboard">Back to Dashboard</a>

</div>
</div>
</body>
</html>
    <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>
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

    

                entered_pin = request.args.get("pin")
                if alert_mode:
                    success = send_full_alert(name, emergency_phones, emergency_emails, band_id)

                    if success:
                        return f"""
                        <h1>✅ Alert Sent</h1>
                        <p>Emergency contact(s) have been notified.</p>
                        <p><a href="/im_safe/{band_id}" style="display:inline-block;margin-top:14px;padding:14px 22px;border-radius:12px;background:#16a34a;color:white;text-decoration:none;font-weight:bold;">✅ I'm Safe — Notify Contacts It Was a False Alarm</a></p>
                        <p style="margin-top:14px;"><a href="/{band_id}">Go Back</a></p>
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

@app.route("/im_safe/<band_id>")
def im_safe(band_id):
    band_id = band_id.strip().upper()
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

# ===============================
# SCAN LOGS PAGE
# ===============================

@app.route("/scans")
def scans():

    if not session.get("logged_in"):
        return redirect("/admin")

    scans_list = []

    try:

        with open(scan_log_file, "r", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:
                scans_list.append(row)

        scans_list.reverse()

    except:
        scans_list = []

    rows_html = ""

    for scan in scans_list:

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
   <script src="//code.tidio.co/5wtnltojqfvgeld8mqgrsjopkkkwqgxd.js" async></script>
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
                emergency_phones = row[4] if len(row) > 4 else ""
                emergency_emails = row[5] if len(row) > 5 else ""

                send_full_alert(name, emergency_phones, emergency_emails, band_id, maps_link)

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

        .site-footer{{
    margin-top:40px;
    padding:25px 15px;
    text-align:center;
    color:rgba(255,255,255,0.75);
    font-size:14px;
    border-top:1px solid rgba(255,255,255,0.15);
    background:rgba(0,0,0,0.18);
}}

.site-footer p{{
    margin:6px 0;
}}
    </style>
</head>

<body>
    <div class="card">
        <h1>✅ Alert Sent</h1>
        <p>Emergency contacts have been notified.</p>

        <a href="/" class="home-btn">🏠 Return Home</a>
    </div>

    <footer class="site-footer">
        <p><strong>EmpowerBands Worldwide</strong> © 2026</p>
        <p>One Tap. One Network. Infinite Possibilities.</p>
        <p>Emergency support profiles powered by NFC + QR access.</p>
        <p>Decatur, Alabama | support@empowerbands.org</p>
    </footer>

</body>
</html>
"""

    return "<h1>Band not found</h1>"


# ===============================
# APP MANIFEST
# ===============================

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "EmpowerBands Worldwide",
        "short_name": "EmpowerBands",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#07111f",
        "theme_color": "#07111f",
        "icons": [
            {
                "src": LOGO_URL,
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": LOGO_URL,
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }) 
                

# ===============================
# EDIT HISTORY PAGE
# ===============================

@app.route("/history")
def edit_history():
    import urllib.request
    import json as _json
    gh_token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    repo = "Ave4prezi/Empowerbands"
    commits_html = ""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/commits?per_page=30",
            headers={
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "EmpowerBands-App"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            commits = _json.loads(resp.read().decode())
        for c in commits:
            sha = c.get("sha","")[:7]
            msg = c.get("commit",{}).get("message","").split("\n")[0]
            author = c.get("commit",{}).get("author",{}).get("name","")
            date_raw = c.get("commit",{}).get("author",{}).get("date","")
            date = date_raw[:10] if date_raw else ""
            url = c.get("html_url","#")
            commits_html += f"""
            <div class="commit">
                <div class="commit-msg">{msg}</div>
                <div class="commit-meta">
                    <span class="sha"><a href="{url}" target="_blank">{sha}</a></span>
                    <span>{author}</span>
                    <span>{date}</span>
                </div>
            </div>"""
    except Exception as e:
        commits_html = f'<p style="color:#f87171;">Could not load history: {e}</p>'

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit History — EmpowerBands</title>
    <style>
        body {{
            margin:0;
            font-family:Arial,sans-serif;
            background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);
            color:white;
            min-height:100vh;
            padding:30px 20px;
        }}
        .page {{ max-width:720px; margin:auto; }}
        h1 {{ font-size:32px; margin-bottom:6px; }}
        .subtitle {{ color:#94a3b8; margin-bottom:20px; font-size:14px; }}
        .filters {{
            display:flex;
            gap:12px;
            margin-bottom:24px;
            flex-wrap:wrap;
        }}
        .filters input {{
            flex:1;
            min-width:160px;
            padding:12px 16px;
            border:none;
            border-radius:12px;
            background:rgba(255,255,255,0.1);
            color:white;
            font-size:14px;
            outline:none;
        }}
        .filters input::placeholder {{ color:#94a3b8; }}
        .filters input:focus {{ background:rgba(255,255,255,0.15); }}
        .clear-btn {{
            padding:12px 18px;
            border:none;
            border-radius:12px;
            background:rgba(255,255,255,0.08);
            color:#94a3b8;
            font-size:13px;
            cursor:pointer;
            white-space:nowrap;
        }}
        .clear-btn:hover {{ background:rgba(255,255,255,0.14); color:white; }}
        .commit {{
            background:rgba(255,255,255,0.07);
            border:1px solid rgba(255,255,255,0.12);
            border-radius:16px;
            padding:16px 20px;
            margin-bottom:12px;
        }}
        .commit.hidden {{ display:none; }}
        .commit-msg {{ font-size:15px; font-weight:600; margin-bottom:8px; }}
        .commit-meta {{ display:flex; gap:18px; font-size:12px; color:#94a3b8; flex-wrap:wrap; }}
        .sha a {{ color:#67e8f9; text-decoration:none; font-family:monospace; }}
        .back {{
            display:inline-block;
            margin-bottom:24px;
            padding:10px 18px;
            border-radius:12px;
            background:rgba(255,255,255,0.1);
            color:white;
            text-decoration:none;
            font-size:14px;
        }}
        .no-results {{
            text-align:center;
            padding:40px;
            color:#94a3b8;
            display:none;
        }}
        .count {{ color:#67e8f9; font-size:13px; margin-bottom:16px; }}
    </style>
</head>
<body>
<div class="page">
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px;">
        <a class="back" href="/">← Back to Home</a>
        <a class="back" href="/dashboard" style="background:rgba(37,99,235,0.35);">⚙️ Dashboard</a>
    </div>
    <h1>Edit History</h1>
    <p class="subtitle">Last 30 changes to the EmpowerBands codebase</p>

    <div class="filters">
        <input type="text" id="keywordFilter" placeholder="🔍 Search by keyword or author..." oninput="filterCommits()">
        <input type="date" id="dateFilter" oninput="filterCommits()">
        <button class="clear-btn" onclick="clearFilters()">✕ Clear</button>
    </div>

    <div class="count" id="resultCount"></div>

    <div id="commitList">
        {commits_html}
    </div>
    <div class="no-results" id="noResults">No matching changes found.</div>
</div>

<script>
function filterCommits() {{
    const keyword = document.getElementById('keywordFilter').value.toLowerCase().trim();
    const date = document.getElementById('dateFilter').value;
    const commits = document.querySelectorAll('.commit');
    let visible = 0;

    commits.forEach(c => {{
        const msg = c.querySelector('.commit-msg').textContent.toLowerCase();
        const meta = c.querySelector('.commit-meta').textContent.toLowerCase();
        const combined = msg + ' ' + meta;

        const matchesKeyword = !keyword || combined.includes(keyword);
        const matchesDate = !date || meta.includes(date);

        if (matchesKeyword && matchesDate) {{
            c.classList.remove('hidden');
            visible++;
        }} else {{
            c.classList.add('hidden');
        }}
    }});

    const countEl = document.getElementById('resultCount');
    const noResults = document.getElementById('noResults');

    if (keyword || date) {{
        countEl.textContent = visible + ' result' + (visible !== 1 ? 's' : '') + ' found';
        noResults.style.display = visible === 0 ? 'block' : 'none';
    }} else {{
        countEl.textContent = '';
        noResults.style.display = 'none';
    }}
}}

function clearFilters() {{
    document.getElementById('keywordFilter').value = '';
    document.getElementById('dateFilter').value = '';
    filterCommits();
}}
</script>
</body>
</html>
"""


# ===============================
# MARK CHANGES AS SEEN
# ===============================

@app.route("/dashboard/mark-seen")
def mark_seen():
    if not session.get("logged_in"):
        return redirect("/admin")
    import urllib.request as _ur2, json as _jj2
    try:
        _req3 = _ur2.Request(
            "https://api.github.com/repos/Ave4prezi/Empowerbands/commits?per_page=1",
            headers={"Authorization": f"token {os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN','')}",
                     "Accept": "application/vnd.github.v3+json", "User-Agent": "EmpowerBands-App"}
        )
        with _ur2.urlopen(_req3, timeout=5) as _r3:
            _cc3 = _jj2.loads(_r3.read().decode())
        session["last_seen_sha"] = _cc3[0]["sha"] if _cc3 else ""
    except:
        pass
    return redirect("/dashboard")


# ===============================
# GITHUB PUSH WEBHOOK
# ===============================

@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            return "Forbidden", 403

    payload = request.get_json(silent=True) or {}
    ref = payload.get("ref", "")

    # Only notify on pushes to the main/master branch
    if ref not in ("refs/heads/main", "refs/heads/master"):
        return "OK", 200

    pusher = payload.get("pusher", {}).get("name", "Someone")
    commits = payload.get("commits", [])
    repo_name = payload.get("repository", {}).get("full_name", "Ave4prezi/Empowerbands")
    compare_url = payload.get("compare", f"https://github.com/{repo_name}/commits")

    if not commits:
        return "OK", 200

    commit_lines = ""
    for c in commits[:5]:
        sha = c.get("id", "")[:7]
        msg = c.get("message", "").split("\n")[0]
        url = c.get("url", "#")
        commit_lines += f"  • [{sha}] {msg}\n    {url}\n\n"

    email_body = (
        f"EmpowerBands — New Code Change\n\n"
        f"{pusher} pushed {len(commits)} commit{'s' if len(commits) != 1 else ''} to {repo_name}.\n\n"
        f"Changes:\n{commit_lines}"
        f"View diff: {compare_url}\n\n"
        f"— EmpowerBands Webhook"
    )

    email_list = [e.strip() for e in ALERT_EMAILS.split(",") if e.strip()] if ALERT_EMAILS else []

    if email_list and ALERT_EMAIL_PASSWORD:
        try:
            msg = MIMEText(email_body)
            msg["Subject"] = f"🔔 EmpowerBands: {len(commits)} new change{'s' if len(commits) != 1 else ''} by {pusher}"
            msg["From"] = email_list[0]
            msg["To"] = ", ".join(email_list)
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(email_list[0], ALERT_EMAIL_PASSWORD)
            server.sendmail(email_list[0], email_list, msg.as_string())
            server.quit()
        except Exception as e:
            print(f"Webhook email error: {e}")

    return "OK", 200


# ===============================
# BLESSING BOXES PAGE
# ===============================

@app.route("/blessing-boxes", methods=["GET","POST"])
def blessing_boxes():
    import json as _bb_json
    try:
        with open("blessing_box_needs.json", "r") as _f:
            _bb_items = _bb_json.load(_f)
    except:
        _bb_items = []
    needs_grid_html = "".join(
        f'<div class="need-item"><span>{i["emoji"]}</span>{i["label"]}</div>'
        for i in _bb_items
    ) or '<p style="color:#94a3b8;">No items listed yet.</p>'

    vol_success = False
    vol_error = ""
    if request.method == "POST":
        v_name = request.form.get("v_name","").strip()
        v_email = request.form.get("v_email","").strip()
        v_phone = request.form.get("v_phone","").strip()
        v_avail = request.form.get("v_avail","").strip()
        v_msg   = request.form.get("v_msg","").strip()
        if v_name and (v_email or v_phone):
            import csv as _vcsv, time as _vt
            with open("bb_volunteers.csv","a",newline="",encoding="utf-8") as _vf:
                _vcsv.writer(_vf).writerow([v_name,v_email,v_phone,v_avail,v_msg,_vt.strftime("%Y-%m-%d %H:%M")])
            vol_success = True
        else:
            vol_error = "Please enter your name and at least one way to reach you."

    vol_banner = ""
    if vol_success:
        vol_banner = '''<div style="background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.4);border-radius:14px;padding:16px 20px;margin-bottom:20px;color:#86efac;font-size:15px;font-weight:600;">
            ✅ Thank you! We'll be in touch soon.
        </div>'''
    elif vol_error:
        vol_banner = f'''<div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:14px;padding:16px 20px;margin-bottom:20px;color:#fca5a5;font-size:14px;">
            ⚠️ {vol_error}
        </div>'''

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blessing Boxes — EmpowerBands</title>
    <style>
        *{{box-sizing:border-box;margin:0;padding:0;}}
        body{{
            font-family:Arial,sans-serif;
            background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);
            color:white;
            min-height:100vh;
        }}
        .hero{{
            text-align:center;
            padding:60px 20px 40px;
        }}
        .hero h1{{
            font-size:38px;
            font-weight:900;
            margin-bottom:14px;
        }}
        .hero h1 span{{color:#67e8f9;}}
        .hero p{{
            font-size:17px;
            color:#cbd5e1;
            max-width:600px;
            margin:0 auto;
            line-height:1.7;
        }}
        .page{{max-width:760px;margin:0 auto;padding:0 20px 60px;}}
        .card{{
            background:rgba(255,255,255,0.07);
            border:1px solid rgba(255,255,255,0.13);
            border-radius:20px;
            padding:28px;
            margin-bottom:22px;
        }}
        .card h2{{
            font-size:20px;
            font-weight:800;
            margin-bottom:12px;
            color:#67e8f9;
            display:flex;
            align-items:center;
            gap:10px;
        }}
        .card p,.card li{{
            color:#cbd5e1;
            line-height:1.75;
            font-size:15px;
        }}
        .card ul{{
            padding-left:20px;
            margin-top:8px;
        }}
        .card li{{margin-bottom:6px;}}
        .location-badge{{
            display:inline-block;
            background:rgba(14,165,233,0.18);
            border:1px solid rgba(103,232,249,0.3);
            border-radius:10px;
            padding:8px 16px;
            font-size:14px;
            color:#e0f2fe;
            margin:6px 6px 0 0;
        }}
        .needs-grid{{
            display:grid;
            grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
            gap:12px;
            margin-top:14px;
        }}
        .need-item{{
            background:rgba(255,255,255,0.07);
            border-radius:12px;
            padding:14px;
            text-align:center;
            font-size:14px;
            color:#e5e7eb;
        }}
        .need-item span{{display:block;font-size:26px;margin-bottom:6px;}}
        .btn{{
            display:inline-block;
            padding:15px 28px;
            border-radius:14px;
            text-decoration:none;
            font-weight:700;
            font-size:15px;
            margin:8px 8px 0 0;
        }}
        .btn-cyan{{background:linear-gradient(135deg,#06b6d4,#2563eb);color:white;}}
        .btn-green{{background:linear-gradient(135deg,#22c55e,#16a34a);color:white;}}
        .btn-outline{{
            background:rgba(255,255,255,0.1);
            border:1px solid rgba(255,255,255,0.2);
            color:white;
        }}
        .partner-box{{
            background:rgba(37,99,235,0.15);
            border:1px solid rgba(96,165,250,0.3);
            border-radius:16px;
            padding:22px;
            margin-top:14px;
        }}
        .partner-box p{{color:#bfdbfe;font-size:15px;line-height:1.7;}}
        .back{{
            display:inline-block;
            margin:24px 0 0;
            padding:10px 18px;
            border-radius:12px;
            background:rgba(255,255,255,0.1);
            color:white;
            text-decoration:none;
            font-size:14px;
        }}
        footer{{
            text-align:center;
            padding:30px 20px;
            color:#475569;
            font-size:13px;
            border-top:1px solid rgba(255,255,255,0.07);
        }}
        footer a{{color:#67e8f9;text-decoration:none;}}
    </style>
</head>
<body>

<div class="hero">
    <img src="https://i.imgur.com/RpBUbHd.png" alt="EmpowerBands Logo" style="width:70px;margin-bottom:20px;border-radius:50%;">
    <h1>Community <span>Blessing Boxes</span></h1>
    <p>
        Free essentials — no questions asked. Our Blessing Boxes are stocked by neighbors
        for neighbors, keeping food, hygiene products, and daily necessities within reach
        for anyone who needs them.
    </p>
</div>

<div class="page">
    <a class="back" href="/">← Back to Home</a>

    <!-- WHERE ARE THE BOXES -->
    <div class="card" style="margin-top:20px;">
        <h2>📍 Where to Find a Box</h2>
<p>We currently have Blessing Boxes set up at:</p>

<br>

<a href="https://www.google.com/maps/search/The+Spotted+Ladybug+Hartselle+AL"
   target="_blank"
   class="location-badge"
   style="text-decoration:none;">
    📦 The Spotted Ladybug — Downtown Hartselle, AL
</a>

<br><br>

<a href="https://www.google.com/maps/search/Cowboys+1605+Main+St+E+Hartselle+AL+35640"
   target="_blank"
   class="location-badge"
   style="text-decoration:none;">
    📦 Cowboys — 1605 Main St E, Hartselle, AL
</a>

<br><br>

<p style="font-size:14px;color:#94a3b8;">
    📌 <em>Tap either badge above to get directions.</em>
</p>

<br>

<p>
    We are actively looking to partner with additional local businesses to host
    Blessing Boxes throughout the community. If you own or manage a business and
    would like to host a box, see the partnership section below.
</p>
</div>

    <!-- WHAT'S NEEDED -->
    <div class="card">
        <h2>🛒 What's Needed Right Now</h2>
        <p>The boxes accept any gently used or new items. Here's what's most needed:</p>
        <div class="needs-grid">
            {needs_grid_html}
        </div>
    </div>

    <!-- HOW TO HELP -->
    <div class="card">
        <h2>🤝 How You Can Help</h2>
        <p>There are three simple ways to make a difference:</p>
        <ul>
            <li><strong>Drop off supplies</strong> — Visit any box location and leave items you can spare.</li>
            <li><strong>Volunteer</strong> — Help us restock, organize, and maintain the boxes.</li>
            <li><strong>Donate</strong> — A financial gift helps us purchase the items the boxes need most.</li>
        </ul>
        <br>
        <a class="btn btn-cyan" href="/donate">❤️ Donate Now</a>
    </div>

    <!-- VOLUNTEER FORM -->
    <div class="card" id="volunteer">
        <h2>✋ Volunteer Sign Up</h2>
        <p style="color:#cbd5e1;margin-bottom:18px;">Fill out the form below and we'll reach out with next steps. No experience needed — just a willing heart!</p>
        {vol_banner}
        <form method="POST" action="/blessing-boxes#volunteer">
            <div style="display:grid;gap:12px;">
                <input type="text" name="v_name" placeholder="Your Name *" required
                    style="padding:13px 16px;border:none;border-radius:12px;background:rgba(255,255,255,0.1);color:white;font-size:15px;outline:none;width:100%;box-sizing:border-box;">
                <input type="email" name="v_email" placeholder="Email Address"
                    style="padding:13px 16px;border:none;border-radius:12px;background:rgba(255,255,255,0.1);color:white;font-size:15px;outline:none;width:100%;box-sizing:border-box;">
                <input type="tel" name="v_phone" placeholder="Phone Number"
                    style="padding:13px 16px;border:none;border-radius:12px;background:rgba(255,255,255,0.1);color:white;font-size:15px;outline:none;width:100%;box-sizing:border-box;">
                <select name="v_avail"
                    style="padding:13px 16px;border:none;border-radius:12px;background:rgba(30,41,59,0.9);color:white;font-size:15px;outline:none;width:100%;box-sizing:border-box;">
                    <option value="">When are you available?</option>
                    <option>Weekday mornings</option>
                    <option>Weekday afternoons</option>
                    <option>Weekday evenings</option>
                    <option>Weekends</option>
                    <option>Flexible / Any time</option>
                </select>
                <textarea name="v_msg" placeholder="Anything else you'd like us to know? (optional)" rows="3"
                    style="padding:13px 16px;border:none;border-radius:12px;background:rgba(255,255,255,0.1);color:white;font-size:15px;outline:none;width:100%;box-sizing:border-box;resize:vertical;"></textarea>
                <button type="submit"
                    style="padding:15px;border:none;border-radius:14px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;font-size:16px;font-weight:700;cursor:pointer;">
                    ✋ Submit Sign Up
                </button>
            </div>
        </form>
    </div>

    <!-- BUSINESS PARTNERSHIP -->
    <div class="card">
        <h2>🏪 Partner With Us</h2>
        <p>
            We are looking to partner with local businesses in Hartselle and the surrounding
            area to host Blessing Boxes at their locations. Hosting a box is a simple, powerful
            way to show your community that your business cares.
        </p>
        <div class="partner-box">
            <p>
                <strong style="color:white;">What hosting looks like:</strong><br>
                We provide the box and handle restocking. You provide a visible outdoor or
                entryway space. Your business gets recognized as a community partner on our
                website and social media.
            </p>
        </div>
        <br>
        <a class="btn btn-outline" href="mailto:support@empowerbands.org?subject=Blessing Box Partnership Inquiry">📧 Contact Us to Partner</a>
    </div>

    <!-- SPREAD THE WORD -->
    <div class="card">
        <h2>📣 Spread the Word</h2>
        <p>
            Share this page with friends, family, churches, and local groups.
            The more people who know, the more lives we can reach together.
        </p>
        <br>
        <a class="btn btn-outline" href="https://www.facebook.com/sharer/sharer.php?u=https://empowerbands.org/blessing-boxes" target="_blank">Share on Facebook</a>
    </div>

</div>

<footer>
    <p>&copy; 2026 EmpowerBands Worldwide &nbsp;|&nbsp; Decatur, Alabama &nbsp;|&nbsp; support@empowerbands.org</p>
    <p style="margin-top:8px;">
        <a href="/">Home</a> &nbsp;|&nbsp;
        <a href="/donate">Donate</a> &nbsp;|&nbsp;
        <a href="/privacy">Privacy Policy</a>
    </p>
</footer>

</body>
</html>
"""



# ===============================
# ADMIN — VIEW VOLUNTEERS
# ===============================

@app.route("/admin/volunteers")
def admin_volunteers():
    if not session.get("logged_in"):
        return redirect("/admin")
    vols = []
    try:
        with open("bb_volunteers.csv","r",encoding="utf-8") as _vf:
            import csv as _vacsv
            reader = _vacsv.DictReader(_vf)
            for row in reader:
                vols.append(row)
        vols.reverse()
    except:
        vols = []

    rows_html = ""
    for v in vols:
        rows_html += f"""<tr>
            <td>{v.get('Name','')}</td>
            <td>{v.get('Email','')}</td>
            <td>{v.get('Phone','')}</td>
            <td>{v.get('Availability','')}</td>
            <td style="max-width:180px;word-break:break-word;">{v.get('Message','')}</td>
            <td>{v.get('Submitted','')}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volunteers — EmpowerBands</title>
    <style>
        body{{margin:0;font-family:Arial,sans-serif;background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);color:white;min-height:100vh;padding:25px 16px;}}
        .page{{max-width:960px;margin:auto;}}
        h1{{font-size:28px;margin-bottom:4px;}}
        .sub{{color:#94a3b8;font-size:14px;margin-bottom:24px;}}
        .back{{display:inline-block;margin-bottom:22px;padding:10px 18px;border-radius:12px;background:rgba(255,255,255,0.1);color:white;text-decoration:none;font-size:14px;margin-right:10px;}}
        .wrap{{overflow-x:auto;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:20px;}}
        table{{width:100%;border-collapse:collapse;font-size:14px;}}
        th{{color:#67e8f9;font-size:12px;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.1);}}
        td{{padding:12px 12px;border-bottom:1px solid rgba(255,255,255,0.06);color:#e5e7eb;vertical-align:top;}}
        tr:last-child td{{border-bottom:none;}}
        .empty{{text-align:center;padding:40px;color:#64748b;}}
        .count{{display:inline-block;background:rgba(103,232,249,0.12);border:1px solid rgba(103,232,249,0.25);border-radius:8px;padding:4px 12px;font-size:13px;color:#67e8f9;margin-bottom:20px;}}
    </style>
</head>
<body>
<div class="page">
    <a class="back" href="/dashboard">⬅ Dashboard</a>
    <a class="back" href="/blessing-boxes" target="_blank">👁 View Page</a>
    <a class="back" href="/admin/volunteers/export">⬇ Export CSV</a>
    <h1>✋ Blessing Box Volunteers</h1>
    <p class="sub">Everyone who has signed up to help through the website.</p>
    <div class="count">{len(vols)} volunteer{{'s' if len(vols) != 1 else ''}} total</div>
    <div class="wrap">
        <table>
            <tr><th>Name</th><th>Email</th><th>Phone</th><th>Availability</th><th>Message</th><th>Submitted</th></tr>
            {rows_html if rows_html else '<tr><td colspan="6" class="empty">No sign-ups yet.</td></tr>'}
        </table>
    </div>
</div>
</body>
</html>
"""

# ===============================
# ADMIN — FAMILY SPOTLIGHT
# ===============================

@app.route("/admin/spotlight", methods=["GET","POST"])
def admin_spotlight():
    if not session.get("logged_in"):
        return redirect("/admin")
    import json as _asp_json
    _sp_file = "family_spotlight.json"
    message = ""

    if request.method == "POST":
        data = {
            "active": request.form.get("active") == "on",
            "month": request.form.get("month","").strip(),
            "story": request.form.get("story","").strip(),
            "photo_url": request.form.get("photo_url","").strip(),
        }
        with open(_sp_file, "w") as _f:
            _asp_json.dump(data, _f)
        message = "✅ Spotlight updated!"

    try:
        with open(_sp_file, "r") as _f:
            current = _asp_json.load(_f)
    except:
        current = {"active": False, "month": "", "story": "", "photo_url": ""}

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Spotlight — EmpowerBands</title>
    <style>
        body{{margin:0;font-family:Arial,sans-serif;background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);color:white;min-height:100vh;padding:30px 20px;}}
        .page{{max-width:640px;margin:auto;}}
        h1{{font-size:28px;margin-bottom:6px;}}
        .sub{{color:#94a3b8;font-size:14px;margin-bottom:24px;}}
        .back{{display:inline-block;margin-bottom:22px;padding:10px 18px;border-radius:12px;background:rgba(255,255,255,0.1);color:white;text-decoration:none;font-size:14px;margin-right:10px;}}
        .card{{background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:26px;}}
        label{{display:block;font-size:13px;color:#94a3b8;margin-bottom:6px;margin-top:16px;}}
        input[type=text],textarea{{width:100%;box-sizing:border-box;padding:13px 16px;border:none;border-radius:12px;background:rgba(255,255,255,0.1);color:white;font-size:15px;outline:none;}}
        textarea{{resize:vertical;}}
        .toggle-row{{display:flex;align-items:center;gap:10px;margin-top:16px;}}
        button{{margin-top:22px;width:100%;padding:15px;border:none;border-radius:14px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;font-size:16px;font-weight:700;cursor:pointer;}}
        .msg{{background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.4);border-radius:12px;padding:12px 16px;margin-bottom:16px;color:#86efac;font-size:14px;}}
    </style>
</head>
<body>
<div class="page">
    <a class="back" href="/dashboard">⬅ Dashboard</a>
    <a class="back" href="/" target="_blank">👁 View Page</a>
    <h1>💚 Family Spotlight</h1>
    <p class="sub">Feature the family your donations are blessing this month on the homepage.</p>
    {'<div class="msg">' + message + '</div>' if message else ''}
    <div class="card">
        <form method="POST">
            <div class="toggle-row">
                <input type="checkbox" name="active" id="active" {'checked' if current.get('active') else ''} style="width:20px;height:20px;">
                <label for="active" style="margin:0;">Show on homepage</label>
            </div>
            <label>Month (e.g. "July 2026")</label>
            <input type="text" name="month" value="{current.get('month','')}" placeholder="July 2026">
            <label>Family's Story</label>
            <textarea name="story" rows="5" placeholder="This month, we're blessing the Johnson family...">{current.get('story','')}</textarea>
            <label>Photo URL (optional — defaults to logo)</label>
            <input type="text" name="photo_url" value="{current.get('photo_url','')}" placeholder="https://...">
            <button type="submit">💾 Save & Publish</button>
        </form>
    </div>
</div>
</body>
</html>
"""

# ===============================
# ADMIN — EXPORT VOLUNTEERS CSV
# ===============================

@app.route("/admin/volunteers/export")
def admin_volunteers_export():
    if not session.get("logged_in"):
        return redirect("/admin")
    if not os.path.exists("bb_volunteers.csv"):
        return redirect("/admin/volunteers")
    return send_file(
        "bb_volunteers.csv",
        as_attachment=True,
        download_name="blessing_box_volunteers.csv",
        mimetype="text/csv"
    )

# ===============================
# ADMIN — UPDATE BLESSING BOX NEEDS
# ===============================

@app.route("/admin/blessing-box-needs", methods=["GET", "POST"])
def admin_blessing_box_needs():
    if not session.get("logged_in"):
        return redirect("/admin")
    import json as _ubn_json

    _needs_file = "blessing_box_needs.json"
    message = ""

    if request.method == "POST":
        raw = request.form.get("needs_text", "")
        new_items = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                new_items.append({"emoji": parts[0].strip(), "label": parts[1].strip()})
            else:
                new_items.append({"emoji": "📦", "label": line})
        with open(_needs_file, "w") as _f:
            _ubn_json.dump(new_items, _f)
        message = "✅ Needs list updated!"

    try:
        with open(_needs_file, "r") as _f:
            items = _ubn_json.load(_f)
    except:
        items = []

    current_text = "\n".join(f'{i["emoji"]} {i["label"]}' for i in items)
    preview_rows = "".join(
        f'<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;gap:10px;align-items:center;">'
        f'<span style="font-size:20px;">{i["emoji"]}</span>'
        f'<span style="color:#e5e7eb;">{i["label"]}</span></div>'
        for i in items
    ) or '<p style="color:#94a3b8;">No items yet.</p>'

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Box Needs — EmpowerBands</title>
    <style>
        body{{margin:0;font-family:Arial,sans-serif;background:radial-gradient(circle at top,#0ea5e9 0%,#07111f 35%,#030712 100%);color:white;min-height:100vh;padding:30px 20px;}}
        .page{{max-width:700px;margin:auto;}}
        h1{{font-size:28px;margin-bottom:6px;}}
        .sub{{color:#94a3b8;font-size:14px;margin-bottom:28px;}}
        .card{{background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:26px;margin-bottom:20px;}}
        .card h2{{font-size:17px;font-weight:700;color:#67e8f9;margin-bottom:14px;}}
        textarea{{width:100%;box-sizing:border-box;padding:14px;border:none;border-radius:14px;background:rgba(255,255,255,0.1);color:white;font-size:14px;line-height:1.7;resize:vertical;outline:none;font-family:monospace;}}
        textarea::placeholder{{color:#64748b;}}
        .hint{{font-size:12px;color:#64748b;margin-top:8px;line-height:1.6;}}
        .save-btn{{margin-top:16px;width:100%;padding:15px;border:none;border-radius:14px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;font-size:16px;font-weight:700;cursor:pointer;}}
        .save-btn:hover{{opacity:0.9;}}
        .msg{{background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.4);border-radius:12px;padding:12px 16px;margin-bottom:20px;color:#86efac;font-size:14px;font-weight:600;}}
        .back{{display:inline-block;margin-bottom:22px;padding:10px 18px;border-radius:12px;background:rgba(255,255,255,0.1);color:white;text-decoration:none;font-size:14px;margin-right:10px;}}
        .preview-box{{max-height:320px;overflow-y:auto;}}
    </style>
</head>
<body>
<div class="page">
    <a class="back" href="/dashboard">⬅ Dashboard</a>
    <a class="back" href="/blessing-boxes" target="_blank">👁 View Page</a>
    <h1>📦 Update Blessing Box Needs</h1>
    <p class="sub">Edit the list of items visitors see on the Blessing Boxes page.</p>

    {f'<div class="msg">{message}</div>' if message else ''}

    <div class="card">
        <h2>✏️ Edit Needs List</h2>
        <form method="POST">
            <textarea name="needs_text" rows="14" placeholder="One item per line. Start each line with an emoji, then the item name.&#10;Example:&#10;🥫 Canned Food&#10;🧴 Shampoo">{current_text}</textarea>
            <p class="hint">
                One item per line · Start with an emoji, then a space, then the item name<br>
                Example: <code style="color:#67e8f9;">🥫 Canned Soup</code> &nbsp;|&nbsp; <code style="color:#67e8f9;">🧼 Hand Soap</code>
            </p>
            <button class="save-btn" type="submit">💾 Save & Publish</button>
        </form>
    </div>

    <div class="card">
        <h2>👁 Current List Preview</h2>
        <div class="preview-box">
            {preview_rows}
        </div>
    </div>
</div>
</body>
</html>
"""

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
