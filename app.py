import os
import time
import json
import sqlite3

import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText

# =========================
# APP SETUP
# =========================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "empowerbands-secret")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet"
)

# =========================
# OPTIONAL REDIS (SAFE FALLBACK)
# =========================
try:
    import redis
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=True
    )
except:
    redis_client = None

# =========================
# DATABASE
# =========================
DB = "empowerbands.db"
active_alerts = {}

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        band_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        band_id TEXT,
        lat REAL,
        lon REAL,
        ts INTEGER,
        alert INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        band_id TEXT,
        lat REAL,
        lon REAL,
        ts INTEGER,
        type TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# ENV
# =========================
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER")

ALERT_EMAIL = os.environ.get("ALERT_EMAILS")
ALERT_EMAIL_PASS = os.environ.get("ALERT_EMAIL_PASSWORD")

BASE_URL = os.environ.get("BASE_URL", "https://empowerbands.org")

# =========================
# NOTIFICATIONS
# =========================
def send_sms(phone, message):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone
        )
    except:
        pass

def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = ALERT_EMAIL
        msg["To"] = to_email

        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(ALERT_EMAIL, ALERT_EMAIL_PASS)
        s.sendmail(ALERT_EMAIL, to_email, msg.as_string())
        s.quit()
    except:
        pass

# =========================
# SOS CORE
# =========================
def trigger_sos(band_id, lat, lon):
    ts = int(time.time())

    conn = db()
    c = conn.cursor()

    c.execute(
        "INSERT INTO alerts (band_id, lat, lon, ts, type) VALUES (?, ?, ?, ?, ?)",
        (band_id, lat, lon, ts, "SOS")
    )

    conn.commit()
    conn.close()

    payload = {
        "band_id": band_id,
        "lat": lat,
        "lon": lon,
        "ts": ts,
        "type": "SOS"
    }

    # Redis OR fallback memory
    if redis_client:
        redis_client.set(f"live:{band_id}", json.dumps(payload))
    else:
        active_alerts[band_id] = payload

    socketio.emit("sos_event", payload)

    msg = f"EMERGENCY ALERT\n{BASE_URL}/{band_id}\nLocation: {lat},{lon}"

    # notify user if exists
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE band_id=?", (band_id,))
    user = c.fetchone()
    conn.close()

    if user:
        if user["phone"]:
            send_sms(user["phone"], msg)
        if user["email"]:
            send_email(user["email"], "EMERGENCY ALERT", msg)

# =========================
# TRACK LOCATION (LIVE)
# =========================
@app.route("/track", methods=["POST"])
def track():
    data = request.json or {}

    band_id = data.get("band_id")
    lat = data.get("lat")
    lon = data.get("lon")
    alert = data.get("alert", 0)

    if not band_id:
        return jsonify({"error": "missing band_id"}), 400

    ts = int(time.time())

    conn = db()
    c = conn.cursor()

    c.execute(
        "INSERT INTO locations (band_id, lat, lon, ts, alert) VALUES (?, ?, ?, ?, ?)",
        (band_id, lat, lon, ts, alert)
    )

    conn.commit()
    conn.close()

    payload = {
        "band_id": band_id,
        "lat": lat,
        "lon": lon,
        "ts": ts,
        "alert": alert
    }

    if redis_client:
        redis_client.set(f"live:{band_id}", json.dumps(payload))
    else:
        active_alerts[band_id] = payload

    socketio.emit("location_update", payload)

    if alert:
        trigger_sos(band_id, lat, lon)

    return jsonify({"ok": True})

# =========================
# SOS API
# =========================
@app.route("/sos", methods=["POST"])
def sos():
    data = request.json or {}

    band_id = data.get("band_id")
    lat = data.get("lat")
    lon = data.get("lon")

    if not band_id:
        return jsonify({"error": "missing band_id"}), 400

    trigger_sos(band_id, float(lat), float(lon))

    return jsonify({"ok": True})

# =========================
# ALERT WITH LOCATION (FIXED)
# =========================
@app.route("/alert_with_location")
def alert_with_location():
    band_id = request.args.get("band_id")
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not band_id or not lat or not lon:
        return jsonify({"error": "missing data"}), 400

    trigger_sos(band_id, float(lat), float(lon))

    return jsonify({
        "status": "alert sent",
        "band_id": band_id
    })

# =========================
# LIVE LOCATION (OPTIONAL EXTRA)
# =========================
@app.route("/live_location", methods=["POST"])
def live_location():
    data = request.json or {}

    band_id = data.get("band_id")
    lat = data.get("lat")
    lon = data.get("lon")

    if band_id:
        payload = {
            "band_id": band_id,
            "lat": lat,
            "lon": lon,
            "time": time.time()
        }

        if redis_client:
            redis_client.set(f"live:{band_id}", json.dumps(payload))
        else:
            active_alerts[band_id] = payload

        socketio.emit("update_location", payload)

    return jsonify({"ok": True})

# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin")
def admin():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Live Dashboard</title>
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body style="background:#0b1220;color:white;font-family:Arial;">

<h1>Live Tracking Dashboard</h1>
<div id="events"></div>

<script>
const socket = io();

socket.on("location_update", (data) => {
    let div = document.createElement("div");
    div.style.padding = "10px";
    div.style.margin = "10px";
    div.style.background = "#111827";
    div.innerHTML = `
        <b>${data.band_id}</b><br>
        ${data.lat}, ${data.lon}<br>
        ${new Date(data.ts*1000).toLocaleTimeString()}
    `;
    document.getElementById("events").prepend(div);
});

socket.on("sos_event", (data) => {
    let div = document.createElement("div");
    div.style.padding = "12px";
    div.style.margin = "10px";
    div.style.background = "#7f1d1d";
    div.innerHTML = `
        <b>🚨 SOS ${data.band_id}</b><br>
        ${data.lat}, ${data.lon}<br>
        ${new Date(data.ts*1000).toLocaleTimeString()}
    `;
    document.getElementById("events").prepend(div);
});
</script>

</body>
</html>
"""

# =========================
# SIMPLE PROFILE
# =========================
@app.route("/<band_id>")
def profile(band_id):
    return f"""
<html>
<body style="background:#0b1220;color:white;">
<h1>{band_id}</h1>

<script>
setInterval(() => {{
    navigator.geolocation.getCurrentPosition(pos => {{
        fetch("/track", {{
            method:"POST",
            headers:{{"Content-Type":"application/json"}},
            body:JSON.stringify({{
                band_id:"{band_id}",
                lat:pos.coords.latitude,
                lon:pos.coords.longitude
            }})
        }});
    }});
}}, 5000);
</script>

</body>
</html>
"""

# =========================
# HOME (FIX FOR 404)
# =========================
@app.route("/")
def home():
    return "EmpowerBands Running"

# =========================
# RUN (RENDER SAFE)
# =========================
if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
)
