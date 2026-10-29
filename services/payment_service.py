import json
import uuid
import time
import random
from datetime import datetime
from database import get_db_connection

class ServiceValidationError(Exception):
    def __init__(self, message, code="VALIDATION_FAILED", details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

class EcommercePaymentAdapter:
    """
    Adapter specialization for E-Commerce Retail App (e.g., NovaShop / Amazon-like).
    Caters to:
    - Cart items total validation
    - Promotional coupon code deduction
    - Shipping tax and net total calculation
    - Card / Wallet / COD payment methods
    - Instant order confirmation & stock deduction
    """
    CLIENT_TYPE = "ecommerce"

    def pre_validate(self, payload):
        items = payload.get("items", [])
        if not items:
            raise ServiceValidationError("E-Commerce transaction requires at least 1 item in the cart.", "EMPTY_CART")
        
        customer_name = payload.get("customer_name")
        shipping_address = payload.get("shipping_address")
        if not customer_name or not shipping_address:
            raise ServiceValidationError("Customer name and shipping address are required for checkout.", "MISSING_SHIPPING_INFO")

        # Calculate subtotal and verify stock in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        computed_subtotal = 0.0

        for item in items:
            p_id = item.get("id")
            qty = int(item.get("quantity", 1))
            cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (p_id,))
            prod = cursor.fetchone()
            if not prod:
                conn.close()
                raise ServiceValidationError(f"Product ID {p_id} not found in inventory.", "ITEM_NOT_FOUND")
            if prod["stock"] < qty:
                conn.close()
                raise ServiceValidationError(f"Insufficient stock for {prod['name']}. Available: {prod['stock']}", "STOCK_DEPLETED")
            computed_subtotal += prod["price"] * qty

        # Validate Coupon
        coupon_code = payload.get("coupon_code", "").strip().upper()
        discount_amount = 0.0
        if coupon_code:
            cursor.execute("SELECT * FROM coupons WHERE code = ? AND active = 1", (coupon_code,))
            coupon = cursor.fetchone()
            if coupon:
                if computed_subtotal >= coupon["min_spend"]:
                    potential_discount = (computed_subtotal * coupon["discount_percent"]) / 100.0
                    discount_amount = min(potential_discount, coupon["max_discount"])
                else:
                    conn.close()
                    raise ServiceValidationError(f"Coupon {coupon_code} requires minimum purchase of ${coupon['min_spend']:.2f}", "COUPON_MIN_NOT_MET")
            else:
                conn.close()
                raise ServiceValidationError(f"Invalid or expired promo code: {coupon_code}", "INVALID_COUPON")

        conn.close()

        shipping_fee = 0.0 if computed_subtotal > 100.0 else 9.99
        final_amount = round(computed_subtotal - discount_amount + shipping_fee, 2)

        # Standard payment processing fee for merchant (absorbed or logged)
        processing_fee = round(final_amount * 0.024 + 0.30, 2)

        return {
            "amount": final_amount,
            "subtotal": round(computed_subtotal, 2),
            "discount_amount": round(discount_amount, 2),
            "shipping_fee": shipping_fee,
            "fee": processing_fee,
            "payment_method": payload.get("payment_method", "credit_card"),
            "source_account": f"CARD-****-****-{random.randint(1000, 9999)}",
            "target_account": "ACC-88301124", # NovaShop Merchant Account
            "currency": "USD",
            "requires_challenge": False,
            "meta": {
                "order_number": f"ORD-{int(time.time())}-{random.randint(100, 999)}",
                "customer_name": customer_name,
                "customer_email": payload.get("customer_email", "customer@example.com"),
                "shipping_address": shipping_address,
                "items": items,
                "coupon_code": coupon_code or None
            }
        }

    def post_settle(self, tx_id, context):
        """
        Deducts warehouse stock and creates confirmed order.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        meta = context["meta"]

        # Reduce stock
        for item in meta["items"]:
            cursor.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (int(item.get("quantity", 1)), item["id"])
            )

        # Record Order
        cursor.execute('''
            INSERT INTO orders (
                order_number, customer_name, customer_email, shipping_address,
                total_amount, discount_amount, shipping_fee, final_amount,
                status, payment_transaction_id, items_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            meta["order_number"],
            meta["customer_name"],
            meta["customer_email"],
            meta["shipping_address"],
            context["subtotal"],
            context["discount_amount"],
            context["shipping_fee"],
            context["amount"],
            "CONFIRMED",
            tx_id,
            json.dumps(meta["items"])
        ))

        # Credit Merchant Account
        cursor.execute(
            "UPDATE accounts SET balance = balance + ? WHERE account_number = 'ACC-88301124'",
            (context["amount"] - context["fee"],)
        )

        conn.commit()
        conn.close()

        return {
            "order_number": meta["order_number"],
            "delivery_estimate": "2-3 Business Days",
            "receipt_url": f"/api/ecommerce/orders/{meta['order_number']}/receipt"
        }


class BankingPaymentAdapter:
    """
    Adapter specialization for Core Banking Application (e.g., Apex Bank Portal).
    Caters to:
    - Account balance verification
    - Daily transfer limit checking
    - Mandatory 2FA OTP challenge for high-value transfers (>= $500.00)
    - Wire / Transfer fees
    - Sender balance deduction and beneficiary balance credit
    """
    CLIENT_TYPE = "banking"

    def pre_validate(self, payload):
        source_account = payload.get("source_account")
        target_account = payload.get("target_account")
        amount = float(payload.get("amount", 0.0))
        transfer_speed = payload.get("transfer_speed", "IMPS") # IMPS, NEFT, WIRE

        if not source_account or not target_account:
            raise ServiceValidationError("Source and target account numbers are required.", "MISSING_ACCOUNTS")
        if source_account == target_account:
            raise ServiceValidationError("Source and destination accounts cannot be identical.", "SAME_ACCOUNT")
        if amount <= 0:
            raise ServiceValidationError("Transfer amount must be greater than zero.", "INVALID_AMOUNT")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE account_number = ?", (source_account,))
        src = cursor.fetchone()
        if not src:
            conn.close()
            raise ServiceValidationError("Source bank account not found.", "SOURCE_NOT_FOUND")

        # Check balance
        fee = 0.0
        if transfer_speed == "WIRE":
            fee = 15.00
        elif transfer_speed == "EXPRESS":
            fee = 3.50
        else: # IMPS / ACH
            fee = 0.50

        total_debit = amount + fee
        if src["balance"] < total_debit:
            conn.close()
            raise ServiceValidationError(f"Insufficient funds. Required: ${total_debit:.2f}, Available: ${src['balance']:.2f}", "INSUFFICIENT_FUNDS")

        # Check daily limit
        new_spent = src["spent_today"] + amount
        if new_spent > src["daily_limit"]:
            conn.close()
            raise ServiceValidationError(f"Transfer exceeds daily allowance. Limit: ${src['daily_limit']:.2f}, Remaining: ${src['daily_limit'] - src['spent_today']:.2f}", "EXCEEDS_DAILY_LIMIT")

        conn.close()

        # Security policy: Transfers >= $500 require 2-Factor OTP verification
        requires_challenge = amount >= 500.0
        otp_code = str(random.randint(100000, 999999)) if requires_challenge else None

        return {
            "amount": amount,
            "fee": fee,
            "source_account": source_account,
            "target_account": target_account,
            "currency": src["currency"],
            "requires_challenge": requires_challenge,
            "otp_code": otp_code,
            "meta": {
                "transfer_speed": transfer_speed,
                "memo": payload.get("memo", "Direct Bank Transfer"),
                "beneficiary_name": payload.get("beneficiary_name", "Registered Beneficiary"),
                "sender_name": src["holder_name"]
            }
        }

    def post_settle(self, tx_id, context):
        """
        Deducts balance from sender and credits recipient.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        amount = context["amount"]
        fee = context["fee"]
        src_acc = context["source_account"]
        tgt_acc = context["target_account"]

        # Deduct from source
        cursor.execute(
            "UPDATE accounts SET balance = balance - ?, spent_today = spent_today + ? WHERE account_number = ?",
            (amount + fee, amount, src_acc)
        )

        # Credit destination if local account
        cursor.execute("SELECT id FROM accounts WHERE account_number = ?", (tgt_acc,))
        dest = cursor.fetchone()
        if dest:
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?", (amount, tgt_acc))
        else:
            # External banking node clearing simulation
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = 'ACC-99412033'", (amount,))

        conn.commit()
        conn.close()

        return {
            "transfer_reference": f"TX-WIRE-{tx_id[:8].upper()}",
            "clearing_status": "REALTIME_SETTLED",
            "statement_narrative": f"Transfer to {context['meta']['beneficiary_name']}: -${amount + fee:.2f}"
        }


class PaymentEnterpriseService:
    """
    Central Reusable Service for SOA Platform.
    Adheres to SOA design principles:
    - Service Reusability (single engine for multiple consumer apps)
    - Service Abstraction (consumer apps don't know ledger internals)
    - Service Contract (standard request/response schema)
    - Policy Customization via App-specific Adapters
    - Integrated Risk Assessment & Observability Audit Trail
    """
    def __init__(self):
        self.adapters = {
            "ecommerce": EcommercePaymentAdapter(),
            "banking": BankingPaymentAdapter()
        }

    def get_adapter(self, client_type):
        adapter = self.adapters.get(client_type)
        if not adapter:
            raise ServiceValidationError(f"Unknown client type '{client_type}'. Supported clients: {list(self.adapters.keys())}", "UNKNOWN_CLIENT")
        return adapter

    def assess_risk(self, amount, client_type, metadata):
        """
        Reusable Risk & Fraud Assessment Component
        """
        risk_score = 0
        if amount > 5000:
            risk_score += 45
        elif amount > 1000:
            risk_score += 20
        else:
            risk_score += 5

        # Check anomaly heuristic
        if client_type == "banking" and metadata.get("transfer_speed") == "WIRE":
            risk_score += 15

        decision = "APPROVE"
        if risk_score > 70:
            decision = "CHALLENGE"
        return risk_score, decision

    def process_payment(self, client_type, payload):
        start_time = time.time()
        adapter = self.get_adapter(client_type)

        # 1. Adapter Pre-Validation & Domain Normalization
        normalized = adapter.pre_validate(payload)

        # 2. Idempotency Check
        idempotency_key = payload.get("idempotency_key") or str(uuid.uuid4())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE idempotency_key = ?", (idempotency_key,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return self._build_transaction_response(existing, "IDEMPOTENT_REPLAY")

        # 3. Core Enterprise Risk Scoring
        risk_score, risk_decision = self.assess_risk(normalized["amount"], client_type, normalized["meta"])

        tx_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        status = "CHALLENGE_REQUIRED" if normalized["requires_challenge"] else "SETTLED"

        # 4. Insert into Unified Ledger
        cursor.execute('''
            INSERT INTO transactions (
                id, client_app, transaction_type, source_account, target_account,
                amount, fee, currency, status, idempotency_key, risk_score,
                risk_decision, client_metadata, otp_code, otp_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tx_id,
            client_type,
            "ORDER_PURCHASE" if client_type == "ecommerce" else "FUNDS_TRANSFER",
            normalized["source_account"],
            normalized["target_account"],
            normalized["amount"],
            normalized["fee"],
            normalized["currency"],
            status,
            idempotency_key,
            risk_score,
            risk_decision,
            json.dumps(normalized["meta"]),
            normalized.get("otp_code"),
            0 if normalized["requires_challenge"] else 1
        ))
        conn.commit()
        conn.close()

        # 5. Post-settlement action if not challenged
        adapter_output = {}
        if status == "SETTLED":
            adapter_output = adapter.post_settle(tx_id, normalized)

        # 6. Audit Trail Logging
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        self._record_audit_trace(tx_id, client_type, "/api/payment-service/process", execution_time_ms, 200, payload, {
            "transaction_id": tx_id,
            "status": status,
            "amount": normalized["amount"],
            "fee": normalized["fee"]
        })

        return {
            "success": True,
            "transaction_id": tx_id,
            "client_app": client_type,
            "status": status,
            "amount": normalized["amount"],
            "fee": normalized["fee"],
            "currency": normalized["currency"],
            "requires_otp": normalized["requires_challenge"],
            "otp_challenge_hint": f"Enter OTP sent to your registered phone (Demo OTP: {normalized.get('otp_code')})" if normalized.get("otp_code") else None,
            "risk_score": risk_score,
            "risk_decision": risk_decision,
            "adapter_result": adapter_output,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

    def verify_challenge(self, tx_id, otp_code):
        """
        Fulfills 2-Factor Authentication step for banking transactions requiring challenge
        """
        start_time = time.time()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        tx = cursor.fetchone()
        if not tx:
            conn.close()
            raise ServiceValidationError("Transaction not found.", "NOT_FOUND")

        if tx["status"] != "CHALLENGE_REQUIRED":
            conn.close()
            raise ServiceValidationError(f"Transaction is already in status '{tx['status']}'", "INVALID_STATE")

        if tx["otp_code"] != otp_code.strip():
            conn.close()
            raise ServiceValidationError("Invalid 2FA Passcode. Verification failed.", "OTP_MISMATCH")

        # Update status to SETTLED
        cursor.execute("UPDATE transactions SET status = 'SETTLED', otp_verified = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()

        # Call Adapter post-settle
        adapter = self.get_adapter(tx["client_app"])
        normalized = {
            "amount": tx["amount"],
            "fee": tx["fee"],
            "source_account": tx["source_account"],
            "target_account": tx["target_account"],
            "meta": json.loads(tx["client_metadata"] or "{}")
        }
        adapter_output = adapter.post_settle(tx_id, normalized)

        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        self._record_audit_trace(tx_id, tx["client_app"], "/api/payment-service/verify-challenge", execution_time_ms, 200, {"tx_id": tx_id}, {"status": "SETTLED"})

        return {
            "success": True,
            "transaction_id": tx_id,
            "status": "SETTLED",
            "message": "Security verification successful. Funds transferred.",
            "adapter_result": adapter_output
        }

    def get_transaction_details(self, tx_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise ServiceValidationError("Transaction not found", "NOT_FOUND")
        return dict(row)

    def _record_audit_trace(self, tx_id, client_app, endpoint, exec_ms, status_code, req_obj, res_obj):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_traces (
                    transaction_id, client_app, service_name, endpoint,
                    execution_time_ms, status_code, request_payload, response_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx_id,
                client_app,
                "PaymentEnterpriseService",
                endpoint,
                exec_ms,
                status_code,
                json.dumps(req_obj, default=str),
                json.dumps(res_obj, default=str)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print("Audit trace recording failed:", e)

    def _build_transaction_response(self, tx_row, note):
        return {
            "success": True,
            "transaction_id": tx_row["id"],
            "client_app": tx_row["client_app"],
            "status": tx_row["status"],
            "amount": tx_row["amount"],
            "fee": tx_row["fee"],
            "currency": tx_row["currency"],
            "risk_score": tx_row["risk_score"],
            "risk_decision": tx_row["risk_decision"],
            "note": note,
            "created_at": tx_row["created_at"]
        }

# Global singleton instance of the reusable payment service
payment_service = PaymentEnterpriseService()
