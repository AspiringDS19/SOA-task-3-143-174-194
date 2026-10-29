import sqlite3
import os
import json
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "soa_platform.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Accounts Table (for Banking Application)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT UNIQUE NOT NULL,
            holder_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            currency TEXT NOT NULL DEFAULT 'USD',
            daily_limit REAL NOT NULL DEFAULT 5000.0,
            spent_today REAL NOT NULL DEFAULT 0.0,
            avatar TEXT
        )
    ''')

    # 2. Beneficiaries Table (Banking Contacts)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS beneficiaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_account_number TEXT NOT NULL,
            beneficiary_name TEXT NOT NULL,
            beneficiary_account TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            routing_code TEXT NOT NULL,
            category TEXT DEFAULT 'Personal'
        )
    ''')

    # 3. Products Table (for E-Commerce Application)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            rating REAL NOT NULL DEFAULT 4.5,
            reviews_count INTEGER DEFAULT 120,
            image TEXT,
            stock INTEGER NOT NULL DEFAULT 50,
            description TEXT
        )
    ''')

    # 4. Coupons Table (E-Commerce Promos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            discount_percent REAL NOT NULL,
            max_discount REAL NOT NULL,
            min_spend REAL NOT NULL DEFAULT 0.0,
            active INTEGER DEFAULT 1
        )
    ''')

    # 5. E-Commerce Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            total_amount REAL NOT NULL,
            discount_amount REAL DEFAULT 0.0,
            shipping_fee REAL DEFAULT 0.0,
            final_amount REAL NOT NULL,
            status TEXT NOT NULL,
            payment_transaction_id TEXT,
            items_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Central SOA Unified Payment Ledger (The Reusable Service Core Table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            client_app TEXT NOT NULL, -- 'ecommerce' or 'banking'
            transaction_type TEXT NOT NULL, -- 'ORDER_PURCHASE', 'FUNDS_TRANSFER', 'ESCROW_HOLD'
            source_account TEXT,
            target_account TEXT,
            amount REAL NOT NULL,
            fee REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'USD',
            status TEXT NOT NULL, -- 'PENDING', 'CHALLENGE_REQUIRED', 'AUTHORIZED', 'SETTLED', 'FAILED'
            idempotency_key TEXT UNIQUE,
            risk_score REAL DEFAULT 0.0,
            risk_decision TEXT DEFAULT 'APPROVE',
            client_metadata TEXT, -- JSON blob of custom context
            otp_code TEXT, -- 2FA code for banking high-value transfers
            otp_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Audit & Service Tracing (SOA Observability)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            client_app TEXT NOT NULL,
            service_name TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            execution_time_ms REAL NOT NULL,
            status_code INTEGER NOT NULL,
            request_payload TEXT,
            response_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # Seed initial data if tables are empty
    seed_data(cursor, conn)

    conn.close()

def seed_data(cursor, conn):
    # Check if accounts seeded
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        accounts = [
            ('ACC-10098421', 'Alex Morgan', 'Premier Checking', 12450.00, 'USD', 10000.0, 320.0, 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80'),
            ('ACC-20048190', 'Alex Morgan', 'High-Yield Savings', 48750.00, 'USD', 25000.0, 0.0, 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80'),
            ('ACC-88301124', 'Nexus Global Merchant', 'Business Merchant Account', 94320.00, 'USD', 500000.0, 0.0, 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150&auto=format&fit=crop&q=80'),
            ('ACC-99412033', 'Global Clearing Vault', 'Settlement Escrow Reserve', 1500000.00, 'USD', 10000000.0, 0.0, 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=150&auto=format&fit=crop&q=80')
        ]
        cursor.executemany('''
            INSERT INTO accounts (account_number, holder_name, account_type, balance, currency, daily_limit, spent_today, avatar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', accounts)

    # Beneficiaries
    cursor.execute("SELECT COUNT(*) FROM beneficiaries")
    if cursor.fetchone()[0] == 0:
        beneficiaries = [
            ('ACC-10098421', 'Sarah Jenkins', 'ACC-55219084', 'J.P. Morgan Chase', 'CHASUS33', 'Family'),
            ('ACC-10098421', 'TechFlow Innovations LLC', 'ACC-88301124', 'Apex Bank Corp', 'APEXUS44', 'Vendor'),
            ('ACC-10098421', 'Liam Henderson (Landlord)', 'ACC-33190241', 'Bank of America', 'BOFAUS3N', 'Utilities'),
            ('ACC-10098421', 'Elena Rostova', 'ACC-77401928', 'Citibank NA', 'CITIUS33', 'Personal')
        ]
        cursor.executemany('''
            INSERT INTO beneficiaries (user_account_number, beneficiary_name, beneficiary_account, bank_name, routing_code, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', beneficiaries)

    # Products for E-Commerce
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ('Sony WH-1000XM5 Wireless Headphones', 'Electronics', 349.99, 4.8, 482, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=80', 25, 'Industry-leading noise cancellation with two processors and 8 microphones for unparalleled quiet.'),
            ('Apple MacBook Air M3 15-inch', 'Computers', 1299.00, 4.9, 810, 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&auto=format&fit=crop&q=80', 14, 'Impossibly thin and fast with the latest M3 Apple silicon chip and liquid retina display.'),
            ('Omega Speedmaster Moonwatch', 'Luxury & Watches', 850.00, 4.7, 95, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&auto=format&fit=crop&q=80', 8, 'Legendary chronograph timepiece crafted with precision mechanical movement and sapphire crystal.'),
            ('Ergonomic Mesh Executive Chair', 'Office & Home', 289.50, 4.6, 230, 'https://images.unsplash.com/photo-1580481077195-c3f99dd92083?w=500&auto=format&fit=crop&q=80', 30, 'Full lumbar support with 4D adjustable armrests and high-breathability matrix mesh.'),
            ('Fujifilm X-T5 Mirrorless Camera', 'Photography', 1699.00, 4.9, 142, 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&auto=format&fit=crop&q=80', 10, '40.2 megapixel APS-C sensor with 5-axis in-body image stabilization and 4K/60p video capture.'),
            ('Bose SoundLink Flex Portable Speaker', 'Audio', 149.00, 4.5, 319, 'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=500&auto=format&fit=crop&q=80', 40, 'Rugged outdoor waterproof Bluetooth speaker with PositionIQ technology for deep rich audio.')
        ]
        cursor.executemany('''
            INSERT INTO products (name, category, price, rating, reviews_count, image, stock, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', products)

    # Coupons
    cursor.execute("SELECT COUNT(*) FROM coupons")
    if cursor.fetchone()[0] == 0:
        coupons = [
            ('WELCOME20', 20.0, 100.0, 50.0, 1),
            ('CYBERDEAL', 15.0, 150.0, 100.0, 1),
            ('VIP50', 50.0, 300.0, 500.0, 1)
        ]
        cursor.executemany('''
            INSERT INTO coupons (code, discount_percent, max_discount, min_spend, active)
            VALUES (?, ?, ?, ?, ?)
        ''', coupons)

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
