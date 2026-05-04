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

# ===============================
# CREATE FILES
# ===============================

# Create customers file if missing
if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "band_id","name","email","phone","age_group",
            "condition","instructions","medical_notes","pin"
        ])

# Always make sure demo band exists
with open(file_name, "r+", newline="", encoding="utf-8") as f:
    rows = list(csv.reader(f))
    existing_ids = [r[0] for r in rows if r]

    if "EB001" not in existing_ids:
        writer = csv.writer(f)
        writer.writerow([
            "EB001",
            "Jordan",
            "email@test.com",
            "+12565551234,+12565550000",
            "Child",
            "Autism – Nonverbal",
            "Please stay calm. I may not respond verbally. Call my caregiver immediately.",
            "No allergies",
            "1234"
        ])

# Create scan log file if missing
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
    <h1>EmpowerBands</h1>
    <p>System is running.</p>
    <p><a href="/customer/EB001">View Demo Band</a></p>
    <p><a href="/admin">Admin Login</a></p>
    """


# Old short link support: /EB001 redirects to /customer/EB001
@app.route("/<band_id>")
def old_band_link(band_id):
    if band_id.lower() in ["admin", "add"]:
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
                    <h1>Confirm Emergency Alert</h1>
                    <p>This will send an emergency text alert to the caregiver contact.</p>
                    <p>Only continue if this person may be lost, confused, or unable to communicate.</p>

                    <p>
                        <button onclick="sendAlertWithLocation()">🚨 Send Emergency Alert</button>
                    </p>

                    <p>
                        <a href="/customer/{band_id}">Cancel</a>
                    </p>

                    <script>
                    function sendAlertWithLocation(){{
                        if (navigator.geolocation) {{
                            navigator.geolocation.getCurrentPosition(function(pos){{

                                let lat = pos.coords.latitude;
                                let lon = pos.coords.longitude;

                                window.location.href = "/alert_with_location?band_id={band_id}&lat=" + lat + "&lon=" + lon;

                            }}, function(){{
                                alert("Location permission denied.");
                            }});
                        }} else {{
                            alert("Location not supported.");
                        }}
                    }}
                    </script>
                    """

                if entered_pin != pin:
                    return f"""
                    <h1>Emergency Access</h1>
                    <p><strong>Name:</strong> {name}</p>
                    <p><strong>Condition:</strong> {condition}</p>
                    <p><strong>What To Do:</strong> {instructions}</p>

                    <p><a href="tel:{phone.split(',')[0].strip()}">📞 Call Emergency Contact</a></p>
                    <p><a href="/customer/{band_id}?confirm_alert=yes">🚨 Send Emergency Alert</a></p>

                    <hr>
                    <p><strong>Authorized personnel only</strong></p>
                    <form method="GET" action="/customer/{band_id}">
                        <input type="password" name="pin" placeholder="Enter PIN">
                        <button type="submit">Unlock Full Info</button>
                    </form>
                    """

                return f"""
                <h1>Full Emergency Info</h1>
                <p><strong>Name:</strong> {name}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Emergency Contact:</strong> {phone}</p>
                <p><strong>Age Group:</strong> {age_group}</p>
                <p><strong>Condition:</strong> {condition}</p>
                <p><strong>Instructions:</strong> {instructions}</p>
                <p><strong>Medical Notes:</strong> {medical_notes}</p>

                <p><a href="tel:{phone.split(',')[0].strip()}">📞 Call Emergency Contact</a></p>
                <p><a href="/customer/{band_id}">Back to Public View</a></p>
                """

    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/admin">Admin Login</a></p>
    """


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
                                body=f"🚨 EmpowerBands Alert: {name} may need help.\n📍 Location: {location_link}\nProfile: {BASE_URL}/customer/{band_id}",
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

