from flask import Flask, request, redirect, session
from twilio.rest import Client
import csv
import os
import time
import html

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")

def generate_band_id():
    highest = 0

    with open(file_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) > 0:
                band = row[0].strip().upper()

                if band.startswith("EB"):
                    try:
                        number = int(band.replace("EB", ""))
                        if number > highest:
                            highest = number
                    except:
                        pass

    return f"EB{highest + 1:03d}"


@app.route("/add", methods=["GET", "POST"])
def add():

    if not session.get("logged_in"):
        return redirect("/admin")

    next_band_id = generate_band_id()

    if request.method == "POST":

        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            writer.writerow([
                request.form["band_id"].strip().upper(),
                request.form["name"],
                request.form["email"],
                request.form["phone"],
                request.form["age_group"],
                request.form["condition"],
                request.form["instructions"],
                request.form["medical_notes"],
                request.form["pin"]
            ])

        return redirect(f"/customer/{request.form['band_id'].strip().upper()}")

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Add EmpowerBand Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>

body{{
    margin:0;
    font-family:Arial,sans-serif;
    background:
    radial-gradient(circle at top,#0ea5e9 0%,#07111f 30%,#030712 100%);
    min-height:100vh;
    color:white;
}}

.page{{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:24px;
}}

.card{{
    width:100%;
    max-width:560px;
    background:rgba(255,255,255,0.08);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.15);
    border-radius:28px;
    padding:30px;
    box-shadow:0 25px 80px rgba(0,0,0,.55);
}}

h1{{
    margin:0;
    font-size:34px;
    font-weight:800;
    text-align:center;
}}

.subtitle{{
    text-align:center;
    color:#cbd5e1;
    margin:10px 0 25px;
}}

input, textarea{{
    width:100%;
    box-sizing:border-box;
    padding:15px;
    border:none;
    outline:none;
    border-radius:16px;
    background:rgba(255,255,255,.1);
    color:white;
    margin-bottom:14px;
    font-size:16px;
}}

textarea{{
    min-height:90px;
    resize:vertical;
}}

input::placeholder,
textarea::placeholder{{
    color:#cbd5e1;
}}

button{{
    width:100%;
    padding:16px;
    border:none;
    border-radius:16px;
    background:linear-gradient(135deg,#22c55e,#06b6d4);
    color:white;
    font-weight:bold;
    font-size:17px;
    cursor:pointer;
}}

.footer{{
    text-align:center;
    margin-top:18px;
    color:#94a3b8;
    font-size:12px;
}}

</style>
</head>

<body>

<div class="page">

<div class="card">

<h1>Add Profile</h1>

<div class="subtitle">
Create a secure EmpowerBand emergency profile
</div>

<form method="POST">

<input name="band_id" value="{next_band_id}" readonly>

<input name="name" placeholder="Full Name" required>

<input name="email" placeholder="Email">

<input name="phone" placeholder="Emergency Phone Number" required>

<input name="age_group" placeholder="Child / Adult / Senior">

<input name="condition" placeholder="Public condition example: Autism - Nonverbal">

<textarea name="instructions" placeholder="Public instructions"></textarea>

<textarea name="medical_notes" placeholder="Private medical notes"></textarea>

<input name="pin" placeholder="PIN example: 1234" required>

<button type="submit">
Save Profile
</button>

</form>

<div class="footer">
EmpowerBands Admin System
</div>

</div>

</div>

</body>
</html>
return f"""
