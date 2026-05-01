from flask import Flask, request, redirect, session
from twilio.rest import Client
import csv
import os
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")
file_name = "customers.csv"

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.onrender.com")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

LOGO_URL = "https://i.imgur.com/dE4kSOz.png"

last_alert_sent = {}


def send_alert_text(name, phones, band_id):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        print("Twilio not configured.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message_body = (
            f"🚨 EmpowerBands Alert: {name}'s band was scanned in ALERT MODE. "
            f"They may be lost or unable to communicate. "
            f"Profile: {BASE_URL}/{band_id}?alert=yes"
        )

        phone_list = [p.strip() for p in phones.split(",") if p.strip()]

        for phone in phone_list:
            client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=phone
            )
            print(f"Alert text sent to {phone}")

    except Exception as e:
        print(f"Twilio error: {e}")


if not os.path.exists(file_name):
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "BandID", "Name", "Email", "Phone",
            "AgeGroup", "Condition", "Instructions", "MedicalNotes"
        ])
        writer.writerow([
            "EB001", "Jordan", "parent@email.com", "+12565551234",
            "Child", "Autism – Nonverbal",
            "Please stay calm. I may not respond verbally. Call emergency contact immediately.",
            "No allergies"
        ])


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
                background: #f4f8ff;
                color: #111;
            }
            .hero {
                max-width: 520px;
                margin: auto;
                padding: 42px 22px;
                text-align: center;
            }
            .badge {
                display: inline-block;
                background: #e0edff;
                color: #0a58ca;
                padding: 8px 12px;
                border-radius: 999px;
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 18px;
            }
            h1 {
                font-size: 36px;
                margin: 10px 0;
                color: #0a58ca;
            }
            .lead {
                font-size: 19px;
                line-height: 1.45;
                color: #444;
            }
            .btn {
                display: block;
                margin: 14px auto;
                padding: 16px;
                background: #0a58ca;
                color: white;
                text-decoration: none;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
                max-width: 360px;
            }
            .btn.secondary {
                background: #111;
            }
            .card {
                background: white;
                border-radius: 18px;
                padding: 20px;
                margin-top: 26px;
                text-align: left;
                box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            }
            .item {
                margin: 14px 0;
                font-size: 16px;
                line-height: 1.4;
            }
            .footer {
                margin-top: 26px;
                font-size: 13px;
                color: #666;
            }
        </style>
    </head>

    <body>
        <div class="hero">
            <div class="badge">Emergency Support Wearable</div>

            <h1>EmpowerBands</h1>

            <p class="lead">
                Smart wearable bands that help children with visible and invisible disabilities,
                and elderly individuals with dementia or Alzheimer’s communicate in emergencies.
            </p>

            <a class="btn" href="/EB001">View Live Demo</a>
            <a class="btn" href="/EB001?alert=yes">Alert Mode Demo</a>
            <a class="btn secondary" href="/admin">Admin Login</a>

            <div class="card">
                <div class="item">🔵 Tap the band with a phone</div>
                <div class="item">🔵 Instantly view the person’s support profile</div>
                <div class="item">🔵 Activate emergency alert when needed</div>
                <div class="item">🔵 Call the caregiver with one tap</div>
            </div>

            <div class="footer">
                Built for families, caregivers, schools, and support organizations.
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/add")
        return "Wrong password"

    return """
    <h2>Admin Login</h2>
    <form method="POST">
        <input type="password" name="password" placeholder="Password">
        <button type="submit">Login</button>
    </form>
    """


@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        new_row = [
            request.form["band_id"].strip().upper(),
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["phone"].strip(),
            request.form["age_group"].strip(),
            request.form["condition"].strip(),
            request.form["instructions"].strip(),
            request.form["medical_notes"].strip()
        ]

        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(new_row)

        return redirect("/" + new_row[0])

    return """
    <h2>Add Profile</h2>
    <p>Use phone format like +12565551234 for texting.</p>
    <form method="POST">
        ID: <input name="band_id" placeholder="EB002"><br>
        Name: <input name="name"><br>
        Email: <input name="email"><br>
       Phone(s): <input name="phone" placeholder="+12565551234,+12565559876"><br>
        Age: <input name="age_group"><br>
        Condition: <input name="condition"><br>
        Instructions: <input name="instructions"><br>
        Notes: <input name="medical_notes"><br>
        <button type="submit">Save</button>
    </form>
    """


@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.strip().upper()
    alert_mode = request.args.get("alert") == "yes"

    with open(file_name, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        for row in reader:
            if len(row) >= 8 and row[0].strip().upper() == band_id:

                if alert_mode:
                    now = time.time()
                    last_time = last_alert_sent.get(band_id, 0)

                    if now - last_time > 300:
                        send_alert_text(row[1], row[3], row[0])
                        last_alert_sent[band_id] = now

                alert_banner = ""
                if alert_mode:
                    alert_banner = """
                    <div class="alert-banner">
                        🚨 ALERT MODE 🚨<br>
                        This person may be lost or unable to communicate.<br>
                        Stay with them and call immediately.
                    </div>
                    """

                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>EmpowerBands Profile</title>
                <style>
                body {{
                    margin:0;
                    font-family:Arial, sans-serif;
                    background:#eaf3ff;
                }}

                .card {{
                    max-width:420px;
                    margin:0 auto;
                    padding:16px;
                    background:white;
                    min-height:100vh;
                    display:flex;
                    flex-direction:column;
                    box-sizing:border-box;
                }}

                .logo {{
                    text-align:center;
                    margin-bottom:2px;
                }}

                .logo img {{
                    width:90px;
                    height:auto;
                    display:block;
                    margin:0 auto;
                }}

                .name {{
                    text-align:center;
                    font-size:24px;
                    font-weight:bold;
                    margin-top:4px;
                }}

                .sub {{
                    text-align:center;
                    color:#0a58ca;
                    font-size:13px;
                    margin-bottom:6px;
                }}

                .alert-banner {{
                    background:#d62828;
                    color:white;
                    padding:10px;
                    border-radius:10px;
                    text-align:center;
                    margin:8px 0;
                    font-weight:bold;
                    font-size:14px;
                    line-height:1.35;
                }}

                .alert {{
                    background:#e0edff;
                    border-left:4px solid #0a58ca;
                    padding:10px;
                    border-radius:10px;
                    margin:8px 0;
                    font-size:15px;
                    font-weight:bold;
                }}

                .section {{
                    margin-top:10px;
                }}

                .title {{
                    font-size:12px;
                    font-weight:bold;
                    color:#444;
                    margin-bottom:3px;
                }}

                .text {{
                    font-size:15px;
                    line-height:1.35;
                    color:#222;
                }}

                .alert-btn {{
                    display:block;
                    margin-top:12px;
                    background:#d62828;
                    color:white;
                    text-align:center;
                    padding:12px;
                    border-radius:10px;
                    text-decoration:none;
                    font-weight:bold;
                    font-size:15px;
                }}

                .gps {{
                    margin-top:8px;
                    background:#111;
                    color:white;
                    padding:11px;
                    border-radius:10px;
                    border:none;
                    width:100%;
                    font-weight:bold;
                    font-size:15px;
                }}

                .call {{
                    margin-top:auto;
                    background:#0a58ca;
                    color:white;
                    text-align:center;
                    padding:14px;
                    border-radius:10px;
                    text-decoration:none;
                    font-weight:bold;
                    font-size:17px;
                }}

                .notes {{
                    margin-bottom:12px;
                }}
                </style>
                </head>

                <body>

                <div class="card">

                    <div class="logo">
                        <img src="{LOGO_URL}">
                    </div>

                    <div class="name">{row[1]}</div>
                    <div class="sub">{row[4]} • {row[0]}</div>

                    {alert_banner}

                    <div class="alert">⚠️ {row[5]}</div>

                    <div class="section">
                        <div class="title">WHAT TO DO</div>
                        <div class="text">{row[6]}</div>
                    </div>

                    <div class="section notes">
                        <div class="title">MEDICAL NOTES</div>
                        <div class="text">{row[7]}</div>
                    </div>

                    <a class="alert-btn" href="/{row[0]}?alert=yes">🚨 Activate Emergency Alert</a>

                    <button class="gps" onclick="shareLocation()">📍 Share Location</button>

                    <a class="call" href="tel:{row[3]}">📞 CALL NOW</a>

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

    return "Band not found"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
