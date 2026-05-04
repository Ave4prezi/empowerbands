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

last_alert_sent = {}


# ===============================
# CREATE FILES
# ===============================

if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
       writer = csv.writer(f)
writer.writerow(["band_id", "name", "phone", "emergency_contact", "critical_info", "medical_info", "address", "pin"])
        writer.writerow([
            "EB001",
            "Jordan",
            "email@test.com",
            "+12565551234",
            "Child",
            "Autism – Nonverbal",
            "Please stay calm. I may not respond verbally. Call my caregiver immediately.",
            "No allergies"
        ])

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
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    message = (
        f"🚨 EmpowerBands Alert: {name}'s band was scanned in ALERT MODE. "
        f"They may be lost or unable to communicate. "
        f"Profile: {BASE_URL}/{band_id}?alert=yes"
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
                margin: 0 auto 14px;
                display: block;
            }

            .badge {
                display: inline-block;
                background: #dcebff;
                color: #0a58ca;
                padding: 8px 14px;
                border-radius: 999px;
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 16px;
            }

            h1 {
                font-size: 36px;
                margin: 8px 0;
                color: #0a58ca;
            }

            .lead {
                font-size: 18px;
                line-height: 1.5;
                color: #445;
                margin-bottom: 24px;
            }

            .btn {
                display: block;
                padding: 16px;
                margin: 12px auto;
                max-width: 360px;
                border-radius: 14px;
                text-decoration: none;
                font-size: 17px;
                font-weight: bold;
                background: #0a58ca;
                color: white;
                box-shadow: 0 8px 18px rgba(10,88,202,0.22);
            }

            .btn.dark {
                background: #111827;
            }

            .card {
                background: white;
                border-radius: 20px;
                padding: 22px;
                margin-top: 26px;
                text-align: left;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            }

            .item {
                font-size: 16px;
                margin: 14px 0;
                line-height: 1.4;
            }

            .footer {
                margin-top: 24px;
                color: #667;
                font-size: 13px;
                line-height: 1.4;
            }
        </style>
    </head>

    <body>
        <div class="page">
            <img class="logo" src="https://i.imgur.com/dE4kSOz.png">

            <div class="badge">Emergency Support Wearable</div>

            <h1>EmpowerBands</h1>

            <p class="lead">
                Smart wearable bands that help children with visible and invisible disabilities,
                and elderly individuals with dementia or Alzheimer’s communicate in emergencies.
            </p>

            <a class="btn" href="/EB001">View Live Demo</a>
            <a class="btn dark" href="/admin">Admin Login</a>

            <div class="card">
                <div class="item">🔵 Tap the band with a phone</div>
                <div class="item">🔵 Instantly view support instructions</div>
                <div class="item">🔵 Activate caregiver alerts when needed</div>
                <div class="item">🔵 Call and share location with one tap</div>
            </div>

            <div class="footer">
                Built for families, caregivers, schools, and support organizations.
            </div>
        </div>
    </body>
    </html>
    """


# ===============================
# ADMIN LOGIN
# ===============================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/add")
        return "<h2>Wrong password</h2><p><a href='/admin'>Try again</a></p>"

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #eaf3ff;
            }

            .card {
                max-width: 420px;
                margin: 40px auto;
                background: white;
                padding: 24px;
                border-radius: 18px;
                box-shadow: 0 10px 28px rgba(0,0,0,0.08);
                text-align: center;
            }

            input {
                width: 100%;
                padding: 14px;
                margin: 12px 0;
                font-size: 16px;
                border-radius: 10px;
                border: 1px solid #ccc;
                box-sizing: border-box;
            }

            button {
                width: 100%;
                padding: 15px;
                background: #0a58ca;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 17px;
                font-weight: bold;
            }
        </style>
    </head>

    <body>
        <div class="card">
            <h2>EmpowerBands Admin</h2>
            <form method="POST">
                <input type="password" name="password" placeholder="Enter password">
                <button type="submit">Login</button>
            </form>
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
            request.form["medical_notes"].strip()
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        return redirect("/" + row[0])

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #eaf3ff;
            }

            .card {
                max-width: 430px;
                margin: 20px auto;
                background: white;
                padding: 22px;
                border-radius: 18px;
                box-shadow: 0 10px 28px rgba(0,0,0,0.08);
            }

            h2 {
                text-align: center;
                color: #0a58ca;
            }

            label {
                font-weight: bold;
                font-size: 13px;
                color: #333;
            }

            input, textarea {
                width: 100%;
                padding: 12px;
                margin: 6px 0 14px;
                font-size: 15px;
                border: 1px solid #ccc;
                border-radius: 10px;
                box-sizing: border-box;
            }

            button {
                width: 100%;
                padding: 15px;
                background: #0a58ca;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 17px;
                font-weight: bold;
            }

            .hint {
                font-size: 13px;
                color: #666;
                margin-bottom: 14px;
            }
        </style>
    </head>

    <body>
        <div class="card">
            <h2>Add Profile</h2>
            <p class="hint">For multiple contacts, separate phone numbers with commas.</p>

            <form method="POST">
                <label>Band ID</label>
                <input name="band_id" placeholder="EB002" required>

                <label>Name</label>
                <input name="name" placeholder="Jordan" required>

                <label>Email</label>
                <input name="email" placeholder="parent@email.com">

                <label>Phone(s)</label>
                <input name="phone" placeholder="+12565551234,+12565559876" required>

                <label>Age Group</label>
                <input name="age_group" placeholder="Child / Adult / Senior">

                <label>Condition</label>
                <input name="condition" placeholder="Autism – Nonverbal">

                <label>Instructions</label>
                <textarea name="instructions" rows="3" placeholder="Please stay calm. Call caregiver immediately."></textarea>

                <label>Medical Notes</label>
                <textarea name="medical_notes" rows="3" placeholder="No allergies"></textarea>

                <button type="submit">Save Profile</button>
            </form>
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

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) >= 8 and row[0].strip().upper() == band_id:

                pin = row[7] if len(row) > 7 else "1234"
                entered_pin = request.args.get("pin")

                # ✅ ALERT CONFIRMATION
                if confirm_alert:
                    return f"""
                    <h1>Confirm Emergency Alert</h1>
                    <p>This will notify the emergency contact.</p>

                    <a href="/customer/{band_id}?alert=yes">YES — SEND ALERT</a><br><br>
                    <a href="/customer/{band_id}">Cancel</a>
                    """

                # 🟢 PUBLIC VIEW
                if entered_pin != pin:
                    return f"""
                    <h1>Emergency Access</h1>
                    <p><strong>Name:</strong> {row[1]}</p>

                    <a href="tel:{row[3]}">Call Emergency Contact</a><br><br>

                    <a href="/customer/{band_id}?confirm_alert=yes">
                        Send Emergency Alert
                    </a>

                    <hr>
                    <p>Authorized personnel only</p>
                    <a href="/customer/{band_id}?pin={pin}">
                        Unlock Full Info
                    </a>
                    """

                # 🔴 FULL VIEW
                return f"""
                <h1>Full Emergency Info</h1>

                <p><strong>Name:</strong> {row[1]}</p>
                <p><strong>Phone:</strong> {row[2]}</p>
                <p><strong>Emergency Contact:</strong> {row[3]}</p>
                <p><strong>Medical Info:</strong> {row[4]}</p>

                <a href="tel:{row[3]}">Call Emergency Contact</a>
                """

    return f"""
    <h1>Band Not Found</h1>
    <p>Band ID: {band_id}</p>
    """

                

                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>EmpowerBands Profile</title>
                    <style>
                        * {{
                            -webkit-tap-highlight-color: transparent;
                        }}

                        body {{
                            margin: 0;
                            font-family: Arial, sans-serif;
                            background: #eaf3ff;
                        }}

                        .card {{
                            max-width: 420px;
                            margin: 0 auto;
                            padding: 14px 16px;
                            background: white;
                            min-height: 100vh;
                            display: flex;
                            flex-direction: column;
                            box-sizing: border-box;
                        }}

                        .logo {{
                            text-align: center;
                            margin-bottom: 2px;
                        }}

                        .logo img {{
                            width: 95px;
                            height: auto;
                            display: block;
                            margin: 0 auto;
                            border-radius: 10px;
                        }}

                        .name {{
                            text-align: center;
                            font-size: 25px;
                            font-weight: bold;
                            margin-top: 5px;
                        }}

                        .sub {{
                            text-align: center;
                            color: #0a58ca;
                            font-size: 13px;
                            margin: 2px 0 8px;
                        }}

                        .alert-banner {{
                            background: #d62828;
                            color: white;
                            padding: 11px;
                            border-radius: 12px;
                            text-align: center;
                            margin: 8px 0;
                            font-weight: bold;
                            font-size: 14px;
                            line-height: 1.35;
                        }}

                        .alert {{
                            background: #e0edff;
                            border-left: 5px solid #0a58ca;
                            padding: 11px;
                            border-radius: 12px;
                            margin: 8px 0;
                            font-size: 15px;
                            font-weight: bold;
                        }}

                        .section {{
                            margin-top: 10px;
                        }}

                        .title {{
                            font-size: 12px;
                            font-weight: bold;
                            color: #4a5568;
                            margin-bottom: 4px;
                        }}

                        .text {{
                            font-size: 15px;
                            line-height: 1.35;
                            color: #222;
                        }}

                        .spacer {{
                            flex: 1;
                        }}

                        .alert-btn {{
                            display: block;
                            margin-top: 12px;
                            background: #d62828;
                            color: white;
                            text-align: center;
                            padding: 12px;
                            border-radius: 12px;
                            text-decoration: none;
                            font-weight: bold;
                            font-size: 15px;
                        }}

                        .gps {{
                            margin-top: 8px;
                            background: #111827;
                            color: white;
                            padding: 12px;
                            border-radius: 12px;
                            border: none;
                            width: 100%;
                            font-weight: bold;
                            font-size: 15px;
                        }}

                        .call {{
                            display: block;
                            margin-top: 8px;
                            background: #0a58ca;
                            color: white;
                            text-align: center;
                            padding: 14px;
                            border-radius: 12px;
                            text-decoration: none;
                            font-weight: bold;
                            font-size: 17px;
                        }}

                        .disclaimer {{
                            margin-top: 10px;
                            text-align: center;
                            font-size: 11px;
                            color: #667;
                            line-height: 1.3;
                        }}
                    </style>
                </head>

                <body>
                    <div class="card">
                        <div class="logo">
                            <img src="{LOGO_URL}">
                        </div>

                        <div class="name">{row[1]}</div>
                        <div class="sub">{row[4]} • ID: {row[0]}</div>

                        {alert_banner}

                        <div class="alert">⚠️ {row[5]}</div>

                        <div class="section">
                            <div class="title">WHAT TO DO</div>
                            <div class="text">{row[6]}</div>
                        </div>

                        <div class="section">
                            <div class="title">MEDICAL NOTES</div>
                            <div class="text">{row[7]}</div>
                        </div>

                        <div class="spacer"></div>

                        <a class="alert-btn" href="/{row[0]}?confirm_alert=yes">🚨 Activate Emergency Alert</a>

                        <button class="gps" onclick="shareLocation()">📍 Share Location</button>

                        <a class="call" href="tel:{row[3].split(',')[0].strip()}">📞 CALL NOW</a>

                        <div class="disclaimer">
                            In a life-threatening emergency, call 911 immediately.
                        </div>
                    </div>

                    <script>
                    function shareLocation(){{
                        if (navigator.geolocation) {{
                            navigator.geolocation.getCurrentPosition(function(pos){{
                                let link = "https://maps.google.com/?q=" + pos.coords.latitude + "," + pos.coords.longitude;
                                window.open(link, "_blank");
                            }}, function(){{
                                alert("Location permission was denied.");
                            }});
                        }} else {{
                            alert("Location is not supported on this device.");
                        }}
                    }}
                    </script>
                </body>
                </html>
                """

    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/admin">Admin Login</a></p>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
