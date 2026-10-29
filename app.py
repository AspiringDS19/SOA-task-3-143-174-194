import os
import json
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from database import init_db, get_db_connection, seed_data
from services.payment_service import payment_service, ServiceValidationError
from services.soa_registry import get_soa_service_definition, get_soa_telemetry

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Ensure database is created and seeded
init_db()

# ============================================================================
# FRONTEND ROUTE
# ============================================================================
@app.route("/")
def index():
    return render_template("index.html")


# ============================================================================
# APPLICATION 1: E-COMMERCE CLIENT API (NovaShop)
# ============================================================================
@app.route("/api/ecommerce/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "products": products})

@app.route("/api/ecommerce/orders", methods=["GET"])
def get_orders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 20")
    orders = []
    for r in cursor.fetchall():
        order_dict = dict(r)
        try:
            order_dict["items"] = json.loads(order_dict["items_json"])
        except Exception:
            order_dict["items"] = []
        orders.append(order_dict)
    conn.close()
    return jsonify({"success": True, "orders": orders})

@app.route("/api/ecommerce/validate-coupon", methods=["POST"])
def validate_coupon():
    data = request.get_json() or {}
    code = (data.get("code") or "").strip().upper()
    subtotal = float(data.get("subtotal", 0.0))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons WHERE code = ? AND active = 1", (code,))
    coupon = cursor.fetchone()
    conn.close()

    if not coupon:
        return jsonify({"success": False, "message": "Invalid or expired promo code."}), 400

    if subtotal < coupon["min_spend"]:
        return jsonify({
            "success": False,
            "message": f"Code {code} requires a minimum order of ${coupon['min_spend']:.2f}"
        }), 400

    discount = min((subtotal * coupon["discount_percent"]) / 100.0, coupon["max_discount"])
    return jsonify({
        "success": True,
        "code": code,
        "discount_percent": coupon["discount_percent"],
        "discount_amount": round(discount, 2),
        "message": f"Promo code {code} applied! Saved ${discount:.2f}"
    })

@app.route("/api/ecommerce/checkout", methods=["POST"])
def ecommerce_checkout():
    """
    E-Commerce checkout endpoint:
    Uses the Reusable Payment Service via the 'ecommerce' adapter.
    """
    payload = request.get_json() or {}
    try:
        # Invoking the shared SOA Payment Service
        result = payment_service.process_payment("ecommerce", payload)
        return jsonify(result), 200
    except ServiceValidationError as e:
        return jsonify({"success": False, "error": e.message, "code": e.code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "code": "INTERNAL_ERROR"}), 500


# ============================================================================
# APPLICATION 2: CORE BANKING CLIENT API (Apex Bank)
# ============================================================================
@app.route("/api/banking/accounts", methods=["GET"])
def get_banking_accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE account_number LIKE 'ACC-1%' OR account_number LIKE 'ACC-2%'")
    accounts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "accounts": accounts})

@app.route("/api/banking/beneficiaries", methods=["GET"])
def get_beneficiaries():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM beneficiaries")
    beneficiaries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "beneficiaries": beneficiaries})

@app.route("/api/banking/transfer", methods=["POST"])
def banking_transfer():
    """
    Banking Funds Transfer endpoint:
    Uses the Reusable Payment Service via the 'banking' adapter.
    Triggers 2FA OTP challenge if transfer amount >= $500.
    """
    payload = request.get_json() or {}
    try:
        # Invoking the shared SOA Payment Service
        result = payment_service.process_payment("banking", payload)
        return jsonify(result), 200
    except ServiceValidationError as e:
        return jsonify({"success": False, "error": e.message, "code": e.code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "code": "INTERNAL_ERROR"}), 500

@app.route("/api/banking/verify-otp", methods=["POST"])
def banking_verify_otp():
    """
    Second-phase commit for banking transactions challenged with 2FA OTP.
    """
    payload = request.get_json() or {}
    tx_id = payload.get("transaction_id")
    otp_code = payload.get("otp_code")
    if not tx_id or not otp_code:
        return jsonify({"success": False, "error": "Transaction ID and OTP code are required."}), 400

    try:
        result = payment_service.verify_challenge(tx_id, otp_code)
        return jsonify(result), 200
    except ServiceValidationError as e:
        return jsonify({"success": False, "error": e.message, "code": e.code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/banking/statement", methods=["GET"])
def get_banking_statement():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM transactions 
        WHERE client_app = 'banking' 
        ORDER BY created_at DESC 
        LIMIT 20
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        try:
            r["metadata"] = json.loads(r["client_metadata"] or "{}")
        except Exception:
            r["metadata"] = {}
    conn.close()
    return jsonify({"success": True, "statement": rows})


# ============================================================================
# REUSABLE SOA PAYMENT SERVICE DIRECT ENDPOINTS
# ============================================================================
@app.route("/api/payment-service/process", methods=["POST"])
def direct_payment_process():
    data = request.get_json() or {}
    client_type = data.get("client_type")
    payload = data.get("payload") or data
    if not client_type:
        return jsonify({"success": False, "error": "client_type ('ecommerce' or 'banking') must be specified in the SOA contract header/body."}), 400
    try:
        result = payment_service.process_payment(client_type, payload)
        return jsonify(result), 200
    except ServiceValidationError as e:
        return jsonify({"success": False, "error": e.message, "code": e.code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/payment-service/transactions/<tx_id>", methods=["GET"])
def get_transaction(tx_id):
    try:
        tx = payment_service.get_transaction_details(tx_id)
        return jsonify({"success": True, "transaction": tx}), 200
    except ServiceValidationError as e:
        return jsonify({"success": False, "error": e.message}), 404


# ============================================================================
# SOA OBSERVABILITY, REGISTRY & TELEMETRY
# ============================================================================
@app.route("/api/soa/definition", methods=["GET"])
def get_definition():
    return jsonify(get_soa_service_definition())

@app.route("/api/soa/telemetry", methods=["GET"])
def get_telemetry():
    return jsonify(get_soa_telemetry())

@app.route("/api/soa/reset-demo", methods=["POST"])
def reset_demo():
    """
    Clears transactions and resets sample account balances/stock for a fresh demo presentation.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM audit_traces")
    cursor.execute("UPDATE accounts SET balance = 12450.00, spent_today = 320.0 WHERE account_number = 'ACC-10098421'")
    cursor.execute("UPDATE accounts SET balance = 48750.00, spent_today = 0.0 WHERE account_number = 'ACC-20048190'")
    cursor.execute("UPDATE accounts SET balance = 94320.00 WHERE account_number = 'ACC-88301124'")
    cursor.execute("UPDATE products SET stock = 25 WHERE id = 1")
    cursor.execute("UPDATE products SET stock = 14 WHERE id = 2")
    cursor.execute("UPDATE products SET stock = 8 WHERE id = 3")
    cursor.execute("UPDATE products SET stock = 30 WHERE id = 4")
    cursor.execute("UPDATE products SET stock = 10 WHERE id = 5")
    cursor.execute("UPDATE products SET stock = 40 WHERE id = 6")
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Demo data reset successfully."})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
