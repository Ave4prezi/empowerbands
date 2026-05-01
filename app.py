from flask import Flask, request, redirect, session
import csv
import os

app = Flask(__name__)

# 🔐 SECURITY
app.secret_key = "change-this-to-a-random-secret"
ADMIN_PASSWORD = "empower123"

file_name = "customers.csv"

HEADERS = [
    "BandID", "Name", "Email", "Phone",
    "AgeGroup", "Condition", "Instructions", "MedicalNotes"
]

# ===============================
# CREATE CSV IF MISSING
# ===============================
if not os.path.exists(file_name):
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADERS)
        writer.writerow([
            "EB001",
            "Jordan",
            "parent@email.com",
            "2565551234",
            "Child",
            "Autism – Nonverbal",
            "Please stay calm. I may not respond verbally. Call my emergency contact immediately.",
            "No allergies"
        ])

# ===============================
# HOME PAGE (BLUE THEME)
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
            <a class="btn secondary" href="/admin">Admin Login</a>

            <div class="card">
                <div class="item">🔵 Tap the band with a phone</div>
                <div class="item">🔵 Instantly view the person’s support profile</div>
                <div class="item">🔵 See what to do in an emergency</div>
                <div class="item">🔵 Call the caregiver with one tap</div>
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
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect("/add")

        return "<h2>Wrong password</h2><p><a href='/admin'>Try again</a></p>"

    return """
    <h2>Admin Login</h2>
    <form method="POST">
        <input type="password" name="password" placeholder="Enter password" required>
        <button type="submit">Login</button>
    </form>
    """

# ===============================
# ADD PERSON (PROTECTED)
# ===============================
@app.route("/add", methods=["GET", "POST"])
def add_person():
    if not session.get("admin_logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        data = [
            request.form["band_id"],
            request.form["name"],
            request.form["email"],
            request.form["phone"],
            request.form["age_group"],
            request.form["condition"],
            request.form["instructions"],
            request.form["medical_notes"],
        ]

        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(data)

        return redirect(f"/{data[0]}")

    return """
    <h2>Add Profile</h2>
    <form method="POST">
        ID: <input name="band_id" required><br>
        Name: <input name="name" required><br>
        Email: <input name="email"><br>
        Phone: <input name="phone" required><br>
        Age: <input name="age_group"><br>
        Condition: <input name="condition"><br>
        Instructions: <input name="instructions"><br>
        Notes: <input name="medical_notes"><br>
        <button type="submit">Save</button>
    </form>
    """

# ===============================
# PROFILE PAGE
# ===============================
@app.route("/<band_id>")
def profile(band_id):
    with open(file_name, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)

        for row in reader:
            if len(row) >= 8 and row[0] == band_id:
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>EmpowerBands Profile</title>
                    <style>
                        body {{
                            margin: 0;
                            font-family: Arial;
                            background: #f4f8ff;
                        }}
                        .card {{
                            max-width: 420px;
                            margin: auto;
                            background: white;
                            padding: 24px;
                            min-height: 100vh;
                        }}
                        .logo {{
                            text-align: center;
                            margin-bottom: 10px;
                        }}
                        .logo img {{
                            width: 80px;
                        }}
                        .name {{
                            text-align: center;
                            font-size: 28px;
                            font-weight: bold;
                        }}
                        .sub {{
                            text-align: center;
                            color: #0a58ca;
                            margin-top: 5px;
                        }}
                        .alert {{
                            margin-top: 20px;
                            background: #e0edff;
                            border-left: 6px solid #0a58ca;
                            padding: 14px;
                            border-radius: 10px;
                            font-size: 18px;
                            font-weight: bold;
                        }}
                        .section {{
                            margin-top: 20px;
                        }}
                        .title {{
                            font-weight: bold;
                            font-size: 13px;
                            color: #444;
                        }}
                        .text {{
                            font-size: 18px;
                            margin-top: 5px;
                        }}
                        .call {{
                            display: block;
                            margin-top: 25px;
                            background: #0a58ca;
                            color: white;
                            text-align: center;
                            padding: 16px;
                            border-radius: 12px;
                            text-decoration: none;
                            font-size: 20px;
                            font-weight: bold;
                        }}
                    </style>
                </head>

                <body>
                    <div class="card">
                    <div style="text-align:center; margin-bottom:15px;">
    <img src="https://i.imgur.com/dE4kSOz.png" style="width:140px; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.15);">
</div>
</div>

                        <div class="logo">
                            <img src="YOUR_LOGO_URL_HERE">
                        </div>

                        <div class="name">{row[1]}</div>
                        <div class="sub">{row[4]} • ID: {row[0]}</div>

                        <div class="alert">⚠️ {row[5]}</div>

                        <div class="section">
                            <div class="title">WHAT TO DO</div>
                            <div class="text">{row[6]}</div>
                        </div>

                        <a class="call" href="tel:{row[3]}">📞 CALL NOW</a>

                        <div class="section">
                            <div class="title">MEDICAL NOTES</div>
                            <div class="text">{row[7]}</div>
                        </div>

                    </div>
                </body>
                </html>
                """

    return "<h1>Band Not Found</h1>"
# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
