from flask import Flask, render_template_string, request, redirect, session
import os
import csv
import time

app = Flask(__name__)

# SETTINGS
app.secret_key = os.environ.get("SECRET_KEY", "empowerbands-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "empower123")

CUSTOMERS_FILE = "customers.csv"
SCAN_LOG_FILE = "scan_log.csv"


# Create CSV files if missing
def setup_files():
    if not os.path.exists(CUSTOMERS_FILE):
        with open(CUSTOMERS_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["band_id", "name", "phone", "emergency_contact", "medical_info"])

    if not os.path.exists(SCAN_LOG_FILE):
        with open(SCAN_LOG_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["band_id", "name", "time", "scan_type", "ip"])


setup_files()


def get_customer(band_id):
    with open(CUSTOMERS_FILE, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["band_id"] == band_id:
                return row
    return None


def log_scan(band_id, name, scan_type, ip):
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(SCAN_LOG_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([band_id, name, now, scan_type, ip])


@app.route("/")
def home():
    return """
    <h1>EmpowerBands</h1>
    <p>System is running.</p>
    <a href="/admin">Admin Login</a>
    """


@app.route("/customer/<band_id>")
def customer_page(band_id):
    customer = get_customer(band_id)

    if not customer:
        return f"""
        <h1>Band Not Activated</h1>
        <p>Band ID: {band_id}</p>
        <p>Please contact EmpowerBands to activate this band.</p>
        """

    log_scan(
        band_id,
        customer["name"],
        request.args.get("type", "scan"),
        request.remote_addr
    )

    return render_template_string("""
    <html>
    <head>
        <title>EmpowerBands Emergency Info</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #111;
                color: white;
                padding: 30px;
            }
            .card {
                max-width: 500px;
                margin: auto;
                background: #1e1e1e;
                padding: 25px;
                border-radius: 18px;
                box-shadow: 0 0 20px rgba(0,0,0,.4);
            }
            h1 {
                color: #f5c542;
            }
            .button {
                display: block;
                background: #f5c542;
                color: #111;
                padding: 14px;
                margin: 12px 0;
                text-align: center;
                border-radius: 10px;
                text-decoration: none;
                font-weight: bold;
            }
            .secondary {
                background: #333;
                color: white;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Emergency Info</h1>
            <p><strong>Name:</strong> {{ customer.name }}</p>
            <p><strong>Phone:</strong> {{ customer.phone }}</p>
            <p><strong>Emergency Contact:</strong> {{ customer.emergency_contact }}</p>
            <p><strong>Medical Info:</strong> {{ customer.medical_info }}</p>

            <a class="button" href="tel:{{ customer.emergency_contact }}">Call Emergency Contact</a>

            <a class="button secondary" href="sms:{{ customer.emergency_contact }}?body=Someone%20scanned%20your%20EmpowerBand.">
                Send Text Alert
            </a>

            <a class="button secondary" href="/scan/{{ customer.band_id }}?type=tap">
                Log This Scan
            </a>
        </div>
    </body>
    </html>
    """, customer=customer)


@app.route("/scan/<band_id>")
def scan(band_id):
    customer = get_customer(band_id)

    if customer:
        log_scan(
            band_id,
            customer["name"],
            request.args.get("type", "tap"),
            request.remote_addr
        )

    return redirect(f"/customer/{band_id}")


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")
        else:
            return "<h1>Wrong password</h1><a href='/admin'>Try again</a>"

    return """
    <h1>EmpowerBands Admin Login</h1>
    <form method="POST">
        <input type="password" name="password" placeholder="Enter admin password" required>
        <button type="submit">Login</button>
    </form>
    """


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    customers = []
    scans = []

    with open(CUSTOMERS_FILE, "r", encoding="utf-8") as file:
        customers = list(csv.DictReader(file))

    with open(SCAN_LOG_FILE, "r", encoding="utf-8") as file:
        scans = list(csv.DictReader(file))

    return render_template_string("""
    <h1>EmpowerBands Admin Dashboard</h1>

    <p><a href="/admin/add">Add New Band Customer</a></p>
    <p><a href="/admin/logout">Logout</a></p>

    <h2>Customers</h2>
    <table border="1" cellpadding="8">
        <tr>
            <th>Band ID</th>
            <th>Name</th>
            <th>Phone</th>
            <th>Emergency Contact</th>
            <th>Medical Info</th>
            <th>Customer Link</th>
        </tr>
        {% for c in customers %}
        <tr>
            <td>{{ c.band_id }}</td>
            <td>{{ c.name }}</td>
            <td>{{ c.phone }}</td>
            <td>{{ c.emergency_contact }}</td>
            <td>{{ c.medical_info }}</td>
            <td><a href="/customer/{{ c.band_id }}">Open</a></td>
        </tr>
        {% endfor %}
    </table>

    <h2>Scan Log</h2>
    <table border="1" cellpadding="8">
        <tr>
            <th>Band ID</th>
            <th>Name</th>
            <th>Time</th>
            <th>Scan Type</th>
            <th>IP</th>
        </tr>
        {% for s in scans %}
        <tr>
            <td>{{ s.band_id }}</td>
            <td>{{ s.name }}</td>
            <td>{{ s.time }}</td>
            <td>{{ s.scan_type }}</td>
            <td>{{ s.ip }}</td>
        </tr>
        {% endfor %}
    </table>
    """, customers=customers, scans=scans)


@app.route("/admin/add", methods=["GET", "POST"])
def add_customer():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        band_id = request.form.get("band_id")
        name = request.form.get("name")
        phone = request.form.get("phone")
        emergency_contact = request.form.get("emergency_contact")
        medical_info = request.form.get("medical_info")

        with open(CUSTOMERS_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([band_id, name, phone, emergency_contact, medical_info])

        return redirect("/admin/dashboard")

    return """
    <h1>Add New Band Customer</h1>

    <form method="POST">
        <p><input name="band_id" placeholder="Band ID, example: 001" required></p>
        <p><input name="name" placeholder="Customer Name" required></p>
        <p><input name="phone" placeholder="Customer Phone"></p>
        <p><input name="emergency_contact" placeholder="Emergency Contact Phone"></p>
        <p><textarea name="medical_info" placeholder="Medical Info"></textarea></p>
        <button type="submit">Save Customer</button>
    </form>

    <p><a href="/admin/dashboard">Back to Dashboard</a></p>
    """


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
