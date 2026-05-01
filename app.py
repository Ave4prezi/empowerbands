from flask import Flask, request, redirect
import csv
import os

app = Flask(__name__)

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
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>EmpowerBands</title>
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f2f2f2;
                text-align: center;
            }
            .container {
                max-width: 500px;
                margin: auto;
                padding: 40px 20px;
            }
            h1 {
                font-size: 32px;
                margin-bottom: 10px;
            }
            p {
                font-size: 18px;
                color: #555;
                line-height: 1.4;
            }
            .btn {
                display: block;
                margin: 18px auto;
                padding: 16px;
                background: #d62828;
                color: white;
                text-decoration: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                width: 85%;
            }
        </style>
    </head>

    <body>
        <div class="container">
            <h1>EmpowerBands</h1>
            <p>
                Smart wearable bands that help children with disabilities
                and elderly individuals communicate in emergencies.
            </p>

            <a class="btn" href="/EB001">View Demo</a>
            <a class="btn" href="/add">Add a Person</a>
        </div>
    </body>
    </html>
    """


# ===============================
# ADD PERSON PAGE
# ===============================
@app.route("/add", methods=["GET", "POST"])
def add_person():
    if request.method == "POST":
        band_id = request.form.get("band_id", "").strip().upper()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        age_group = request.form.get("age_group", "").strip()
        condition = request.form.get("condition", "").strip()
        instructions = request.form.get("instructions", "").strip()
        medical_notes = request.form.get("medical_notes", "").strip()

        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                band_id,
                name,
                email,
                phone,
                age_group,
                condition,
                instructions,
                medical_notes
            ])

        return redirect(f"/{band_id}")

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Add Person - EmpowerBands</title>
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f2f2f2;
                padding: 20px;
            }
            .card {
                max-width: 430px;
                margin: auto;
                background: white;
                padding: 24px;
                border-radius: 14px;
                box-sizing: border-box;
            }
            h2 {
                text-align: center;
                margin-top: 0;
            }
            label {
                font-weight: bold;
                font-size: 14px;
            }
            input, textarea {
                width: 100%;
                padding: 13px;
                margin: 8px 0 16px 0;
                box-sizing: border-box;
                font-size: 16px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
            button {
                width: 100%;
                background: #d62828;
                color: white;
                padding: 16px;
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }
            .back {
                display: block;
                text-align: center;
                margin-top: 18px;
                color: #555;
            }
        </style>
    </head>

    <body>
        <div class="card">
            <h2>Add EmpowerBand Profile</h2>

            <form method="POST">
                <label>Band ID</label>
                <input name="band_id" placeholder="EB002" required>

                <label>Name</label>
                <input name="name" placeholder="Jordan" required>

                <label>Email</label>
                <input name="email" placeholder="parent@email.com">

                <label>Phone</label>
                <input name="phone" placeholder="2565551234" required>

                <label>Age Group</label>
                <input name="age_group" placeholder="Child / Adult / Senior" required>

                <label>Condition</label>
                <input name="condition" placeholder="Autism – Nonverbal" required>

                <label>What To Do</label>
                <textarea name="instructions" rows="4" placeholder="Please stay calm. Call my emergency contact immediately." required></textarea>

                <label>Medical Notes</label>
                <textarea name="medical_notes" rows="3" placeholder="No allergies"></textarea>

                <button type="submit">Save Profile</button>
            </form>

            <a class="back" href="/">Back Home</a>
        </div>
    </body>
    </html>
    """


# ===============================
# BAND PROFILE PAGE
# ===============================
@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.strip().upper()

    with open(file_name, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        for row in reader:
            if len(row) >= 8 and row[0].strip().upper() == band_id:
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>EmpowerBands Profile</title>
                    <style>
                        body {{
                            margin: 0;
                            font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                            background: #f2f2f2;
                        }}
                        .card {{
                            max-width: 430px;
                            margin: auto;
                            background: white;
                            padding: 24px;
                            min-height: 100vh;
                            box-sizing: border-box;
                        }}
                        .brand {{
                            text-align: center;
                            font-size: 14px;
                            color: #666;
                            margin-bottom: 15px;
                            font-weight: bold;
                            letter-spacing: 1px;
                        }}
                        .name {{
                            text-align: center;
                            font-size: 30px;
                            font-weight: bold;
                        }}
                        .sub {{
                            text-align: center;
                            color: #777;
                            margin-top: 5px;
                        }}
                        .alert {{
                            margin-top: 22px;
                            background: #ffe5e5;
                            border-left: 6px solid #d62828;
                            padding: 15px;
                            border-radius: 12px;
                            font-size: 19px;
                            font-weight: bold;
                        }}
                        .section {{
                            margin-top: 22px;
                        }}
                        .title {{
                            font-size: 13px;
                            font-weight: bold;
                            color: #444;
                            margin-bottom: 6px;
                        }}
                        .text {{
                            font-size: 18px;
                            line-height: 1.45;
                        }}
                        .call {{
                            display: block;
                            margin-top: 26px;
                            background: #d62828;
                            color: white;
                            text-align: center;
                            padding: 17px;
                            border-radius: 14px;
                            text-decoration: none;
                            font-size: 20px;
                            font-weight: bold;
                        }}
                        .footer {{
                            margin-top: 25px;
                            font-size: 12px;
                            color: #777;
                            text-align: center;
                            line-height: 1.4;
                        }}
                    </style>
                </head>

                <body>
                    <div class="card">
                        <div class="brand">EMPOWERBANDS</div>

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

                        <div class="footer">
                            EmpowerBands helps children with visible and invisible disabilities,
                            and elderly individuals with dementia or Alzheimer’s.
                        </div>
                    </div>
                </body>
                </html>
                """

    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/add">Add a Person</a></p>
    """


# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
