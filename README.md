# OmniPay | Payment as a Service (PaaS) Platform
## Reusable Multi-Tenant Enterprise Payment Engine

An enterprise demonstration of **Payment as a Service (PaaS)** architecture, featuring a central **Reusable Payment & Ledger Enterprise Service** that dynamically caters to two distinct consumer applications:
1. **NovaShop Digital Storefront** (E-Commerce / Amazon-style Retail B2C)
2. **Apex Online Banking Portal** (FinTech Interbank Wire & Account Clearing)

---

## 🏛️ 1. SOA Service Identification & Modeling Principles

In traditional siloed systems, both E-Commerce and Banking build redundant, bespoke payment and accounting mechanisms. Under **SOA design principles**, common business capabilities are extracted into an autonomous, reusable enterprise service, while client-specific nuances are managed through specialized adapter policies.

```
                      ┌──────────────────────────────────────┐
                      │        CONSUMER APPLICATIONS         │
                      └──────────────────┬───────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
      ┌──────────▼──────────┐                         ┌──────────▼──────────┐
      │   🛍️ NovaShop Store │                         │  🏦 Apex Online     │
      │   (E-Commerce App)  │                         │     Banking Portal  │
      └──────────┬──────────┘                         └──────────┬──────────┘
                 │                                               │
                 │ REST / JSON (Client Payload)                  │ REST / JSON (Client Payload)
                 ▼                                               ▼
      ┌─────────────────────┐                         ┌─────────────────────┐
      │  E-Commerce Adapter │                         │   Banking Adapter   │
      │ ─────────────────── │                         │ ─────────────────── │
      │ • Inventory & Stock │                         │ • Balance Checking  │
      │ • Coupon Discounts  │                         │ • Daily Limits      │
      │ • Shipping Invoices │                         │ • 2FA OTP Challenge │
      └──────────┬──────────┘                         └──────────┬──────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │ Normalized SOA Contract
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │   ⚡ ENTERPRISE REUSABLE PAYMENT SERVICE      │
                 │   ──────────────────────────────────────────  │
                 │   • Unified Double-Entry Ledger Orchestration │
                 │   • Idempotency Guarantee & Deduplication     │
                 │   • Real-Time Risk & Fraud Screening          │
                 │   • State Lifecycle (PENDING -> SETTLED)      │
                 │   • SLA Latency & Audit Trail Telemetry       │
                 └───────────────────────┬───────────────────────┘
                                         │ ACID Storage
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │          SQLITE ENTERPRISE DATABASE           │
                 │   (transactions, audit_traces, accounts)      │
                 └───────────────────────────────────────────────┘
```

---

## ⚖️ 2. Comparative Policy Specialization Matrix

How the single reusable service caters separately to both applications:

| SOA Architectural Dimension | NovaShop (E-Commerce App) | Apex Banking (FinTech Portal) | Core Shared Reusable Engine |
| :--- | :--- | :--- | :--- |
| **Transaction Type** | `ORDER_PURCHASE` | `FUNDS_TRANSFER` | Unified State Machine |
| **Validation Criteria** | Cart inventory, min order spend, delivery address | Source account balance, routing code, daily limit | Schema validation & idempotency |
| **Specialized Adjustments** | Coupon codes (`WELCOME20`, `CYBERDEAL`), shipping fees | Wire clearing fees ($0.50 IMPS to $15 Wire) | Merchant transaction fee ledger |
| **Security Challenge Policy** | Frictionless 1-Click checkout | Mandatory 2FA OTP challenge for amounts $\ge$ $500 | Challenge token state & verification |
| **Post-Settlement Action** | Deducts physical inventory, creates order receipt | Debits sender account, credits beneficiary | Double-entry ledger audit record |

---

## 🚀 3. Technology Stack

- **Backend**: Python 3.12, Flask, Flask-CORS
- **Database**: SQLite3 (ACID-compliant relational database with foreign keys)
- **Frontend**: Vue.js 3 (reactive state management), HTML5 Semantic markup, Custom Glassmorphic Dark-Mode CSS Design System
- **Typography**: Google Fonts (*Plus Jakarta Sans*, *JetBrains Mono*)

---

## 💻 4. Running the Application

### 1. Prerequisites
Ensure Python 3.x is installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize the Database
```bash
python database.py
```

### 4. Start the Application Server
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔍 5. Interactive Demo Walkthrough

### 🛍️ Scenario A: NovaShop Checkout Flow
1. Open the **NovaShop Store** tab.
2. Products with live stock counts and images are rendered.
3. In the right-hand cart panel, enter promo code `WELCOME20` and click **Apply** to see discount computation.
4. Click **Complete Checkout**.
5. The `EcommercePaymentAdapter` validates stock, applies the discount, charges the merchant account, and generates a confirmed order receipt.

### 🏦 Scenario B: Apex Banking Interbank Transfer Flow
1. Switch to the **Apex Online Banking** tab.
2. View real-time checking & savings balance cards.
3. Select a beneficiary (e.g. *Sarah Jenkins*) and choose transfer speed (*Instant IMPS*, *FedNow Express*, or *Swift Wire*).
4. Set the transfer amount to **$650.00** (triggers the security policy rule for $\ge \$500$).
5. Click **Confirm Transfer**.
6. The **2FA Security Challenge Modal** will appear displaying the system-generated Demo OTP.
7. Enter the OTP and click **Verify & Authorize Funds Transfer**.
8. The funds are transferred, balances are updated, and the transaction is committed to the statement ledger.

### 🌐 Scenario C: PaaS Architecture & Service Registry
1. Switch to the **PaaS Architecture & Registry** tab.
2. View the visual **PaaS Topology Flow** diagram and the **Comparative Specialization Matrix**.
3. Inspect live metrics: Total Volume, Average Latency (ms), and Risk Scores.
4. Click on any row in the **Live Service Execution Traces** list to open the **Contract Inspector** and examine the normalized JSON request and response payloads.
5. Click **🔄 Reset Demo** anytime in the top bar to restore balances and stock for a fresh presentation.
