"""Clean activation routes for the CSV-backed EmpowerBands app.

Use once from app.py after ``app`` and ``file_name`` are defined:

    from activation_routes_clean import register_activation_routes
    register_activation_routes(app, file_name)

This module intentionally keeps only the public page and its API route.  It
uses activation_codes.csv for codes because customers.csv is the profile
store and existing rows do not consistently contain an activation-code
column.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from flask import jsonify, render_template, request


PROFILE_COLUMNS = (
    "band_id",
    "activation_code",
    "name",
    "email",
    "phone",
    "emergency_phones",
    "emergency_emails",
    "age_group",
    "condition",
    "instructions",
    "medical_notes",
    "pin",
    "address",
    "race",
    "gender",
    "photo_url",
)


def _normalise(value: Any) -> str:
    return str(value or "").strip().upper()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [name.strip() for name in (reader.fieldnames or [])]
        rows = []
        for raw in reader:
            row = {key: (value or "").strip() for key, value in raw.items() if key}
            rows.append(row)
        return fieldnames, rows


def _read_activation_codes(path: Path) -> dict[str, str]:
    _, rows = _read_csv(path)
    return {
        _normalise(row.get("band_id")): _normalise(row.get("activation_code"))
        for row in rows
        if _normalise(row.get("band_id"))
    }


def _write_profiles(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    columns = fieldnames or list(PROFILE_COLUMNS)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in columns} for row in rows)


def register_activation_routes(app, customers_file: str = "customers.csv"):
    """Register the single activation page and API endpoint on ``app``."""
    customers_path = Path(customers_file)
    codes_path = customers_path.with_name("activation_codes.csv")

    @app.route("/activate", defaults={"band_id": None})
    @app.route("/activate/<band_id>")
    def activate(band_id=None):
        """Render the activation page; the optional URL ID is prefilled by JS."""
        return render_template("activate.html", band_id=_normalise(band_id))

    @app.route("/api/activate", methods=["POST"])
    def api_activate():
        data = request.get_json(silent=True) or {}

        band_id = _normalise(data.get("bandId"))
        activation_code = _normalise(data.get("activationCode"))
        first_name = str(data.get("firstName") or "").strip()
        last_name = str(data.get("lastName") or "").strip()
        email = str(data.get("email") or "").strip().lower()
        phone = str(data.get("phone") or "").strip()
        profile_type = str(data.get("profileType") or "").strip()

        required = (
            (band_id, "Safety ID is required."),
            (activation_code, "Activation code is required."),
            (first_name, "First name is required."),
            (last_name, "Last name is required."),
            (email, "Email is required."),
        )
        for value, message in required:
            if not value:
                return jsonify(error=message), 400

        fieldnames, rows = _read_csv(customers_path)
        if not fieldnames:
            return jsonify(error="Safety ID database was not found or is empty."), 500

        profile = next(
            (row for row in rows if _normalise(row.get("band_id")) == band_id),
            None,
        )
        if profile is None:
            return jsonify(error="Safety ID not found."), 404

        # The committed customers.csv has legacy rows where column 1 is the
        # person's name.  Never read the activation code positionally.
        expected_code = _read_activation_codes(codes_path).get(band_id)
        if not expected_code:
            expected_code = _normalise(profile.get("activation_code"))
        if not expected_code:
            return jsonify(error="No activation code is configured for this Safety ID."), 409
        if expected_code != activation_code:
            return jsonify(error="Activation code is incorrect."), 403

        if profile.get("name", "").strip() or profile.get("email", "").strip():
            return jsonify(error="This Safety ID has already been activated."), 409

        profile["name"] = f"{first_name} {last_name}".strip()
        profile["email"] = email
        profile["phone"] = phone
        profile["age_group"] = profile_type
        _write_profiles(customers_path, fieldnames, rows)

        return jsonify(
            ok=True,
            bandId=band_id,
            message="Safety ID activated successfully.",
        )

    return activate, api_activate
