from flask import Flask
import csv
import os

app = Flask(__name__)

file_name = "customers.csv"

# ===============================
# CREATE CSV IF IT DOESN'T EXIST
# ===============================
if not os.path.exists(file_name):
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            "BandID", "Name", "Email", "Phone",
            "AgeGroup", "Condition", "Instructions", "MedicalNotes"
        ])
        writer.writerow([
            "EB001", "Jordan", "parent@email.com", "2565551234",
            "Child", "Autism – Nonverbal",
            "Please stay calm. I may not respond verbally, but I understand you. Call my emergency contact immediately.",
            "No allergies"
        ])

# ===============================
# HOME ROUTE
# ===============================
@app.route('/')
def home():
    return "EmpowerBands Server Running"

# ===============================
# PROFILE PAGE (MAIN FEATURE)
# ===============================
@app.route('/<band_id>')
def profile(band_id):
    with open(file_name, mode='r') as file:
        reader = csv.reader(file)
        next(reader)

        for row in reader:
            if row and row[0] == band_id:

                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>EmpowerBands</title>
                <style>
                body {{
                    margin:0;
                    font-family:-apple-system, Arial;
                    background:#f2f2f2;
                }}
                .card {{
                    max-width:420px;
                    margin:auto;
                    background:white;
                    padding:24px;
                    min-height:100vh;
                }}
                .brand {{
                    text-align:center;
                    font-size:14px;
                    color:#666;
                    margin-bottom:15px;
                    font-weight:bold;
                }}
                .name {{
                    text-align:center;
                    font-size:28px;
                    font-weight:bold;
                }}
                .sub {{
                    text-align:center;
                    color:#777;
                    margin-top:5px;
                }}
                .alert {{
                    margin-top:20px;
                    background:#ffe5e5;
                    border-left:5px solid red;
                    padding:14px;
                    border-radius:10px;
                    font-size:18px;
                    font-weight:bold;
                }}
                .section {{
                    margin-top:20px;
                }}
                .title {{
                    font-size:13px;
                    font-weight:bold;
                    color:#444;
                }}
                .text {{
                    font-size:18px;
                    margin-top:5px;
                }}
                .call {{
                    display:block;
                    margin-top:25px;
                    background:red;
                    color:white;
                    text-align:center;
                    padding:16px;
                    border-radius:12px;
                    text-decoration:none;
                    font-size:20px;
                    font-weight:bold;
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

                </div>
                </body>
                </html>
                """

    return "<h1>Band Not Found</h1>"

# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)