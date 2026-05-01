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
                        body {{
                            margin: 0;
                            font-family: Arial, sans-serif;
                            background: #f4f8ff;
                        }}

                        .card {{
                            max-width: 430px;
                            margin: 0 auto;
                            background: white;
                            padding: 22px;
                            min-height: 100vh;
                            box-sizing: border-box;
                        }}

                        .logo {{
                            text-align: center;
                            margin-bottom: 10px;
                        }}

                        .logo img {{
                            width: 140px;
                            max-width: 75%;
                        }}

                        .name {{
                            text-align: center;
                            font-size: 30px;
                            font-weight: bold;
                        }}

                        .sub {{
                            text-align: center;
                            color: #0a58ca;
                            margin-top: 4px;
                        }}

                        .alert-banner {{
                            margin-top: 15px;
                            background: red;
                            color: white;
                            padding: 15px;
                            border-radius: 12px;
                            text-align: center;
                            font-weight: bold;
                            font-size: 16px;
                            animation: flash 1s infinite;
                        }}

                        @keyframes flash {{
                            0% {{opacity: 1;}}
                            50% {{opacity: 0.4;}}
                            100% {{opacity: 1;}}
                        }}

                        .alert {{
                            margin-top: 20px;
                            background: #e0edff;
                            border-left: 6px solid #0a58ca;
                            padding: 14px;
                            border-radius: 12px;
                            font-size: 18px;
                            font-weight: bold;
                        }}

                        .section {{
                            margin-top: 22px;
                        }}

                        .title {{
                            font-size: 13px;
                            font-weight: bold;
                            color: #444;
                        }}

                        .text {{
                            font-size: 18px;
                            margin-top: 5px;
                        }}

                        .call {{
                            display: block;
                            margin-top: 24px;
                            background: #0a58ca;
                            color: white;
                            text-align: center;
                            padding: 17px;
                            border-radius: 14px;
                            text-decoration: none;
                            font-size: 20px;
                            font-weight: bold;
                        }}
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

                    <div class="section">
                        <div class="title">MEDICAL NOTES</div>
                        <div class="text">{row[7]}</div>
                    </div>

                </div>

                </body>
                </html>
                """

    return "<h1>Band Not Found</h1>"
