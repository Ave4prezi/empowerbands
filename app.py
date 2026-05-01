from flask import Flask, request, redirect, session
import csv
import os

app = Flask(__name__)
app.secret_key = "empowerbands-secret"

ADMIN_PASSWORD = "empower123"
file_name = "customers.csv"

# Create CSV if it doesn't exist
if not os.path.exists(file_name):
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "BandID","Name","Email","Phone",
            "AgeGroup","Condition","Instructions","MedicalNotes"
        ])
        writer.writerow([
            "EB001","Jordan","parent@email.com","2565551234",
            "Child","Autism – Nonverbal",
            "Please stay calm. I may not respond verbally.",
            "Call emergency contact immediately."
        ])

# HOME PAGE
@app.route("/")
def home():
    return """
    <h1>EmpowerBands</h1>
    <p><a href="/EB001">Live Demo</a></p>
    <p><a href="/admin">Admin Login</a></p>
    """

# ADMIN LOGIN
@app.route("/admin", methods=["GET","POST"])
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

# ADD PERSON
@app.route("/add", methods=["GET","POST"])
def add():
    if not session.get("logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        new_row = [
            request.form["band_id"].upper(),
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form["age_group"],
            request.form["condition"],
            request.form["instructions"],
            request.form["medical_notes"]
        ]

        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(new_row)

        return redirect("/" + new_row[0])

    return """
    <h2>Add Profile</h2>
    <form method="POST">
        ID: <input name="band_id"><br>
        Name: <input name="name"><br>
        Email: <input name="email"><br>
        Phone: <input name="phone"><br>
        Age: <input name="age_group"><br>
        Condition: <input name="condition"><br>
        Instructions: <input name="instructions"><br>
        Notes: <input name="medical_notes"><br>
        <button type="submit">Save</button>
    </form>
    """

# PROFILE PAGE
@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.upper()
    alert_mode = request.args.get("alert") == "yes"

    with open(file_name, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)

        for row in reader:
            if len(row) >= 8 and row[0].upper() == band_id:

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
                <style>
                body {{
                    margin:0;
                    font-family:Arial;
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
                }}

                .logo {{
                    text-align:center;
                }}

                .logo img {{
                    width:90px;
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
                    background:red;
                    color:white;
                    padding:10px;
                    border-radius:10px;
                    text-align:center;
                    margin:8px 0;
                }}

                .alert {{
                    background:#e0edff;
                    border-left:4px solid #0a58ca;
                    padding:10px;
                    border-radius:10px;
                    margin:8px 0;
                }}

                .section {{
                    margin-top:10px;
                }}

                .title {{
                    font-size:12px;
                    font-weight:bold;
                }}

                .text {{
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
                }}

                .gps {{
                    margin-top:8px;
                    background:black;
                    color:white;
                    padding:10px;
                    border-radius:10px;
                    border:none;
                    width:100%;
                }}
                </style>
                </head>

                <body>

                <div class="card">

                    <div class="logo">
                        <img src="https://i.imgur.com/dE4kSOz.png">
                    </div>

                    <div class="name">{row[1]}</div>
                    <div class="sub">{row[4]} • {row[0]}</div>

                    {alert_banner}

                    <div class="alert">{row[5]}</div>

                    <div class="section">
                        <div class="title">WHAT TO DO</div>
                        <div class="text">{row[6]}</div>
                    </div>

                    <button class="gps" onclick="shareLocation()">📍 Share Location</button>

                    <a class="call" href="tel:{row[3]}">📞 CALL NOW</a>

                </div>

                <script>
                function shareLocation(){{
                    navigator.geolocation.getCurrentPosition(function(pos){{
                        let link = "https://maps.google.com/?q=" + pos.coords.latitude + "," + pos.coords.longitude;
                        window.open(link);
                    }});
                }}
                </script>

                </body>
                </html>
                """

    return "Band not found"
