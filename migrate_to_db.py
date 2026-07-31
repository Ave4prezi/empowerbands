"""
Create the EmpowerBands bulk-band database tables.

For production, set DATABASE_URL to the PostgreSQL connection
string before running this script.

Run:
    python migrate_to_db.py
"""

import os
import sys

import bulk_bands_db as bulk_db


def main():
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "Add the PostgreSQL connection string to your environment "
            "before running this migration.",
            file=sys.stderr,
        )
        return 1

    if not bulk_db._USING_POSTGRES:
        print(
            "ERROR: bulk_bands_db is not using PostgreSQL.\n"
            "Check that DATABASE_URL begins with postgres:// "
            "or postgresql://.",
            file=sys.stderr,
        )
        return 1

    print("Creating EmpowerBands database tables...")

    try:
        bulk_db.init_db()
    except Exception as error:
        print(f"Database migration failed: {error}", file=sys.stderr)
        return 1

    print("Database migration completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
