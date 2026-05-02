from flask import Flask, request, redirect, session
from twilio.rest import Client
import csv
import os
import time

app = Flask(__name__)
app.secret_key = "empowerbands-secret"

ADMIN_PASSWORD = "empower123"

file_name = "customers.csv"
scan_log_file = "scan_log.csv"

BASE_URL = os.environ.get("BASE_URL")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

LOGO_URL = "https://i.imgur.com/dE4kSOz.png"

last_alert_sent = {}

# ------------------ CREATE FILES ------------------

if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["BandID","Name","Email","Phone","AgeGroup","Condition","Instructions","MedicalNotes"])
        writer.writerow(["EB001","Jordan","email@test.com","+12565551234","Child","Autism","Stay calm and call caregiver","None"])

if not os.path.exists(scan_log_file):
    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["BandID","Name","Time","Type","IP"])

# ------------------ FUNCTIONS ------------------

def log_scan(band_id, name, scan_type, ip):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(scan_log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([band_id, name, now, scan_type, ip])

def send_alert_text(name, phones, band_id):
    if not TWILIO_ACCOUNT_SID:
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    message = f"🚨 ALERT: {name}'s band was scanned. {BASE_URL}/{band_id}?alert=yes"

    for phone in phones.split(","):
        client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone.strip()
        )

# ------------------ ROUTES ------------------

@app.route("/")
def home():
    return '<h1>EmpowerBands</h1><a href="/EB001">Demo</a>'

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/add")
        return "Wrong password"

    return '''
    <form method="POST">
    <input type="password" name="password">
    <button>Login</button>
    </form>
    '''

@app.route("/add", methods=["GET","POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        row = [
            request.form["band_id"].upper(),
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form["age_group"],
            request.form["condition"],
            request.form["instructions"],
            request.form["medical_notes"]
        ]

        with open(file_name, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        return redirect("/" + row[0])

    return '''
    <h2>Add Profile</h2>
    Phone(s): <input name="phone" placeholder="+1256xxxx,+1256xxxx"><br>
    <form method="POST">
    ID: <input name="band_id"><br>
    Name: <input name="name"><br>
    Email: <input name="email"><br>
    Phone(s): <input name="phone"><br>
    Age: <input name="age_group"><br>
    Condition: <input name="condition"><br>
    Instructions: <input name="instructions"><br>
    Notes: <input name="medical_notes"><br>
    <button>Save</button>
    </form>
    '''

@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.upper()
    alert_mode = request.args.get("alert") == "yes"
    confirm_alert = request.args.get("confirm_alert") == "yes"

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)

        for row in reader:
            if row[0] == band_id:

                # CONFIRM SCREEN
                if confirm_alert:
                    return f'''
                    <h2>Confirm Alert</h2>
                    <p>This will notify caregivers.</p>
                    <a href="/{band_id}?alert=yes">YES</a><br>
                    <a href="/{band_id}">Cancel</a>
                    '''

                # LOG SCAN
                scan_type = "ALERT" if alert_mode else "SCAN"
                log_scan(row[0], row[1], scan_type, request.remote_addr)

                # SEND ALERT
                if alert_mode:
                    now = time.time()
                    if now - last_alert_sent.get(band_id, 0) > 300:
                        send_alert_text(row[1], row[3], band_id)
                        last_alert_sent[band_id] = now

                alert_banner = "<h3 style='color:red'>🚨 ALERT MODE</h3>" if alert_mode else ""

                return f'''
                <html>
                <body style="font-family:Arial;background:#eef">

                <div style="max-width:400px;margin:auto;background:white;padding:15px">

                <img src="{LOGO_URL}" width="80"><br>

                <h2>{row[1]}</h2>
                <p>{row[4]} • {row[0]}</p>

                {alert_banner}

                <p><b>{row[5]}</b></p>

                <p>{row[6]}</p>

                <a href="/{band_id}?confirm_alert=yes" style="color:white;background:red;padding:10px;display:block">🚨 Alert</a>

                <button onclick="share()">📍 Share Location</button>

                <a href="tel:{row[3]}" style="background:blue;color:white;padding:10px;display:block">Call</a>

                </div>

                <script>
                function share(){{
                    navigator.geolocation.getCurrentPosition(p=>{
                        window.open("https://maps.google.com/?q="+p.coords.latitude+","+p.coords.longitude)
                    })
                }}
                </script>

                </body>
                </html>
                '''

    return "Not found"

if __name__ == "__main__":
    app.run()
