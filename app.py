from flask import request

@app.route("/<band_id>")
def profile(band_id):
    band_id = band_id.strip().upper()
    alert_mode = request.args.get("alert") == "yes"

    with open(file_name, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        for row in reader:
            if len(row) >= 8 and row[0].strip().upper() == band_id:

                alert_banner = ""
                if alert_mode:
                    alert_banner = """
                    <div class="alert-banner">
                        🚨 ALERT MODE ACTIVATED 🚨<br>
                        This person may be lost or unable to communicate.<br>
                        Please stay with them and call immediately.
                    </div>
                    """

                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>EmpowerBands Profile</title>

                    <style>
                       body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f4f8ff;
}

.card {
    max-width: 380px;
    margin: 10px auto;
    background: white;
    padding: 14px;
    border-radius: 14px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}

.logo {
    text-align: center;
    margin-bottom: 2px;
}

.logo img {
    width: 90px;
    display: block;
    margin: 0 auto;
}

.name {
    text-align: center;
    font-size: 24px;
    font-weight: bold;
    margin: 4px 0 0 0;
}

.sub {
    text-align: center;
    color: #0a58ca;
    margin: 2px 0 8px 0;
    font-size: 13px;
}

.alert-banner {
    margin: 8px 0;
    background: #d62828;
    color: white;
    padding: 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 14px;
}

.alert {
    margin: 8px 0;
    background: #e0edff;
    border-left: 4px solid #0a58ca;
    padding: 10px;
    border-radius: 10px;
    font-size: 15px;
}

.section {
    margin-top: 10px;
}

.title {
    font-size: 12px;
    font-weight: bold;
    color: #444;
}

.text {
    font-size: 15px;
    margin-top: 2px;
    line-height: 1.3;
}

.call {
    display: block;
    margin-top: 12px;
    background: #0a58ca;
    color: white;
    text-align: center;
    padding: 12px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: bold;
}

.gps {
    display: block;
    margin-top: 8px;
    background: #111;
    color: white;
    text-align: center;
    padding: 10px;
    border-radius: 10px;
    font-size: 14px;
    width: 100%;
    border: none;
}
                    </style>
                </head>

                <body>

                <div class="card">

                    <div class="logo">
                        <img src="https://i.imgur.com/dE4kSOz.png">
                    </div>

                    <div class="name">{row[1]}</div>
                    <div class="sub">{row[4]} • ID: {row[0]}</div>

                    {alert_banner}

                    <div class="alert">⚠️ {row[5]}</div>

                    <div class="section">
                        <div class="title">WHAT TO DO</div>
                        <div class="text">{row[6]}</div>
                    </div>

                    <a class="call" href="tel:{row[3]}">📞 CALL NOW</a>

                    <button class="gps" onclick="shareLocation()">📍 Share My Location</button>

                    <div class="section">
                        <div class="title">MEDICAL NOTES</div>
                        <div class="text">{row[7]}</div>
                    </div>

                </div>

                <script>
                function shareLocation() {{
                    if (navigator.geolocation) {{
                        navigator.geolocation.getCurrentPosition(function(position) {{
                            const lat = position.coords.latitude;
                            const lon = position.coords.longitude;
                            const link = "https://maps.google.com/?q=" + lat + "," + lon;
                            window.open(link, "_blank");
                        }});
                    }} else {{
                        alert("Location not supported");
                    }}
                }}
                </script>

                </body>
                </html>
                """

    return "<h1>Band Not Found</h1>"
