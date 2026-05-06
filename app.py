@@ -1,51 +1,39 @@
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
                display:block; width:100%; padding:16px; border-radius:12px;
                text-align:center; text-decoration:none; font-weight:bold;
                margin-top:12px; border:none; font-size:16px; box-sizing:border-box;
            }}
            .alert {{ background:#dc2626; color:white; }}
            .gps {{ background:#111827; color:white; }}
            .secondary {{ background:#111827; color:white; }}
            .unlock {{ margin-top:20px; }}
            input {{
                width:100%;
                padding:12px;
                border-radius:8px;
                border:1px solid #ccc;
                margin-top:8px;
                box-sizing:border-box;
                width:100%; padding:12px; border-radius:8px;
                border:1px solid #ccc; margin-top:8px; box-sizing:border-box;
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

@@ -70,59 +58,92 @@
                <div>{medical_notes}</div>
            </div>

            <button class="btn alert" onclick="smartSmsAlert()">
                🚨 Text Emergency Contact
            <button class="btn alert" onclick="nextLevelAlert()">
                🚨 Send Emergency Alert
            </button>

            <div id="contacts" class="list"></div>
            <div id="hint" class="hint"></div>

            <div class="unlock">
                <form method="GET" action="/customer/{band_id}">
                    <input type="password" name="pin" placeholder="Enter PIN">
                    <button class="unlock-btn" type="submit">
                        Unlock Full Info
                    </button>
                    <button class="unlock-btn" type="submit">Unlock Full Info</button>
                </form>
            </div>

        </div>

        <script>
        function smartSmsAlert(){{
        function nextLevelAlert(){{
            const phones = "{phone}".split(",").map(p => p.trim()).filter(Boolean);

            function buildMessage(locationText){{
                return (
                    "🚨 EmpowerBands Alert%0A%0A" +
                    "Name: {name}%0A" +
                    "Condition: {condition}%0A" +
                    "Instructions: {instructions}%0A%0A" +
                    "🚨 EmpowerBands Alert\\n\\n" +
                    "Name: {name}\\n" +
                    "Condition: {condition}\\n" +
                    "Instructions: {instructions}\\n\\n" +
                    locationText +
                    "%0AProfile: {BASE_URL}/customer/{band_id}"
                    "\\nProfile: {BASE_URL}/customer/{band_id}"
                );
            }}

            function openSms(locationText){{
                const message = buildMessage(locationText);
            function encode(msg){{
                return encodeURIComponent(msg);
            }}

            function showContacts(msg){{
                const list = document.getElementById("contacts");
                const hint = document.getElementById("hint");
                list.innerHTML = "";
                hint.innerText = "";

                if (phones.length === 1) {{
                    window.location.href = "sms:" + phones[0] + "?body=" + message;
                }} else {{
                    alert("Multiple emergency contacts found. Opening first contact.");
                    window.location.href = "sms:" + phones[0] + "?body=" + message;
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
                        pos.coords.latitude + "," + pos.coords.longitude + "%0A%0A";

                    openSms(location);
                        pos.coords.latitude + "," + pos.coords.longitude + "\\n\\n";
                    proceed(location);
                }}, function(){{
                    openSms("Location: Not shared%0A%0A");
                    proceed("Location: Not shared\\n\\n");
                }});
            }} else {{
                openSms("Location: Not supported%0A%0A");
                proceed("Location: Not supported\\n\\n");
            }}
        }}
        </script>
