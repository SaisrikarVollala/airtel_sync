"""
=============================================================================
AIRTEL BUSINESS: CLOUD DATABASE MIGRATION & SEEDING PIPELINE
=============================================================================
Migrates local dataset into a Cloud PostgreSQL Database (e.g. Neon, Supabase,
AWS RDS, or local PostgreSQL).

1. Reads DATABASE_URL from .env or environment variable.
2. Applies DDL schema from database/migrations/0001_cloud_init.sql.
3. Bulk inserts:
   - 25 Products (product_catalogue)
   - 3,534 GSTIN Registry records (gstin_registry)
   - 2,723 MSME Udyam records (udyam_registry)
   - 5,000 SMB Leads (smb_leads)
   - Initial Customer Order (S00060 in orders table)
4. Displays cloud verification summary.
=============================================================================
"""

import os
import sys
import csv
import json
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables from .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

try:
    import psycopg2
    from psycopg2.extras import execute_batch, Json
except ImportError:
    print("❌ Error: psycopg2-binary is not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def seed_cloud_database():
    database_url = os.getenv("DATABASE_URL")
    if not database_url or "localhost" in database_url and len(sys.argv) < 2:
        if len(sys.argv) > 1:
            database_url = sys.argv[1]
        else:
            print("=====================================================================")
            print("⚠️  NO CLOUD DATABASE_URL DETECTED IN .env!")
            print("=====================================================================")
            print("To seed a cloud database (e.g. Neon, Supabase, or AWS RDS):")
            print("1. Get your free connection string, e.g.:")
            print("   postgresql://user:password@ep-cool-xyz.aws.neon.tech/neondb?sslmode=require")
            print("2. Add it to .env: DATABASE_URL=postgresql://...")
            print("   OR run: python scripts/cloud_db_seed.py '<your_cloud_database_url>'")
            print("=====================================================================")
            return False

    print(f"🚀 Connecting to Cloud PostgreSQL Database...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cur = conn.cursor()
        print("✅ Connection established successfully!")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False

    # 1. Apply Schema DDL
    schema_file = BASE_DIR / "database" / "migrations" / "0001_cloud_init.sql"
    if schema_file.exists():
        print(f"📄 Applying schema from {schema_file.name}...")
        with open(schema_file, "r", encoding="utf-8") as f:
            ddl_sql = f.read()
            cur.execute(ddl_sql)
        print("✅ Tables and indexes created successfully.")
    else:
        print("⚠️ Schema file not found!")

    DATA_DIR = BASE_DIR / "data"
    DATASET_DIR = BASE_DIR / "YTL_TrackA_Udyam_Digital_Data"

    # 2. Seed Products
    prod_json = DATA_DIR / "products_normalized.json"
    if prod_json.exists():
        with open(prod_json, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"📦 Seeding {len(products)} products into product_catalogue...")
        prod_query = """
            INSERT INTO product_catalogue (
                product_id, category, product_name, description, unit,
                price_min_inr_per_month, price_max_inr_per_month, one_time_setup_inr,
                min_contract_months, available_city_tiers, min_employees, min_sites,
                requires_gstin, typical_install_days
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                price_min_inr_per_month = EXCLUDED.price_min_inr_per_month;
        """
        prod_data = []
        for p in products:
            prod_data.append((
                p.get("product_id"),
                p.get("category"),
                p.get("product_name"),
                p.get("description", ""),
                p.get("unit", "monthly"),
                p.get("monthly_price_inr", 0),
                p.get("price_max_inr_per_month", p.get("monthly_price_inr", 0)),
                p.get("one_time_setup_inr", 0),
                p.get("contract_months", 12),
                ";".join(str(t) for t in p.get("available_city_tiers", [1, 2])),
                p.get("min_employees", 1),
                p.get("min_sites", 1),
                p.get("requires_gstin") == "Y",
                p.get("typical_install_days", 7)
            ))
        execute_batch(cur, prod_query, prod_data)
        print(f"✅ {len(prod_data)} products inserted.")

    # 3. Seed GSTIN Registry
    gst_csv = DATASET_DIR / "mock_gstin_registry.csv"
    if gst_csv.exists():
        print("🏛️ Reading mock_gstin_registry.csv...")
        gst_data = []
        with open(gst_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                gid = row.get("gstin", "").strip().upper()
                if gid:
                    gst_data.append((
                        gid,
                        row.get("legal_name", ""),
                        row.get("trade_name", ""),
                        row.get("constitution", ""),
                        row.get("principal_place_of_business", ""),
                        row.get("state", ""),
                        row.get("registration_date") or None,
                        row.get("status", "Active")
                    ))
        print(f"🏛️ Seeding {len(gst_data)} GSTIN records into gstin_registry...")
        gst_query = """
            INSERT INTO gstin_registry (
                gstin, legal_name, trade_name, constitution,
                principal_place_of_business, state, registration_date, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (gstin) DO NOTHING;
        """
        execute_batch(cur, gst_query, gst_data, page_size=1000)
        print(f"✅ {len(gst_data)} GSTIN records inserted.")

    # 4. Seed Udyam Registry
    udyam_csv = DATASET_DIR / "mock_udyam_registry.csv"
    if udyam_csv.exists():
        print("🏭 Reading mock_udyam_registry.csv...")
        udyam_data = []
        with open(udyam_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                uid = row.get("udyam_number", "").strip().upper()
                if uid:
                    udyam_data.append((
                        uid,
                        row.get("enterprise_name", ""),
                        row.get("enterprise_type", ""),
                        row.get("major_activity", ""),
                        row.get("nic_description", ""),
                        row.get("state", ""),
                        row.get("city", ""),
                        row.get("date_of_registration") or None
                    ))
        print(f"🏭 Seeding {len(udyam_data)} Udyam records into udyam_registry...")
        udyam_query = """
            INSERT INTO udyam_registry (
                udyam_number, enterprise_name, enterprise_type, major_activity,
                nic_description, state, city, date_of_registration
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (udyam_number) DO NOTHING;
        """
        execute_batch(cur, udyam_query, udyam_data, page_size=1000)
        print(f"✅ {len(udyam_data)} Udyam records inserted.")

    # 5. Seed SMB Leads
    leads_csv = DATASET_DIR / "smb_leads.csv"
    if leads_csv.exists():
        print("📈 Reading smb_leads.csv...")
        leads_data = []
        with open(leads_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lid = row.get("lead_id", "").strip()
                if lid:
                    leads_data.append((
                        lid,
                        row.get("created_date") or None,
                        row.get("lead_source"),
                        row.get("business_name"),
                        row.get("business_type"),
                        row.get("segment"),
                        row.get("city"),
                        int(row.get("city_tier") or 2),
                        row.get("state"),
                        row.get("preferred_language"),
                        int(row.get("employee_count") or 1),
                        int(row.get("num_sites") or 1),
                        row.get("annual_turnover_band"),
                        row.get("has_gstin") == "True",
                        row.get("gstin"),
                        row.get("has_udyam") == "True",
                        row.get("udyam_number"),
                        row.get("current_internet"),
                        row.get("current_provider"),
                        float(row.get("monthly_telecom_spend_inr") or 0),
                        row.get("products_of_interest"),
                        row.get("contact_name"),
                        row.get("contact_role"),
                        row.get("stage_reached"),
                        row.get("outcome"),
                        row.get("drop_reason"),
                        row.get("contacted_date") or None,
                        row.get("needs_assessed_date") or None,
                        row.get("quote_accepted_date") or None,
                        row.get("kyc_complete_date") or None,
                        row.get("activated_date") or None,
                        int(row.get("days_lead_to_activation") or 0) if row.get("days_lead_to_activation") else None,
                        int(row.get("customer_follow_up_calls") or 0),
                        row.get("bundle_products"),
                        float(row.get("monthly_bundle_value_inr") or 0) if row.get("monthly_bundle_value_inr") else None,
                        float(row.get("one_time_setup_inr") or 0) if row.get("one_time_setup_inr") else None,
                        int(row.get("contract_months") or 12) if row.get("contract_months") else None,
                        row.get("churned_within_6_months") == "True",
                        int(row.get("nps_score") or 0) if row.get("nps_score") else None,
                        float(row.get("acquisition_cost_inr") or 0) if row.get("acquisition_cost_inr") else None
                    ))
        print(f"📈 Seeding {len(leads_data)} SMB leads into smb_leads...")
        leads_query = """
            INSERT INTO smb_leads (
                lead_id, created_date, lead_source, business_name, business_type,
                segment, city, city_tier, state, preferred_language, employee_count,
                num_sites, annual_turnover_band, has_gstin, gstin, has_udyam,
                udyam_number, current_internet, current_provider,
                monthly_telecom_spend_inr, products_of_interest, contact_name,
                contact_role, stage_reached, outcome, drop_reason, contacted_date,
                needs_assessed_date, quote_accepted_date, kyc_complete_date,
                activated_date, days_lead_to_activation, customer_follow_up_calls,
                bundle_products, monthly_bundle_value_inr, one_time_setup_inr,
                contract_months, churned_within_6_months, nps_score, acquisition_cost_inr
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (lead_id) DO NOTHING;
        """
        execute_batch(cur, leads_query, leads_data, page_size=1000)
        print(f"✅ {len(leads_data)} SMB leads inserted.")

    # 6. Seed Order S00060
    print("📦 Seeding initial order S00060 into orders table...")
    order_query = """
        INSERT INTO orders (
            order_id, session_id, customer_name, business_type, status,
            current_stage_index, bundle_code, bundle_name, monthly_cost,
            contract_months, contract_terms, milestones
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (order_id) DO UPDATE SET
            status = EXCLUDED.status,
            current_stage_index = EXCLUDED.current_stage_index,
            updated_at = CURRENT_TIMESTAMP;
    """
    s60_terms = {
        "sla_uptime": "99.5% Standard Commercial Uptime SLA",
        "mttr_hours": 8,
        "billing_cycle": "Monthly Advance",
        "notice_period_days": 30
    }
    s60_milestones = [
        {"stage": "PENDING", "title": "Pending", "description": "Your order is in review & verification", "date_str": "Tue, May 21, 2024, 6:44:14 PM", "completed": True, "icon": "pending"},
        {"stage": "CONFIRMED", "title": "Order Confirm", "description": "Your order has been verified & confirmed", "date_str": "Thu, May 30, 2024, 9:42:58 AM", "completed": True, "icon": "confirm"},
        {"stage": "PACKED", "title": "Packed and Processed", "description": "Hardware router & SIM kit dispatched", "date_str": "Fri, May 31, 2024, 9:43:00 AM", "completed": False, "icon": "packed"},
        {"stage": "DELIVERED", "title": "Delivered", "description": "Expected Delivery Date: Tue, Jun 04, 2024", "date_str": "Expected: Jun 04, 2024", "completed": False, "icon": "delivered"}
    ]
    cur.execute(order_query, (
        "S00060",
        "session_s60",
        "Balaji Dental Care LLP",
        "Dental Clinic",
        "Order Confirm",
        1,
        "BUNDLE-PRIMARY",
        "Micro Retail & Services Growth Suite",
        2499.0,
        12,
        Json(s60_terms),
        Json(s60_milestones)
    ))
    print("✅ Order S00060 inserted.")

    # 7. Verification Counts
    print("\n=====================================================================")
    print("📊 CLOUD DATABASE VERIFICATION & STORED RECORD COUNTS:")
    print("=====================================================================")
    for table in ["product_catalogue", "gstin_registry", "udyam_registry", "smb_leads", "orders"]:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        print(f"  • {table.ljust(20)}: {count:,} records stored")
    print("=====================================================================")
    print("🎉 ALL DATA HAS BEEN SUCCESSFULLY STORED IN CLOUD POSTGRESQL!")
    print("=====================================================================\n")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    seed_cloud_database()
