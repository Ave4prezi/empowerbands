@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>EmpowerBands</title>
    <style>
    body {
        margin:0;
        font-family: Arial;
        background:#f2f2f2;
        text-align:center;
    }
    .container {
        max-width:500px;
        margin:auto;
        padding:40px 20px;
    }
    h1 {
        font-size:28px;
    }
    p {
        font-size:18px;
        color:#555;
    }
    .btn {
        display:block;
        margin:20px auto;
        padding:15px;
        background:red;
        color:white;
        text-decoration:none;
        border-radius:10px;
        font-size:18px;
        width:80%;
    }
    </style>
    </head>

    <body>
    <div class="container">

    <h1>EmpowerBands</h1>

    <p>Smart wearable bands that help children with disabilities and elderly individuals communicate in emergencies.</p>

    <a class="btn" href="/EB001">View Demo</a>

    <a class="btn" href="/add">Add a Person</a>

    </div>
    </body>
    </html>
    """
