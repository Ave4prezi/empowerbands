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
# HOME PAGE
# ===============================
@app.route("/")
def home():
    return """
    <h1>EmpowerBands</h1>

    <p>Smart wearable emergency communication system.</p>

    <p>
    Tap a band to instantly view a person's emergency profile,
    instructions, and contact their caregiver in seconds.
    </p>

    <p><a href="/EB001">View Demo</a></p>
    <p><a href="/admin">Admin Login</a></p>
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
                <h1>{row[1]}</h1>
                <h3>⚠️ {row[5]}</h3>
                <p><strong>What to do:</strong> {row[6]}</p>
                <a href="tel:{row[3]}">CALL</a>
                <p>{row[7]}</p>
                """

    return "<h1>Band Not Found</h1>"

# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
