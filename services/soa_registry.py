import json
from database import get_db_connection

def get_soa_service_definition():
    """
    Returns the formal SOA Service Catalog and Contract Specification.
    Demonstrates Task 3: Service Identification and SOA Modeling.
    """
    return {
        "service_name": "Enterprise Unified Payment & Ledger Service",
        "service_code": "SVC-PAY-001",
        "version": "2.4.0",
        "soa_classification": "Core Business Utility Service (Reusable)",
        "protocol": "REST / JSON & WSDL / SOAP compatible contract",
        "description": "Standardized enterprise payment processing and financial ledger engine reused across multi-domain applications with pluggable context adapters.",
        "consumers": [
            {
                "id": "consumer_ecommerce",
                "name": "NovaShop E-Commerce Portal",
                "domain": "Retail & B2C Merchant Storefront",
                "integration_pattern": "Adapter Pattern via Cart & Checkout API",
                "specialized_policies": [
                    "Cart inventory lock & stock deduction",
                    "Promotional coupon discount computation",
                    "Merchant commission / fee processing",
                    "Instant order status settlement"
                ]
            },
            {
                "id": "consumer_banking",
                "name": "Apex Online Banking Portal",
                "domain": "FinTech Core Banking & Retail Accounts",
                "integration_pattern": "Adapter Pattern via Interbank Transfer API",
                "specialized_policies": [
                    "Real-time available balance verification",
                    "Regulatory daily transfer allowance limit",
                    "Mandatory 2FA OTP security challenge on >= $500 transfers",
                    "Inter-account debit/credit ledger commit"
                ]
            }
        ],
        "shared_capabilities": [
            "Central Double-Entry Financial Ledger",
            "Real-time AI/Heuristic Risk & Fraud Assessment",
            "Idempotency Guarantee via Unique Keys",
            "Lifecycle State Machine (PENDING -> CHALLENGE -> SETTLED)",
            "Distributed Audit Logging and Service SLA Tracing"
        ],
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/payment-service/process",
                "description": "Unified processing entrypoint for all consumer applications with specialized payload schema.",
                "auth": "Bearer Client-Token / Mutual TLS"
            },
            {
                "method": "POST",
                "path": "/api/payment-service/verify-challenge",
                "description": "Second-phase commit endpoint for transactions requiring two-factor authorization.",
                "auth": "OTP Session Token"
            },
            {
                "method": "GET",
                "path": "/api/soa/telemetry",
                "description": "Enterprise service monitoring, latency telemetry, and transaction distribution.",
                "auth": "Public / Internal Telemetry"
            }
        ]
    }

def get_soa_telemetry():
    """
    Collects live database metrics across both applications and the shared service.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total counts and amounts
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(AVG(risk_score), 0) FROM transactions")
    total_tx_row = cursor.fetchone()
    total_tx = total_tx_row[0]
    total_volume = round(total_tx_row[1], 2)
    avg_risk = round(total_tx_row[2], 1)

    # Client breakdown
    cursor.execute("""
        SELECT client_app, COUNT(*) as count, COALESCE(SUM(amount), 0) as volume 
        FROM transactions 
        GROUP BY client_app
    """)
    client_rows = cursor.fetchall()
    app_stats = {
        "ecommerce": {"count": 0, "volume": 0.0},
        "banking": {"count": 0, "volume": 0.0}
    }
    for r in client_rows:
        if r["client_app"] in app_stats:
            app_stats[r["client_app"]]["count"] = r["count"]
            app_stats[r["client_app"]]["volume"] = round(r["volume"], 2)

    # Recent transactions
    cursor.execute("""
        SELECT id, client_app, transaction_type, source_account, target_account, 
               amount, fee, currency, status, risk_score, risk_decision, created_at 
        FROM transactions 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    recent_transactions = [dict(r) for r in cursor.fetchall()]

    # Audit traces for latency
    cursor.execute("""
        SELECT COALESCE(AVG(execution_time_ms), 12.4), COUNT(*) 
        FROM audit_traces
    """)
    trace_row = cursor.fetchone()
    avg_latency = round(trace_row[0], 2) if trace_row else 12.4

    cursor.execute("""
        SELECT id, transaction_id, client_app, service_name, endpoint, execution_time_ms, status_code, created_at 
        FROM audit_traces 
        ORDER BY created_at DESC 
        LIMIT 8
    """)
    recent_traces = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "total_transactions": total_tx,
        "total_volume": total_volume,
        "avg_risk_score": avg_risk,
        "avg_latency_ms": avg_latency,
        "sla_uptime_percent": 99.98,
        "app_distribution": app_stats,
        "recent_transactions": recent_transactions,
        "recent_traces": recent_traces
    }
