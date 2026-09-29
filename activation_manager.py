"""Authenticated PostgreSQL activation-code inventory for EmpowerBands."""

from __future__ import annotations

import csv
import hmac
import io
import re
import secrets
import uuid
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterable

import psycopg
import qrcode
from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
BATCH_SIZES = (1, 10, 25, 50, 100, 200)
BAND_ID_RE = re.compile(r"^EB(\d+)$", re.IGNORECASE)


def generate_secure_code(length: int = CODE_LENGTH) -> str:
    """Return an activation code without visually ambiguous characters."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def format_band_id(number: int) -> str:
    """Keep at least three digits while allowing inventory to grow past EB999."""
    if number < 1:
        raise ValueError("Safety ID sequence numbers must be positive.")
    return f"EB{number:03d}"


def sanitize_csv_cell(value: object) -> str:
    """Prevent spreadsheet formula execution in administrator exports."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@dataclass
class GeneratedBatch:
    batch_id: str
    records: list[dict]


class PostgresActivationRepository:
    """All activation inventory writes are transactional and parameterized."""

    def __init__(self, database_url: str):
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        self.database_url = database_url

    def ensure_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    ALTER TABLE activation_codes
                        ADD COLUMN IF NOT EXISTS assigned_to TEXT,
                        ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ,
                        ADD COLUMN IF NOT EXISTS notes TEXT,
                        ADD COLUMN IF NOT EXISTS batch_id TEXT,
                        ADD COLUMN IF NOT EXISTS code_rotated_at TIMESTAMPTZ
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS activation_code_audit (
                        id BIGSERIAL PRIMARY KEY,
                        band_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT 'admin',
                        details TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_activation_codes_claimed
                    ON activation_codes (claimed)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_activation_codes_assigned_to
                    ON activation_codes (LOWER(assigned_to))
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_activation_codes_batch_id
                    ON activation_codes (batch_id)
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_activation_codes_band_id_upper
                    ON activation_codes (UPPER(band_id))
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_activation_codes_code_upper
                    ON activation_codes (UPPER(activation_code))
                    """
                )
            conn.commit()

    def list_records(self, query: str = "", status: str = "all", store: str = "") -> list[dict]:
        clauses = []
        params: list[object] = []
        if query:
            clauses.append("UPPER(band_id) LIKE UPPER(%s)")
            params.append(f"%{query}%")
        if status == "available":
            clauses.append("claimed = FALSE")
        elif status == "claimed":
            clauses.append("claimed = TRUE")
        if store:
            clauses.append("COALESCE(assigned_to, '') ILIKE %s")
            params.append(f"%{store}%")

        where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"""
            SELECT band_id, activation_code, claimed, created_at, claimed_at,
                   assigned_to, assigned_at, notes, batch_id, code_rotated_at
            FROM activation_codes
            {where_sql}
            ORDER BY
                CASE WHEN UPPER(band_id) ~ '^EB[0-9]+$'
                     THEN SUBSTRING(UPPER(band_id) FROM 3)::INTEGER
                     ELSE 2147483647 END DESC,
                band_id DESC
            LIMIT 1000
        """
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [item.name for item in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def counts(self) -> dict[str, int]:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE claimed = FALSE),
                           COUNT(*) FILTER (WHERE claimed = TRUE),
                           COUNT(*) FILTER (WHERE assigned_to IS NOT NULL AND assigned_to <> '')
                    FROM activation_codes
                    """
                )
                total, available, claimed, assigned = cur.fetchone()
        return {
            "total": total,
            "available": available,
            "claimed": claimed,
            "assigned": assigned,
        }

    def _next_sequence(self, cur) -> int:
        # The advisory transaction lock serializes simultaneous batch generation.
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (726381904,))
        cur.execute(
            """
            SELECT COALESCE(MAX(sequence_number), 0)
            FROM (
                SELECT SUBSTRING(UPPER(band_id) FROM 3)::INTEGER AS sequence_number
                FROM activation_codes
                WHERE UPPER(band_id) ~ '^EB[0-9]+$'
                UNION ALL
                SELECT SUBSTRING(UPPER(band_id) FROM 3)::INTEGER AS sequence_number
                FROM members
                WHERE UPPER(band_id) ~ '^EB[0-9]+$'
            ) AS all_ids
            """
        )
        return int(cur.fetchone()[0]) + 1

    def generate(self, count: int) -> GeneratedBatch:
        if count not in BATCH_SIZES:
            raise ValueError("Unsupported batch size.")
        batch_id = uuid.uuid4().hex
        records: list[dict] = []
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                next_number = self._next_sequence(cur)
                used_codes: set[str] = set()
                for offset in range(count):
                    band_id = format_band_id(next_number + offset)
                    while True:
                        code = generate_secure_code()
                        if code in used_codes:
                            continue
                        cur.execute(
                            "SELECT 1 FROM activation_codes WHERE activation_code = %s",
                            (code,),
                        )
                        if cur.fetchone() is None:
                            used_codes.add(code)
                            break
                    cur.execute(
                        """
                        INSERT INTO activation_codes (
                            band_id, activation_code, claimed, batch_id
                        ) VALUES (%s, %s, FALSE, %s)
                        """,
                        (band_id, code, batch_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO activation_code_audit (band_id, action, details)
                        VALUES (%s, 'GENERATED', %s)
                        """,
                        (band_id, f"batch={batch_id}"),
                    )
                    records.append({"band_id": band_id, "activation_code": code})
            conn.commit()
        return GeneratedBatch(batch_id=batch_id, records=records)

    def assign(self, band_id: str, assigned_to: str, notes: str) -> bool:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE activation_codes
                    SET assigned_to = NULLIF(%s, ''),
                        assigned_at = CASE WHEN %s = '' THEN NULL ELSE CURRENT_TIMESTAMP END,
                        notes = NULLIF(%s, '')
                    WHERE UPPER(band_id) = UPPER(%s) AND claimed = FALSE
                    """,
                    (assigned_to, assigned_to, notes, band_id),
                )
                updated = cur.rowcount == 1
                if updated:
                    cur.execute(
                        """
                        INSERT INTO activation_code_audit (band_id, action, details)
                        VALUES (%s, 'ASSIGNED', %s)
                        """,
                        (band_id.upper(), f"organization={assigned_to[:120]}"),
                    )
            conn.commit()
        return updated

    def rotate_unclaimed(self, band_id: str) -> str | None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT claimed FROM activation_codes
                    WHERE UPPER(band_id) = UPPER(%s)
                    FOR UPDATE
                    """,
                    (band_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                if row[0]:
                    raise ValueError("Claimed Safety IDs cannot be rotated here.")
                while True:
                    replacement = generate_secure_code()
                    cur.execute(
                        "SELECT 1 FROM activation_codes WHERE activation_code = %s",
                        (replacement,),
                    )
                    if cur.fetchone() is None:
                        break
                cur.execute(
                    """
                    UPDATE activation_codes
                    SET activation_code = %s,
                        code_rotated_at = CURRENT_TIMESTAMP
                    WHERE UPPER(band_id) = UPPER(%s) AND claimed = FALSE
                    """,
                    (replacement, band_id),
                )
                cur.execute(
                    """
                    INSERT INTO activation_code_audit (band_id, action, details)
                    VALUES (%s, 'ROTATED', 'Unused code revoked and replaced')
                    """,
                    (band_id.upper(),),
                )
            conn.commit()
        return replacement

    def records_for_print(self, band_id: str = "", batch_id: str = "", band_ids: list[str] | None = None) -> list[dict]:
        if not band_id and not batch_id:
            return []
        if band_id:
            where_sql, params = "UPPER(band_id) = UPPER(%s)", (band_id,)
        else:
            where_sql, params = "batch_id = %s", (batch_id,)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT band_id, activation_code, claimed, assigned_to, batch_id
                    FROM activation_codes
                    WHERE {where_sql}
                    ORDER BY band_id
                    """,
                    params,
                )
                return [
                    {
                        "band_id": row[0],
                        "activation_code": row[1],
                        "claimed": row[2],
                        "assigned_to": row[3],
                        "batch_id": row[4],
                    }
                    for row in cur.fetchall()
                ]


def _qr_data_uri(url: str) -> str:
    import base64

    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def register_activation_manager(
    app,
    database_url_getter: Callable[[], str | None],
    logo_url: str,
    base_url: str,
    repository_factory: Callable[[str], object] = PostgresActivationRepository,
) -> Blueprint:
    blueprint = Blueprint("activation_manager", __name__)

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("admin", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def csrf_token() -> str:
        token = session.get("activation_manager_csrf")
        if not token:
            token = secrets.token_urlsafe(32)
            session["activation_manager_csrf"] = token
        return token

    def require_csrf() -> None:
        submitted = request.form.get("csrf_token", "")
        expected = session.get("activation_manager_csrf", "")
        if not submitted or not expected or not hmac.compare_digest(submitted, expected):
            abort(400, description="Invalid or expired form token.")

    def repository():
        database_url = database_url_getter()
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        return repository_factory(database_url)

    @blueprint.after_request
    def secure_admin_response(response):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; base-uri 'none'; form-action 'self'"
        )
        return response

    @blueprint.route("/admin/activation-codes")
    @admin_required
    def activation_codes_index():
        query = request.args.get("q", "").strip()[:64]
        status = request.args.get("status", "all")
        if status not in {"all", "available", "claimed"}:
            status = "all"
        store = request.args.get("store", "").strip()[:120]
        try:
            repo = repository()
            records = repo.list_records(query=query, status=status, store=store)
            counts = repo.counts()
            database_error = ""
        except Exception:
            app.logger.error("Activation inventory could not be loaded")
            records, counts = [], {"total": 0, "available": 0, "claimed": 0, "assigned": 0}
            database_error = "Activation inventory is temporarily unavailable."
        return render_template(
            "admin_activation_codes.html",
            records=records,
            counts=counts,
            query=query,
            status=status,
            store=store,
            csrf_token=csrf_token(),
            batch_sizes=BATCH_SIZES,
            database_error=database_error,
        )

    @blueprint.post("/admin/activation-codes/generate")
    @admin_required
    def activation_codes_generate():
        require_csrf()
        try:
            count = int(request.form.get("count", "0"))
        except ValueError:
            count = 0
        if count not in BATCH_SIZES:
            abort(400, description="Unsupported batch size.")
        try:
            batch = repository().generate(count)
        except Exception:
            # Database exceptions can echo bound values. Never send code material
            # to application logs.
            app.logger.error("Activation code generation failed")
            flash("The Safety IDs could not be generated. No partial batch was saved.", "error")
            return redirect(url_for("activation_manager.activation_codes_index"))
        flash(f"Generated {count} available Safety ID{'s' if count != 1 else ''}.", "success")
        return redirect(
            url_for("activation_manager.activation_codes_index", batch=batch.batch_id)
        )

    @blueprint.post("/admin/activation-codes/assign")
    @admin_required
    def activation_codes_assign():
        require_csrf()
        band_id = request.form.get("band_id", "").strip().upper()
        assigned_to = request.form.get("assigned_to", "").strip()[:160]
        notes = request.form.get("notes", "").strip()[:1000]
        if not BAND_ID_RE.fullmatch(band_id):
            abort(400, description="Invalid Safety ID.")
        if not repository().assign(band_id, assigned_to, notes):
            abort(404, description="Safety ID not found.")
        flash(f"Updated store assignment for {band_id}.", "success")
        return redirect(url_for("activation_manager.activation_codes_index", q=band_id))

    @blueprint.post("/admin/activation-codes/rotate")
    @admin_required
    def activation_codes_rotate():
        require_csrf()
        band_id = request.form.get("band_id", "").strip().upper()
        confirmation = request.form.get("confirmation", "").strip().upper()
        if not BAND_ID_RE.fullmatch(band_id) or confirmation != band_id:
            abort(400, description="Safety ID confirmation did not match.")
        try:
            replacement = repository().rotate_unclaimed(band_id)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("activation_manager.activation_codes_index", q=band_id))
        if replacement is None:
            abort(404, description="Safety ID not found.")
        flash(f"The unused code for {band_id} was revoked and replaced.", "success")
        return redirect(url_for("activation_manager.activation_codes_index", q=band_id))

    @blueprint.get("/admin/activation-codes/export.csv")
    @admin_required
    def activation_codes_export():
        records = repository().list_records(
            query=request.args.get("q", "").strip()[:64],
            status=request.args.get("status", "all"),
            store=request.args.get("store", "").strip()[:120],
        )
        output = io.StringIO()
        fields = [
            "band_id", "activation_code", "claimed", "created_at", "claimed_at",
            "assigned_to", "assigned_at", "notes", "batch_id", "code_rotated_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: sanitize_csv_cell(record.get(key)) for key in fields})
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=empowerbands_activation_inventory.csv"
            },
        )

    @blueprint.get("/admin/activation-codes/print")
    @admin_required
    def activation_codes_print():
        band_id = request.args.get("band_id", "").strip().upper()
        batch_id = request.args.get("batch", "").strip()
        selected_ids = [value.strip().upper() for value in request.args.getlist("band_ids") if value.strip()]
        if band_id and not BAND_ID_RE.fullmatch(band_id):
            abort(400, description="Invalid Safety ID.")
        if any(not BAND_ID_RE.fullmatch(value) for value in selected_ids):
            abort(400, description="One or more Safety IDs are invalid.")
        if len(selected_ids) > 200:
            abort(400, description="Too many Safety IDs selected.")
        if batch_id and not re.fullmatch(r"[a-f0-9]{32}", batch_id):
            abort(400, description="Invalid batch reference.")
        records = repository().records_for_print(
            band_id=band_id,
            batch_id=batch_id,
            band_ids=selected_ids,
        )
        if not records:
            abort(404, description="No activation cards were found.")
        if any(record.get("claimed") for record in records):
            abort(409, description="Claimed Safety IDs cannot be printed as new activation cards.")
        base = base_url.rstrip("/")
        cards = []
        for record in records:
            activation_url = f"{base}/activate/{record['band_id']}"
            cards.append({**record, "activation_url": activation_url, "qr_data": _qr_data_uri(activation_url)})
        return render_template(
            "admin_activation_cards.html",
            cards=cards,
            logo_url=logo_url,
        )

    app.register_blueprint(blueprint)
    app.jinja_env.globals["activation_manager_csrf_token"] = csrf_token

    database_url = database_url_getter()
    if database_url:
        repository_factory(database_url).ensure_schema()
    return blueprint
