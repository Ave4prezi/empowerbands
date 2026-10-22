"""Administrator-only Key Finder inventory creation and private card printing."""
import base64
import csv
import io
import logging
import os
import re
import secrets
from functools import wraps

import psycopg
import qrcode
from flask import Blueprint, abort, redirect, render_template, request, session

from key_finder_backend import RECOVERY_RE, SERIAL_RE, _claim_digest
from scripts.import_key_finder_batch import import_rows

key_finder_admin = Blueprint('key_finder_admin', __name__)
FIELDS = ['activation_card_serial', 'nfc_recovery_identifier', 'nfc_recovery_url', 'hidden_activation_code']
RECOVERY_BASE = 'https://empowerbands.org/k/'
ACTIVATE_URL = 'https://www.empowerbands.org/key-finder/account'
logger = logging.getLogger(__name__)


def _activation_pepper():
    pepper = os.environ.get('KEY_FINDER_ACTIVATION_PEPPER', '')
    if len(pepper) < 32:
        raise RuntimeError('Key Finder activation security is not configured')
    return pepper


def initialize_key_finder_admin():
    logger.warning(
        'Key Finder configuration: activation_pepper=%s; email_delivery=%s',
        'ready' if len(os.environ.get('KEY_FINDER_ACTIVATION_PEPPER', '')) >= 32 else 'missing-or-short',
        'ready' if os.environ.get('RESEND_API_KEY') else 'missing',
    )
    if not os.environ.get('DATABASE_URL'):
        return
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS key_finder_admin_requests (
            request_id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )''')


def admin_required(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not session.get('logged_in'):
            # Preserve only known card destinations through administrator sign-in.
            session['finder_cards_after_login'] = (
                'pet-finder' if request.values.get('product') == 'pet-finder' else 'key-finder'
            )
            return redirect('/admin')
        try:
            return view(*args, **kwargs)
        except (psycopg.Error, RuntimeError, KeyError) as error:
            # Do not log SQL parameters, uploaded codes, connection strings or secret values.
            logger.error('Key Finder admin failed: operation=%s type=%s sqlstate=%s',
                         view.__name__, type(error).__name__, getattr(error, 'sqlstate', None))
            return 'Key Finder inventory is temporarily unavailable. Please try again later.', 503
    return guarded


@key_finder_admin.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


def _form_tokens():
    if not session.get('kf_admin_csrf'):
        session['kf_admin_csrf'] = secrets.token_urlsafe(32)
    if not session.get('kf_admin_request'):
        session['kf_admin_request'] = secrets.token_urlsafe(32)
    return {'csrf': session['kf_admin_csrf'], 'request_id': session['kf_admin_request']}


def _require_form():
    for field, key in [('csrf', 'kf_admin_csrf'), ('request_id', 'kf_admin_request')]:
        submitted, expected = request.form.get(field, ''), session.get(key, '')
        if not submitted or not expected or not secrets.compare_digest(submitted, expected):
            abort(403, 'Invalid or expired form. Return to Key Finder Inventory and try again.')
    return session['kf_admin_request']


def _reserve_request(conn, request_id):
    row = conn.execute('''INSERT INTO key_finder_admin_requests(request_id) VALUES (%s)
        ON CONFLICT DO NOTHING RETURNING request_id''', (request_id,)).fetchone()
    if not row:
        abort(409, 'This request was already processed. Return to inventory; do not submit it again.')


def generate_inventory(conn, count, product='key-finder'):
    _card_product(product)
    prefix = 'PF-' if product == 'pet-finder' else 'KF-'
    rows = []
    for _ in range(count):
        serial = prefix + secrets.token_hex(6).upper()
        token = secrets.token_hex(10).upper()
        code = secrets.token_hex(12).upper()
        conn.execute('''INSERT INTO key_finder_devices
            (serial, recovery_identifier, activation_secret_hash) VALUES (%s, %s, %s)''',
            (serial, token, _claim_digest('activation:' + serial + ':' + code)))
        rows.append(dict(zip(FIELDS, [serial, token, RECOVERY_BASE + token, code])))
    return rows


def parse_batch(raw):
    if len(raw) > 65536:
        raise ValueError('The CSV is too large. Import up to 100 Key Finders at a time.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
        raise ValueError('Choose the PRIVATE activation CSV containing serials, recovery links and hidden activation codes.')
    rows = []
    seen = [set(), set(), set()]
    for row in reader:
        serial, token, url, code = [(row.get(k) or '').strip() for k in FIELDS]
        serial, token, code = serial.upper(), token.upper(), code.upper()
        if (not SERIAL_RE.fullmatch(serial) or not RECOVERY_RE.fullmatch(token)
                or not re.fullmatch(r'[A-Z0-9]{24}', code) or url != RECOVERY_BASE + token):
            raise ValueError('A row has invalid activation details. No records were imported.')
        for value, values in zip([serial, token, code], seen):
            if value in values:
                raise ValueError('The CSV has duplicate serials, links or codes. No records were imported.')
            values.add(value)
        rows.append(dict(zip(FIELDS, [serial, token, url, code])))
        if len(rows) > 100:
            raise ValueError('Import up to 100 Key Finders at a time.')
    if not rows:
        raise ValueError('The CSV contains no Key Finders.')
    return rows


def _card_product(value):
    if value not in ('key-finder', 'pet-finder'):
        abort(400, 'Choose Key Finder or Pet Finder cards.')
    return 'Pet Finder' if value == 'pet-finder' else 'Key Finder'


def _cards(rows, skipped=0, product_name='Key Finder'):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    qr = io.BytesIO()
    qrcode.make(ACTIVATE_URL).save(qr, format='PNG')
    return render_template('admin_key_finder_cards.html', rows=rows, skipped=skipped,
        csv_text=output.getvalue(), activate_url=ACTIVATE_URL, product_name=product_name,
        qr_data=base64.b64encode(qr.getvalue()).decode())


@key_finder_admin.get('/admin/key-finders')
@admin_required
def inventory():
    product = request.args.get('product', 'key-finder')
    _card_product(product)
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        counts = conn.execute('''SELECT COUNT(*), COUNT(*) FILTER (WHERE activated_at IS NOT NULL)
            FROM key_finder_devices''').fetchone()
        devices = conn.execute('''SELECT serial, recovery_identifier, activated_at IS NOT NULL
            FROM key_finder_devices ORDER BY created_at DESC, serial LIMIT 500''').fetchall()
    return render_template('admin_key_finders.html', counts=counts, devices=devices,
        recovery_base=RECOVERY_BASE, product=product, **_form_tokens())


@key_finder_admin.post('/admin/key-finders/generate')
@admin_required
def generate():
    request_id = _require_form()
    product_name = _card_product(request.form.get('product', 'key-finder'))
    try:
        count = int(request.form.get('count', ''))
    except ValueError:
        abort(400, 'Choose a quantity from 1 to 100.')
    if not 1 <= count <= 100:
        abort(400, 'Choose a quantity from 1 to 100.')
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        _reserve_request(conn, request_id)
        rows = generate_inventory(conn, count, request.form.get('product', 'key-finder'))
        page = _cards(rows, product_name=product_name)  # Render before committing inventory.
    session.pop('kf_admin_request', None)
    return page


@key_finder_admin.post('/admin/key-finders/import')
@admin_required
def import_batch():
    # Bound the whole request before parsing a multipart upload.
    if request.content_length is None or request.content_length > 131072:
        abort(413, 'Choose a CSV smaller than 64 KB.')
    request_id = _require_form()
    product_name = _card_product(request.form.get('product', 'key-finder'))
    upload = request.files.get('batch_csv')
    if upload is None:
        abort(400, 'Choose your private activation CSV.')
    try:
        rows = parse_batch(upload.read(65537))
        pepper = _activation_pepper()
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            _reserve_request(conn, request_id)
            import_rows(conn, [(r[FIELDS[0]], r[FIELDS[1]], r[FIELDS[3]]) for r in rows],
                        pepper)
            # Lock inventory through commit so an activation cannot race card selection.
            available = {r[0] for r in conn.execute('''SELECT serial FROM key_finder_devices
                WHERE serial = ANY(%s) AND activated_at IS NULL FOR UPDATE''',
                ([r[FIELDS[0]] for r in rows],)).fetchall()}
            printable = [r for r in rows if r[FIELDS[0]] in available]
            page = _cards(printable, len(rows) - len(printable), product_name=product_name)
    except (ValueError, UnicodeError):
        abort(400, 'This CSV could not be verified. No records changed. Check the private file and current activation pepper; existing codes will not be overwritten.')
    session.pop('kf_admin_request', None)
    return page


@key_finder_admin.get('/admin/key-finders/import')
@key_finder_admin.get('/admin/key-finders/generate')
@admin_required
def return_to_inventory():
    return redirect('/admin/key-finders')
