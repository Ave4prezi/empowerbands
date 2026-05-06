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
                display:block;
                width:100%;
                padding:16px;
                border-radius:12px;
                text-align:center;
                text-decoration:none;
                font-weight:bold;
                margin-top:12px;
                border:none;
                font-size:16px;
                box-sizing:border-box;
            }}
            .alert {{ background:#dc2626; color:white; }}
            .gps {{ background:#111827; color:white; }}
            .unlock {{ margin-top:20px; }}
            input {{
                width:100%;
                padding:12px;
                border-radius:8px;
                border:1px solid #ccc;
                margin-top:8px;
                box-sizing:border-box;
            }}
            .unlock-btn {{
                margin-top:10px;
                width:100%;
                padding:12px;
                border-radius:10px;
                border:none;
                background:#0a58ca;
                color:white;
                font-weight:bold;
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

            <button class="btn alert" onclick="smartSmsAlert()">
                🚨 Text Emergency Contact
            </button>

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
        function smartSmsAlert(){{
            const phones = "{phone}".split(",").map(p => p.trim()).filter(Boolean);

            function buildMessage(locationText){{
                return (
                    "🚨 EmpowerBands Alert%0A%0A" +
                    "Name: {name}%0A" +
                    "Condition: {condition}%0A" +
                    "Instructions: {instructions}%0A%0A" +
                    locationText +
                    "%0AProfile: {BASE_URL}/customer/{band_id}"
                );
            }}

            function openSms(locationText){{
                const message = buildMessage(locationText);

                if (phones.length === 1) {{
                    window.location.href = "sms:" + phones[0] + "?body=" + message;
                }} else {{
                    alert("Multiple emergency contacts found. Opening first contact.");
                    window.location.href = "sms:" + phones[0] + "?body=" + message;
                }}
            }}

            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(function(pos){{
                    const location =
                        "Location: https://maps.google.com/?q=" +
                        pos.coords.latitude + "," + pos.coords.longitude + "%0A%0A";

                    openSms(location);
                }}, function(){{
                    openSms("Location: Not shared%0A%0A");
                }});
            }} else {{
                openSms("Location: Not supported%0A%0A");
            }}
        }}
        </script>

    </body>
    </html>
    """
