"""PayPal Orders v2 checkout for physical EmpowerBands Safety IDs."""
import base64
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.request
from decimal import Decimal
from flask import Blueprint, jsonify, render_template, request, session
import psycopg

checkout = Blueprint("checkout", __name__)
log = logging.getLogger(__name__)
PRICES = {1: Decimal("24.99"), 2: Decimal("49.99")}
SKU = "EMPOWERBANDS-SAFETY-ID"

def configured():
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET") and os.getenv("DATABASE_URL"))

def api_base():
    return "https://api-m.paypal.com" if os.getenv("PAYPAL_MODE", "sandbox").lower() == "live" else "https://api-m.sandbox.paypal.com"

def paypal_request(method, path, token=None, payload=None, request_id=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    else:
        raw = (os.environ["PAYPAL_CLIENT_ID"] + ":" + os.environ["PAYPAL_CLIENT_SECRET"]).encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(api_base() + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def access_token():
    headers = {
        "Authorization": "Basic " + base64.b64encode(
            (os.environ["PAYPAL_CLIENT_ID"] + ":" + os.environ["PAYPAL_CLIENT_SECRET"]).encode()
        ).decode(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req = urllib.request.Request(api_base() + "/v1/oauth2/token",
        data=b"grant_type=client_credentials", headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)["access_token"]

def init_orders():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS safety_id_orders (
                    paypal_order_id TEXT PRIMARY KEY,
                    checkout_nonce TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    amount_usd NUMERIC(10,2) NOT NULL,
                    status TEXT NOT NULL DEFAULT 'CREATED',
                    capture_id TEXT UNIQUE,
                    payer_email TEXT,
                    shipping_name TEXT,
                    shipping_address JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    paid_at TIMESTAMPTZ
                )
            """)

def failure(message, status=400):
    return jsonify({"error": message}), status

@checkout.get("/order")
def order_page():
    return render_template("order.html",
        paypal_client_id=os.getenv("PAYPAL_CLIENT_ID", "") if configured() else "",
        paypal_enabled=configured(),
        paypal_mode=os.getenv("PAYPAL_MODE", "sandbox").lower())

@checkout.post("/api/checkout/orders")
def create_order():
    if not configured():
        return failure("Checkout is temporarily unavailable.", 503)
    data = request.get_json(silent=True) or {}
    qty = data.get("quantity")
    if type(qty) is not int or qty not in PRICES:
        return failure("Choose one or two Safety IDs.")
    nonce = secrets.token_urlsafe(24)
    try:
        token = access_token()
        order = paypal_request("POST", "/v2/checkout/orders", token, {
            "intent": "CAPTURE",
            "purchase_units": [{
                "description": "EmpowerBands Safety ID" + (" bundle (2)" if qty == 2 else ""),
                "custom_id": SKU + "-" + str(qty),
                "amount": {"currency_code": "USD", "value": str(PRICES[qty])},
                "shipping": {"type": "SHIPPING"}
            }],
            "payment_source": {"paypal": {"experience_context": {
                "shipping_preference": "GET_FROM_FILE",
                "user_action": "PAY_NOW"
            }}}
        }, request_id=nonce)
        order_id = order["id"]
        init_orders()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO safety_id_orders
                    (paypal_order_id, checkout_nonce, quantity, amount_usd)
                    VALUES (%s, %s, %s, %s)""",
                    (order_id, nonce, qty, PRICES[qty]))
        session["paypal_checkout_nonce"] = nonce
        return jsonify({"id": order_id})
    except (urllib.error.URLError, KeyError, ValueError, psycopg.Error):
        log.exception("PayPal order creation failed")
        return failure("Unable to start checkout. Please try again.", 502)

@checkout.post("/api/checkout/orders/<order_id>/capture")
def capture_order(order_id):
    if not configured():
        return failure("Checkout is temporarily unavailable.", 503)
    if not re.fullmatch(r"[A-Za-z0-9]{10,40}", order_id):
        return failure("Invalid order.")
    nonce = session.get("paypal_checkout_nonce")
    if not nonce:
        return failure("Checkout session expired. Start again.", 403)
    try:
        init_orders()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT checkout_nonce, quantity, amount_usd, status
                    FROM safety_id_orders WHERE paypal_order_id = %s""", (order_id,))
                row = cur.fetchone()
        if not row or not secrets.compare_digest(row[0], nonce):
            return failure("Order does not match this checkout session.", 403)
        if row[3] == "COMPLETED":
            return jsonify({"status": "COMPLETED", "id": order_id})
        token = access_token()
        result = paypal_request("POST", "/v2/checkout/orders/" + order_id + "/capture",
            token, {}, request_id="capture-" + order_id)
        units = result.get("purchase_units") or []
        captures = units[0].get("payments", {}).get("captures", []) if units else []
        cap = captures[0] if captures else {}
        amount = cap.get("amount") or {}
        if (result.get("status") != "COMPLETED" or cap.get("status") != "COMPLETED"
                or amount.get("currency_code") != "USD"
                or Decimal(str(amount.get("value", "0"))) != row[2]):
            return failure("Payment has not been confirmed. Contact support if charged.", 409)
        payer = result.get("payer") or {}
        shipping = units[0].get("shipping") or {}
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE safety_id_orders SET status='COMPLETED',
                    capture_id=%s, payer_email=%s, shipping_name=%s,
                    shipping_address=%s::jsonb, paid_at=NOW()
                    WHERE paypal_order_id=%s AND status='CREATED'""",
                    (cap["id"], payer.get("email_address"),
                     (shipping.get("name") or {}).get("full_name"),
                     json.dumps(shipping.get("address") or {}), order_id))
        session.pop("paypal_checkout_nonce", None)
        return jsonify({"status": "COMPLETED", "id": order_id})
    except (urllib.error.URLError, KeyError, ValueError, psycopg.Error):
        log.exception("PayPal capture failed")
        return failure("Could not confirm payment. Do not retry payment; contact support.", 502)
