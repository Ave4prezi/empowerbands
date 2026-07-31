import os
import sys
from pathlib import Path

import psycopg2


def migrate():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    schema_file = Path(__file__).with_name("schema_postgres.sql")

    if not schema_file.exists():
        raise FileNotFoundError(
            f"Could not find schema file: {schema_file}"
        )

    schema_sql = schema_file.read_text(encoding="utf-8")

    print("Creating EmpowerBands PostgreSQL database tables...", flush=True)

    connection = psycopg2.connect(database_url)

    try:
        cursor = connection.cursor()
        cursor.execute(schema_sql)
        connection.commit()
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print("Database migration completed successfully.", flush=True)


if __name__ == "__main__":
    try:
        migrate()
    except Exception as error:
        print(f"Database migration failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
