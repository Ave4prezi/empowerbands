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

                # ===============================
                # CONFIRM ALERT SCREEN
                # ===============================
                if confirm_alert:
                    return f"""
                    <html><body style="font-family:Arial;text-align:center;padding:30px;">
                        <h2>Confirm Emergency Alert</h2>
                        <p>This will send a text alert to the caregiver with your location.</p>

                        <button onclick="sendAlertWithLocation()" style="padding:15px;background:#dc2626;color:white;border:none;border-radius:10px;font-weight:bold;">
                            🚨 Send Emergency Alert
                        </button>

                        <p><a href="/customer/{band_id}">Cancel</a></p>

                        <script>
                        function sendAlertWithLocation(){{
                            if (navigator.geolocation) {{
                                navigator.geolocation.getCurrentPosition(function(pos){{
                                    let lat = pos.coords.latitude;
                                    let lon = pos.coords.longitude;
                                    window.location.href = "/alert_with_location?band_id={band_id}&lat=" + lat + "&lon=" + lon;
                                }}, function(){{
                                    window.location.href = "/customer/{band_id}?alert=yes";
                                }});
                            }} else {{
                                window.location.href = "/customer/{band_id}?alert=yes";
                            }}
                        }}
                        </script>
                    </body></html>
                    """

                # ===============================
                # PUBLIC VIEW (NO PIN)
                # ===============================
                if entered_pin != pin:
                    return f"""
                    <html>
                    <head>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body {{ margin:0; font-family:Arial; background:#f3f4f6; }}
                            .container {{ max-width:420px; margin:auto; padding:20px; }}
                            .header {{ text-align:center; margin-top:10px; }}
                            .name {{ font-size:26px; font-weight:bold; }}
                            .sub {{ color:#555; }}
                            .badge {{ background:#dbeafe; padding:12px; border-radius:12px; margin-top:15px; font-weight:bold; }}
                            .section {{ margin-top:20px; }}
                            .title {{ font-weight:bold; color:#555; margin-bottom:6px; }}
                            .btn {{
                                display:block; width:100%; padding:16px;
                                border-radius:12px; text-align:center;
                                font-weight:bold; margin-top:12px;
                                border:none; font-size:16px;
                            }}
                            .alert {{ background:#dc2626; color:white; }}
                            .unlock {{ margin-top:20px; }}
                            input {{
                                width:100%; padding:12px;
                                border-radius:8px; border:1px solid #ccc;
                                margin-top:8px;
                            }}
                            .unlock-btn {{
                                margin-top:10px; width:100%;
                                padding:12px; border-radius:10px;
                                border:none; background:#0a58ca;
                                color:white; font-weight:bold;
                            }}
                        </style>
                    </head>

                    <body>
                        <div class="container">

                            <div class="header">
                                <img src="{LOGO_URL}" width="90">
                                <div class="name">{name}</div>
                                <div class="sub">{age_group} • ID: {band_id}</div>
                            </div>

                            <div class="badge">⚠️ {condition}</div>

                            <div class="section">
                                <div class="title">WHAT TO DO</div>
                                <div>{instructions}</div>
                            </div>

                            <div class="section">
                                <div class="title">MEDICAL NOTES</div>
                                <div>{medical_notes}</div>
                            </div>

                            <button class="btn alert" onclick="nextLevelAlert()">
                                🚨 Send Emergency Alert
                            </button>

                            <div id="contacts"></div>

                            <div class="unlock">
                                <form method="GET" action="/customer/{band_id}">
                                    <input type="password" name="pin" placeholder="Enter PIN">
                                    <button class="unlock-btn" type="submit">
                                        Unlock Full Info
                                    </button>
                                </form>
                            </div>

                        </div>

                        <script>
                        function nextLevelAlert(){{
                            const phones = "{phone}".split(",").map(p => p.trim()).filter(Boolean);

                            function buildMessage(locationText){{
                                return (
                                    "🚨 EmpowerBands Alert\\n\\n" +
                                    "Name: {name}\\n" +
                                    "Condition: {condition}\\n" +
                                    "Instructions: {instructions}\\n\\n" +
                                    locationText +
                                    "\\nProfile: {BASE_URL}/customer/{band_id}"
                                );
                            }}

                            function sendAll(msg){{
                                phones.forEach(p => {{
                                    window.open("sms:" + p + "?body=" + encodeURIComponent(msg), "_blank");
                                }});
                            }}

                            if (navigator.geolocation) {{
                                navigator.geolocation.getCurrentPosition(function(pos){{
                                    let location = "Location: https://maps.google.com/?q=" +
                                        pos.coords.latitude + "," + pos.coords.longitude + "\\n\\n";
                                    sendAll(buildMessage(location));
                                }}, function(){{
                                    sendAll(buildMessage("Location not shared\\n\\n"));
                                }});
                            }} else {{
                                sendAll(buildMessage("Location not supported\\n\\n"));
                            }}
                        }}
                        </script>

                    </body>
                    </html>
                    """

                # ===============================
                # FULL VIEW (PIN CORRECT)
                # ===============================
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
                <p><a href="/customer/{band_id}">Back</a></p>
                """

    return """
    <h1>Band Not Found</h1>
    <p>This band ID has not been added yet.</p>
    <p><a href="/admin">Admin Login</a></p>
    """
