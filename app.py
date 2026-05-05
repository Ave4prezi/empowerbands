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
    "Jordan",
    "email@test.com",
    "+12565551234,+12565550000",
    "Child",
    "Autism – Nonverbal",
    "Please stay calm. I may not respond verbally. Call my caregiver immediately.",
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

            <a class="btn" href="/customer/EB001">View Live Demo</a>
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


# Old short link support: /EB001 redirects to /customer/EB001
@app.route("/<band_id>")
def old_band_link(band_id):
    if band_id.lower() in ["admin", "add", "alert_with_location"]:
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
        return "<h2>Wrong password</h2><p><a href='/admin'>Try again</a></p>"

    return """
    <h1>EmpowerBands Admin</h1>
    <form method="POST">
        <input type="password" name="password" placeholder="Enter password">
        <button type="submit">Login</button>
    </form>
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
    <h1>Add Profile</h1>

    <form method="POST">
        <p><input name="band_id" placeholder="EB002" required></p>
        <p><input name="name" placeholder="Name" required></p>
        <p><input name="email" placeholder="Email"></p>
        <p><input name="phone" placeholder="+12565551234" required></p>
        <p><input name="age_group" placeholder="Child / Adult / Senior"></p>
        <p><input name="condition" placeholder="Public condition, example: Nonverbal"></p>
        <p><textarea name="instructions" placeholder="Public instructions"></textarea></p>
        <p><textarea name="medical_notes" placeholder="Private medical notes"></textarea></p>
        <p><input name="pin" placeholder="PIN, example: 1234" required></p>

        <button type="submit">Save Profile</button>
    </form>
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
                entered_pin = request.args.get("pin")

                log_scan(band_id, name, "scan", request.remote_addr)

                if alert_mode:
                    send_alert_text(name, phone, band_id)
                    return f"""
                    <h1>✅ Alert Sent</h1>
                    <p>Emergency contact has been notified.</p>
                    <p><a href="/customer/{band_id}">Go Back</a></p>
                    """

                if confirm_alert:
                    return f"""
                    <html>
                    <head>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{
                                margin: 0;
                                font-family: Arial;
                                background: #f3f4f6;
                                text-align: center;
                                padding: 30px;
                            }}
                            .box {{
                                background: white;
                                padding: 25px;
                                border-radius: 16px;
                                max-width: 420px;
                                margin: auto;
                                box-shadow: 0 10px 30px rgba(0,0,0,.08);
                            }}
                            .btn {{
                                display: block;
                                padding: 15px;
                                margin-top: 15px;
                                border-radius: 12px;
                                text-decoration: none;
                                font-weight: bold;
                                border: none;
                                width: 100%;
                                font-size: 16px;
                                box-sizing: border-box;
                            }}
                            .alert {{
                                background: #dc2626;
                                color: white;
                            }}
                            .cancel {{
                                background: #111827;
                                color: white;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="box">
                            <img src="{LOGO_URL}" width="95">
                            <h2>Confirm Emergency Alert</h2>
                            <p>This will send a text alert to the caregiver with location if allowed.</p>

                            <button class="btn alert" onclick="sendAlertWithLocation()">
                                🚨 Send Emergency Alert
                            </button>

                            <a class="btn cancel" href="/customer/{band_id}">
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
                    <html>
                    <head>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{ margin:0; font-family:Arial; background:#f3f4f6; }}
                            .container {{ max-width:430px; margin:auto; padding:20px; }}
                            .card {{ background:white; border-radius:18px; padding:22px; box-shadow:0 10px 30px rgba(0,0,0,.08); }}
                            .header {{ text-align:center; }}
                            .logo {{ width:90px; }}
                            h1 {{ font-size:24px; margin:12px 0 4px; color:#111827; }}
                            .sub {{ color:#0a58ca; font-weight:bold; }}
                            .warning {{ background:#fee2e2; color:#991b1b; padding:12px; border-radius:12px; margin-top:18px; font-weight:bold; }}
                            .section {{ margin-top:18px; }}
                            .label {{ font-size:12px; font-weight:bold; color:#6b7280; text-transform:uppercase; }}
                            .value {{ font-size:16px; margin-top:5px; color:#111827; line-height:1.4; }}
                            .btn {{ display:block; padding:15px; border-radius:12px; text-align:center; text-decoration:none; font-weight:bold; margin-top:12px; }}
                            .call {{ background:#0a58ca; color:white; }}
                            .back {{ background:#111827; color:white; }}
                        </style>
                    </head>

                    <body>
                        <div class="container">
                            <div class="card">
                                <div class="header">
                                    <img class="logo" src="{LOGO_URL}">
                                    <h1>Full Emergency Info</h1>
                                    <div class="sub">{name} • ID: {band_id}</div>
                                </div>

                                <div class="warning">
                                    Authorized access only. Use this information to assist safely.
                                </div>

                                <div class="section">
                                    <div class="label">Name</div>
                                    <div class="value">{name}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Email</div>
                                    <div class="value">{email}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Emergency Contact</div>
                                    <div class="value">{phone}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Age Group</div>
                                    <div class="value">{age_group}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Condition</div>
                                    <div class="value">{condition}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Instructions</div>
                                    <div class="value">{instructions}</div>
                                </div>

                                <div class="section">
                                    <div class="label">Medical Notes</div>
                                    <div class="value">{medical_notes}</div>
                                </div>

                                <a class="btn call" href="tel:{phone.split(',')[0].strip()}">📞 Call Emergency Contact</a>
                                <a class="btn back" href="/customer/{band_id}">Back to Public View</a>
                            </div>
                        </div>
                    </body>
                    </html>
                    """

                return f"""
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ margin:0; font-family:Arial; background:#f3f4f6; }}
                        .container {{ max-width:420px; margin:auto; padding:20px; }}
                        .header {{ text-align:center; margin-top:10px; }}
                        .name {{ font-size:30px; font-weight:bold; margin-top:8px; }}
                        .sub {{ color:#0a58ca; font-size:16px; margin-top:4px; }}
                        .badge {{ background:#dbeafe; padding:15px; border-radius:14px; margin-top:22px; font-weight:bold; font-size:18px; border-left:6px solid #0a58ca; }}
                        .section {{ margin-top:22px; }}
                        .title {{ font-weight:bold; color:#4b5563; margin-bottom:8px; font-size:14px; }}
                        .text {{ font-size:17px; line-height:1.45; color:#111827; }}
                        .btn {{ display:block; width:100%; padding:17px; border-radius:14px; text-align:center; text-decoration:none; font-weight:bold; margin-top:14px; border:none; font-size:17px; box-sizing:border-box; }}
                        .alert {{ background:#dc2626; color:white; }}
                        .gps {{ background:#111827; color:white; }}
                        .unlock {{ margin-top:22px; background:white; padding:16px; border-radius:16px; box-shadow:0 8px 24px rgba(0,0,0,.06); }}
                        input {{ width:100%; padding:13px; border-radius:10px; border:1px solid #ccc; margin-top:8px; box-sizing:border-box; font-size:16px; }}
                        .unlock-btn {{ margin-top:10px; width:100%; padding:13px; border-radius:10px; border:none; background:#0a58ca; color:white; font-weight:bold; font-size:16px; }}
                    </style>
                </head>

                <body>
                    <div class="container">
                        <div class="header">
                            <img src="{LOGO_URL}" width="95">
                            <div class="name">{name}</div>
                            <div class="sub">{age_group} • ID: {band_id}</div>
                        </div>

                        <div class="badge">⚠️ {condition}</div>

                        <div class="section">
                            <div class="title">WHAT TO DO</div>
                            <div class="text">{instructions}</div>
                        </div>

                        <div class="section">
                            <div class="title">MEDICAL NOTES</div>
                            <div class="text">{medical_notes}</div>
                        </div>

                        <a class="btn alert" href="/customer/{band_id}?confirm_alert=yes">
                            🚨 Activate Emergency Alert
                        </a>

                        <button class="btn gps" onclick="shareLocation()">
                            📍 Share Location
                        </button>

                        <div class="unlock">
                            <form method="GET" action="/customer/{band_id}">
                                <strong>Authorized Access</strong>
                                <input type="password" name="pin" placeholder="Enter PIN">
                                <button class="unlock-btn" type="submit">Unlock Full Info</button>
                            </form>
                        </div>
                    </div>

                    <script>
                    function shareLocation(){{
                        if (navigator.geolocation) {{
                            navigator.geolocation.getCurrentPosition(function(pos){{
                                let lat = pos.coords.latitude;
                                let lon = pos.coords.longitude;
                                let link = "https://maps.google.com/?q=" + lat + "," + lon;
                                window.open(link, "_blank");
                            }}, function(){{
                                alert("Location permission denied.");
                            }});
                        }} else {{
                            alert("Location not supported.");
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
                <p>Location and profile were sent to caregiver.</p>
                <p><a href="/customer/{band_id}">Go Back</a></p>
                """

    return "<h1>Error sending alert</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
