from flask import Flask, request, redirect, session, jsonify
from twilio.rest import Client
import csv
import os
import time
import smtplib
from email.mime.text import MIMEText
import qrcode
from io import BytesIO
from werkzeug.utils import secure_filename
from threading import Lock

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

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===============================
# LIVE TRACKING STORE
# ===============================
active_locations = {}
lock = Lock()

# ===============================
# FILE SETUP
# ===============================
header = [
    "band_id","name","email","phone","emergency_phones",
    "emergency_emails","age_group","condition","instructions",
    "medical_notes","pin","address","race","gender","photo_url"
]

if not os.path.exists(file_name):
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)

if not os.path.exists(scan_log_file):
    with open(scan_log_file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["BandID","Name","Time","Type","IP"])

# ===============================
# SOS UI
# ===============================
SOS_STYLE = """
<style>
#sosBtn{
    position:fixed;bottom:22px;right:22px;width:72px;height:72px;
    border-radius:50%;background:radial-gradient(circle,#ef4444,#991b1b);
    color:white;font-weight:900;font-size:12px;z-index:9999;
    display:flex;align-items:center;justify-content:center;
    animation:pulse 1.5s infinite;cursor:pointer;
}
@keyframes pulse{0%{box-shadow:0 0 10px rgba(239,68,68,.4)}
50%{box-shadow:0 0 35px rgba(239,68,68,.9)}100%{box-shadow:0 0 10px rgba(239,68,68,.4)}}
#sosOverlay{position:fixed;inset:0;background:rgba(0,0,0,.75);
display:none;align-items:center;justify-content:center;z-index:10000;}
#sosBox{background:#0b1220;padding:22px;border-radius:18px;width:90%;max-width:420px;text-align:center;}
</style>
"""

SOS_HTML = """
<div id="sosBtn"
onmousedown="holdStart()" ontouchstart="holdStart()"
onmouseup="holdEnd()" ontouchend="holdEnd()"
onclick="openSOS()">SOS<br>ALERT</div>

<div id="sosOverlay">
<div id="sosBox">
<h2 style="color:#ef4444;">Emergency</h2>
<button onclick="triggerSOS()" style="width:100%;padding:14px;border:0;border-radius:12px;background:#dc2626;color:white;">SEND SOS</button>
<button onclick="closeSOS()" style="width:100%;padding:14px;border:0;border-radius:12px;background:#111827;color:white;margin-top:10px;">Cancel</button>
</div>
</div>
"""

SOS_SCRIPT = """
<script>
let currentBandId = window.location.pathname.split("/").pop();
let sosArmed = false;
let holdTimer = null;

function openSOS(){document.getElementById("sosOverlay").style.display="flex";}
function closeSOS(){document.getElementById("sosOverlay").style.display="none";}

function triggerSOS(){
    if(!sosArmed){
        sosArmed=true;
        alert("Confirm again");
        setTimeout(()=>sosArmed=false,3000);
        return;
    }
    sendSOS();
}

function holdStart(){
    holdTimer=setTimeout(()=>sendSOS(),3000);
}
function holdEnd(){
    clearTimeout(holdTimer);
}

function sendSOS(){
    navigator.geolocation.getCurrentPosition(function(pos){
        fetch("/track_update",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                band_id:currentBandId,
                lat:pos.coords.latitude,
                lon:pos.coords.longitude,
                ts:Date.now(),
                alert:true
            })
        }).then(()=> {
            window.location.href="/alert_with_location?band_id="+currentBandId+
            "&lat="+pos.coords.latitude+"&lon="+pos.coords.longitude;
        });
    },function(){
        window.location.href="/"+currentBandId+"?alert=yes";
    });
}
</script>
"""

def inject(html):
    return html.replace("</body>", SOS_STYLE + SOS_HTML + SOS_SCRIPT + "</body>")

# ===============================
# ALERT SYSTEM
# ===============================
def send_full_alert(name, phones, emails, band_id, maps_link=None):
    msg = f"EmpowerBands ALERT\n{name}\nhttps://empowerbands.org/{band_id}\n{maps_link or ''}"
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        for p in str(phones).split(","):
            if p.strip():
                client.messages.create(body=msg, from_=TWILIO_PHONE_NUMBER, to=p)
    except:
        pass

    try:
        m = MIMEText(msg)
        m["Subject"] = f"ALERT {name}"
        m["From"] = ALERT_EMAILS
        m["To"] = emails
        s = smtplib.SMTP("smtp.gmail.com",587)
        s.starttls()
        s.login(ALERT_EMAILS,ALERT_EMAIL_PASSWORD)
        s.sendmail(ALERT_EMAILS,emails,m.as_string())
        s.quit()
    except:
        pass

# ===============================
# TRACKING ENDPOINT
# ===============================
@app.route("/track_update", methods=["POST"])
def track_update():
    data = request.json
    band_id = data.get("band_id")

    if not band_id:
        return jsonify({"ok":False})

    with lock:
        active_locations[band_id] = {
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "ts": data.get("ts"),
            "alert": data.get("alert", False)
        }

    return jsonify({"ok":True})

# ===============================
# ADMIN LOGIN SIMPLE
# ===============================
@app.route("/admin")
def admin():
    html = """
<html>
<body style="background:#020817;color:white;font-family:Arial;">
<h1>Admin Live Dashboard</h1>
<div id="list"></div>

<script>
async function load(){
    let res = await fetch("/admin_data");
    let data = await res.json();

    let html = "";
    for(let id in data){
        let d = data[id];
        html += `<div style='padding:10px;margin:10px;background:#111827;border-radius:10px'>
        <b>${id}</b><br>
        Lat: ${d.lat}<br>
        Lon: ${d.lon}<br>
        Alert: ${d.alert}<br>
        </div>`;
    }
    document.getElementById("list").innerHTML = html;
}

setInterval(load,3000);
load();
</script>
</body>
</html>
"""
    return inject(html)

@app.route("/admin_data")
def admin_data():
    return jsonify(active_locations)

# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    return inject("""
<html><body style="background:#020817;color:white;">
<h1>EmpowerBands</h1>
<a href="/admin">Admin Dashboard</a>
</body></html>
""")

# ===============================
# PROFILE PAGE
# ===============================
@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.upper()

    with open(file_name,"r",encoding="utf-8") as f:
        r = csv.reader(f)
        next(r,None)
        for row in r:
            if row and row[0]==band_id:
                name=row[1]
                email=row[2]
                phone=row[3]

                html=f"""
<html>
<body style="background:#0b1220;color:white;">
<h1>{name}</h1>
<p>{email}</p>
<p>{phone}</p>

<p>Live tracking active...</p>

<script>
setInterval(()=>{
    navigator.geolocation.getCurrentPosition(pos=>{
        fetch("/track_update",{
            method:"POST",
            headers:{{"Content-Type":"application/json"}},
            body:JSON.stringify({{
                band_id:"{band_id}",
                lat:pos.coords.latitude,
                lon:pos.coords.longitude,
                ts:Date.now()
            }})
        });
    });
},5000);
</script>

</body></html>
"""
                return inject(html)

    return "Not found"

# ===============================
# ALERT ROUTE
# ===============================
@app.route("/alert_with_location")
def alert_with_location():
    band_id = request.args.get("band_id","")
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    link = f"https://maps.google.com/?q={lat},{lon}"

    send_full_alert("User","", "", band_id, link)

    return "Alert Sent"

if __name__ == "__main__":
    app.run(debug=True)
