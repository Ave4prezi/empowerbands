# EmpowerBands PostgreSQL setup

## 1. Install dependencies

```powershell
pip install -r requirements.txt
```

## 2. Set the database password in PowerShell

```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGDATABASE="empowerbands"
$env:PGUSER="postgres"
$env:PGPASSWORD="YOUR_POSTGRES_PASSWORD"
```

The application creates the `members` and `scan_logs` tables automatically if they do not exist.

## 3. Import the existing CSV profiles once

```powershell
python migrate_csv_to_postgres.py
```

The migration hashes each member PIN before saving it. Running the migration again updates matching Band IDs instead of creating duplicates.

## 4. Start the website

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## Deployment

On Render, Railway, or another host, add the provider's PostgreSQL connection string as the `DATABASE_URL` environment variable. Also set `SECRET_KEY`, `ADMIN_PASSWORD`, and `BASE_URL`.

## Main changes

- Member profiles are stored in PostgreSQL instead of `customers.csv`.
- Scan history is stored in the `scan_logs` table instead of `scan_log.csv`.
- New and edited PINs are securely hashed.
- The old `customers.csv` remains only as a migration backup.
