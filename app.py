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
                display:block; width:100%; padding:16px; border-radius:12px;
                text-align:center; text-decoration:none; font-weight:bold;
                margin-top:12px; border:none; font-size:16px; box-sizing:border-box;
            }}
            .alert {{ background:#dc2626; color:white; }}
            .secondary {{ background:#111827; color:white; }}
            .unlock {{ margin-top:20px; }}
            input {{
                width:100%; padding:12px; border-radius:8px;
                border:1px solid #ccc; margin-top:8px; box-sizing:border-box;
            }}
            .unlock-btn {{
                margin-top:10px; width:100%; padding:12px; border-radius:10px;
                border:none; background:#0a58ca; color:white; font-weight:bold;
            }}
            .list {{ margin-top:16px; }}
            .list a {{
                display:block; padding:12px; margin-top:8px; border-radius:10px;
                background:#e5e7eb; color:#111; text-decoration:none; font-weight:bold;
            }}
            .hint {{ color:#666; font-size:13px; margin-top:8px; }}
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

            <div id="contacts" class="list"></div>
            <div id="hint" class="hint"></div>

            <div class="unlock">
                <form method="GET" action="/customer/{band_id}">
                    <input type="password" name="pin" placeholder="Enter PIN">
                    <button class="unlock-btn" type="submit">Unlock Full Info</button>
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

            function encode(msg){{
                return encodeURIComponent(msg);
            }}

            function showContacts(msg){{
                const list = document.getElementById("contacts");
                const hint = document.getElementById("hint");
                list.innerHTML = "";
                hint.innerText = "";

                if (phones.length > 1) {{
                    hint.innerText = "Multiple contacts found. Tap each to send.";
                }}

                phones.forEach(p => {{
                    const a = document.createElement("a");
                    a.href = "sms:" + p + "?body=" + encode(msg);
                    a.innerText = "Text " + p;
                    list.appendChild(a);
                }});
            }}

            function copyToClipboard(msg){{
                try {{
                    navigator.clipboard.writeText(msg);
                    document.getElementById("hint").innerText = "Message copied. Paste if your SMS app doesn’t fill automatically.";
                }} catch(e) {{
                    // ignore
                }}
            }}

            function openFirst(msg){{
                if (phones.length > 0) {{
                    window.location.href = "sms:" + phones[0] + "?body=" + encode(msg);
                }}
            }}

            function proceed(locationText){{
                const msg = buildMessage(locationText);
                copyToClipboard(msg);
                openFirst(msg);
                showContacts(msg);
            }}

            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(function(pos){{
                    const location =
                        "Location: https://maps.google.com/?q=" +
                        pos.coords.latitude + "," + pos.coords.longitude + "\\n\\n";
                    proceed(location);
                }}, function(){{
                    proceed("Location: Not shared\\n\\n");
                }});
            }} else {{
                proceed("Location: Not supported\\n\\n");
            }}
        }}
        </script>

    </body>
    </html>
    """
