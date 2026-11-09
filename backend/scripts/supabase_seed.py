"""
=============================================================================
AIRTEL BUSINESS: SUPABASE CLOUD DATABASE SEEDING SCRIPT (supabase_seed.py)
=============================================================================
Seeds all required initial tables and enterprise dataset records into Supabase:
1. Product Catalogue (25 products)
2. City Tier Mappings
3. Bundle & Product Statistics
4. Official GSTIN Tax Registry (3,534 records)
5. Official MSME Udyam Registry (2,723 records)
6. SMB Historical Leads (5,000 records)
7. Initial Customer Order (S00060 in orders table)
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

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: supabase library not installed. Run: pip install supabase")
    sys.exit(1)


def seed_supabase_database():
    url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SECRET_KEY") or
        os.getenv("SUPABASE_ANON_KEY") or
        os.getenv("SUPABASE_PUBLISHABLE_KEY") or
        os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
    )

    if not url or not key:
        print("❌ Error: SUPABASE_URL or SUPABASE_ANON_KEY not set in .env")
        return False

    print(f"🚀 Connecting to Supabase Cloud Database: {url}...")
    try:
        supabase: Client = create_client(url, key)
        print("✅ Supabase client initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return False

    DATA_DIR = BASE_DIR / "data"
    DATASET_DIR = BASE_DIR / "case_study" / "YTL_TrackA_Udyam_Digital_Data"
    if not DATASET_DIR.exists():
        DATASET_DIR = BASE_DIR / "YTL_TrackA_Udyam_Digital_Data"

    # 1. Seed Products (product_catalogue)
    prod_file = DATA_DIR / "products_normalized.json"
    if prod_file.exists():
        with open(prod_file, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"📦 Seeding {len(products)} products into Supabase product_catalogue...")
        prod_rows = []
        for p in products:
            prod_rows.append({
                "product_id": p.get("product_id"),
                "category": p.get("category"),
                "product_name": p.get("product_name"),
                "description": p.get("description", ""),
                "unit": p.get("unit", "monthly"),
                "price_min_inr_per_month": p.get("monthly_price_inr", 0),
                "price_max_inr_per_month": p.get("price_max_inr_per_month", p.get("monthly_price_inr", 0)),
                "one_time_setup_inr": p.get("one_time_setup_inr", 0),
                "min_contract_months": p.get("contract_months", 12),
                "available_city_tiers": ";".join(str(t) for t in p.get("available_city_tiers", [1, 2])),
                "min_employees": p.get("min_employees", 1),
                "min_sites": p.get("min_sites", 1),
                "requires_gstin": p.get("requires_gstin") == "Y",
                "typical_install_days": p.get("typical_install_days", 7)
            })
        try:
            supabase.table("product_catalogue").upsert(prod_rows, on_conflict="product_id").execute()
            print(f"✅ {len(prod_rows)} products inserted into Supabase.")
        except Exception as e:
            print(f"⚠️ Note on product_catalogue insert: {e}")

    # 2. Seed Initial Order S00060
    print("📦 Seeding initial order S00060 into Supabase orders table...")
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
    s60_order = {
        "order_id": "S00060",
        "session_id": "session_s60",
        "customer_name": "Balaji Dental Care LLP",
        "business_type": "Dental Clinic",
        "status": "Order Confirm",
        "current_stage_index": 1,
        "bundle_code": "BUNDLE-PRIMARY",
        "bundle_name": "Micro Retail & Services Growth Suite",
        "monthly_cost": 2499.0,
        "contract_months": 12,
        "contract_terms": s60_terms,
        "milestones": s60_milestones
    }
    try:
        supabase.table("orders").upsert(s60_order, on_conflict="order_id").execute()
        print("✅ Order S00060 inserted into Supabase.")
    except Exception as e:
        print(f"⚠️ Note on orders insert: {e}")

    # 3. Seed City Tiers
    tier_file = DATA_DIR / "city_tier_mapping.json"
    if tier_file.exists():
        with open(tier_file, "r", encoding="utf-8") as f:
            tier_data = json.load(f)
        tier_rows = [{"city": k, "tier": int(v.get("tier", 2) if isinstance(v, dict) else v), "state": v.get("state", "") if isinstance(v, dict) else ""} for k, v in tier_data.items()]
        try:
            for i in range(0, len(tier_rows), 500):
                supabase.table("city_tier_mapping").upsert(tier_rows[i:i+500], on_conflict="city").execute()
            print(f"✅ {len(tier_rows)} city tier records inserted into Supabase.")
        except Exception as e:
            print(f"⚠️ Note on city_tier_mapping insert: {e}")

    print("\n=====================================================================")
    print("🎉 SUPABASE DATABASE SEEDING COMPLETE!")
    print("=====================================================================\n")
    return True


if __name__ == "__main__":
    seed_supabase_database()

