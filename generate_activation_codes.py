import csv
import secrets
import string
import os



CUSTOMERS_FILE = "customers.csv"
ACTIVATION_FILE = "activation_codes.csv"


def make_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


existing_codes = {}

if os.path.exists(ACTIVATION_FILE):
    with open(ACTIVATION_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            existing_codes[row["band_id"].strip().upper()] = row


results = []

with open(CUSTOMERS_FILE, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        band_id = row.get("band_id", "").strip().upper()

        if not band_id:
            continue

        if band_id in existing_codes:
            results.append(existing_codes[band_id])
            continue

        # Existing profile = already claimed
        name = row.get("name", "").strip()
        email = row.get("email", "").strip()

        claimed = "yes" if name or email else "no"

        results.append({
            "band_id": band_id,
            "activation_code": make_code(),
            "claimed": claimed
        })


with open(ACTIVATION_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "band_id",
            "activation_code",
            "claimed"
        ]
    )

    writer.writeheader()
    writer.writerows(results)


print(f"Created {ACTIVATION_FILE}")
print(f"{len(results)} Safety IDs processed.")
