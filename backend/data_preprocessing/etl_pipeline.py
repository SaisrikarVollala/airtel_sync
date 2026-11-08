"""
=============================================================================
DATA PREPROCESSING: Automated ETL Pipeline (etl_pipeline.py)
=============================================================================
Ingests, normalizes, and precomputes statistics for all 11,282 synthetic records
across the Accel YTL Hackathon dataset:
- product_catalogue.csv (25 products)
- mock_gstin_registry.csv (3,534 GST records)
- mock_udyam_registry.csv (2,723 MSME records)
- smb_leads.csv (5,000 leads)
=============================================================================
"""

import csv
import json
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "YTL_TrackA_Udyam_Digital_Data"
DATA_DIR = BASE_DIR / "data"


def run_etl() -> Dict[str, Any]:
    """
    Executes ETL parsing and returns summary counts.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    products = []
    gstin_count = 0
    udyam_count = 0
    leads_count = 0

    # 1. Product Catalogue
    prod_csv = DATASET_DIR / "product_catalogue.csv"
    if prod_csv.exists():
        with open(prod_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append({
                    "product_id": row.get("product_id"),
                    "product_name": row.get("product_name"),
                    "category": row.get("category"),
                    "description": row.get("description", ""),
                    "unit": row.get("unit", ""),
                    "monthly_price_inr": float(row.get("price_min_inr_per_month") or row.get("monthly_price_inr") or 0),
                    "price_min_inr_per_month": float(row.get("price_min_inr_per_month") or row.get("monthly_price_inr") or 0),
                    "price_max_inr_per_month": float(row.get("price_max_inr_per_month") or row.get("price_min_inr_per_month") or 0),
                    "one_time_setup_inr": float(row.get("one_time_setup_inr") or 0),
                    "contract_months": int(row.get("min_contract_months") or row.get("contract_months") or 12),
                    "min_contract_months": int(row.get("min_contract_months") or row.get("contract_months") or 12),
                    "min_employees": int(row.get("min_employees") or 1),
                    "min_sites": int(row.get("min_sites") or 1),
                    "requires_gstin": row.get("requires_gstin", "N"),
                    "requires_one_of": row.get("requires_one_of", "").strip(),
                    "available_city_tiers": [int(t) for t in (row.get("available_city_tiers") or "1;2").split(";") if t.isdigit()],
                    "typical_install_days": int(row.get("typical_install_days") or 7),
                    "target_segments": [s.strip() for s in (row.get("target_segments") or "").split(";") if s.strip()]
                })

    # Save normalized products
    with open(DATA_DIR / "products_normalized.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)

    # 2. Count registries
    gst_csv = DATASET_DIR / "mock_gstin_registry.csv"
    if gst_csv.exists():
        with open(gst_csv, "r", encoding="utf-8") as f:
            gstin_count = sum(1 for _ in f) - 1

    udyam_csv = DATASET_DIR / "mock_udyam_registry.csv"
    if udyam_csv.exists():
        with open(udyam_csv, "r", encoding="utf-8") as f:
            udyam_count = sum(1 for _ in f) - 1

    # 3. Process 5,000 SMB Leads to Generate Bundle & Product Statistics
    leads_csv = DATASET_DIR / "smb_leads.csv"
    bundle_aggregates: Dict[str, Any] = {}
    product_aggregates: Dict[str, Any] = {}
    lead_bundle_items: List[Dict[str, Any]] = []
    lead_interest_items: List[Dict[str, Any]] = []

    if leads_csv.exists():
        with open(leads_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads_count += 1
                lid = row.get("lead_id", "").strip()
                b_code = row.get("bundle_products", "").strip()
                outcome = row.get("outcome", "").strip()
                nps = float(row.get("nps_score")) if row.get("nps_score") else None
                churn = row.get("churned_within_6_months", "").strip().upper() == "Y"
                m_val = float(row.get("monthly_bundle_value_inr") or 0)
                s_val = float(row.get("one_time_setup_inr") or 0)
                segment = row.get("segment", "").strip()

                # Explode bundle products: P01x2;P07x1 -> lead_bundle_items
                if b_code:
                    for part in b_code.split(";"):
                        part = part.strip()
                        if not part:
                            continue
                        if "x" in part:
                            p_id, qty_s = part.split("x", 1)
                            qty = int(qty_s) if qty_s.isdigit() else 1
                        else:
                            p_id = part
                            qty = 1
                        lead_bundle_items.append({
                            "lead_id": lid,
                            "product_id": p_id,
                            "qty": qty,
                            "outcome": outcome,
                            "segment": segment,
                            "churn": churn
                        })

                # Explode products of interest -> lead_interest_items
                poi = [p.strip() for p in (row.get("products_of_interest") or "").split(";") if p.strip()]
                for p_id in poi:
                    lead_interest_items.append({
                        "lead_id": lid,
                        "product_id": p_id,
                        "outcome": outcome,
                        "segment": segment
                    })

                # Bundle statistics aggregation (Activated customers)
                if b_code and outcome == "Activated":
                    if b_code not in bundle_aggregates:
                        bundle_aggregates[b_code] = {
                            "bundle_code": b_code,
                            "total_sold": 0,
                            "monthly_vals": [],
                            "setup_fees": [],
                            "nps_scores": [],
                            "churn_count": 0,
                            "segments": {}
                        }
                    b_agg = bundle_aggregates[b_code]
                    b_agg["total_sold"] += 1
                    b_agg["monthly_vals"].append(m_val)
                    b_agg["setup_fees"].append(s_val)
                    if nps is not None:
                        b_agg["nps_scores"].append(nps)
                    if churn:
                        b_agg["churn_count"] += 1
                    b_agg["segments"][segment] = b_agg["segments"].get(segment, 0) + 1

                # Product conversion & NPS aggregation
                for p_id in poi:
                    if p_id not in product_aggregates:
                        product_aggregates[p_id] = {
                            "product_id": p_id,
                            "times_recommended": 0,
                            "times_activated": 0,
                            "nps_scores": [],
                            "churn_count": 0
                        }
                    product_aggregates[p_id]["times_recommended"] += 1
                    if outcome == "Activated":
                        product_aggregates[p_id]["times_activated"] += 1
                        if nps is not None:
                            product_aggregates[p_id]["nps_scores"].append(nps)
                        if churn:
                            product_aggregates[p_id]["churn_count"] += 1

    # Format Bundle Statistics
    bundle_stats = []
    for code, b_data in sorted(bundle_aggregates.items(), key=lambda x: x[1]["total_sold"], reverse=True):
        m_list = b_data["monthly_vals"]
        s_list = b_data["setup_fees"]
        n_list = b_data["nps_scores"]
        total = b_data["total_sold"]
        top_seg = max(b_data["segments"].items(), key=lambda x: x[1])[0] if b_data["segments"] else "General"

        bundle_stats.append({
            "bundle_code": code,
            "total_sold": total,
            "avg_monthly_value": round(sum(m_list) / len(m_list), 2) if m_list else 0,
            "avg_setup_fee": round(sum(s_list) / len(s_list), 2) if s_list else 0,
            "avg_nps": round(sum(n_list) / len(n_list), 2) if n_list else 7.0,
            "churn_rate": round(b_data["churn_count"] / total, 3) if total else 0.0,
            "top_segment": top_seg
        })

    with open(DATA_DIR / "bundle_statistics.json", "w", encoding="utf-8") as f:
        json.dump(bundle_stats, f, indent=2)

    # Format Product Statistics
    product_stats = []
    for pid, p_data in sorted(product_aggregates.items(), key=lambda x: x[1]["times_activated"], reverse=True):
        recs = p_data["times_recommended"]
        acts = p_data["times_activated"]
        n_list = p_data["nps_scores"]

        product_stats.append({
            "product_id": pid,
            "times_recommended": recs,
            "times_activated": acts,
            "conversion_rate": round(acts / recs, 3) if recs else 0.0,
            "avg_nps": round(sum(n_list) / len(n_list), 2) if n_list else 7.0,
            "churn_rate": round(p_data["churn_count"] / acts, 3) if acts else 0.0
        })

    with open(DATA_DIR / "product_statistics.json", "w", encoding="utf-8") as f:
        json.dump(product_stats, f, indent=2)

    with open(DATA_DIR / "lead_bundle_items.json", "w", encoding="utf-8") as f:
        json.dump(lead_bundle_items, f, indent=2)

    with open(DATA_DIR / "lead_interest_items.json", "w", encoding="utf-8") as f:
        json.dump(lead_interest_items, f, indent=2)

    # 4. Generate Overall Dataset Summary
    summary = {
        "products": len(products),
        "gstin_registry": max(0, gstin_count),
        "udyam_registry": max(0, udyam_count),
        "leads": max(0, leads_count),
        "bundles_computed": len(bundle_stats),
        "product_stats_computed": len(product_stats),
        "total_records": len(products) + max(0, gstin_count) + max(0, udyam_count) + max(0, leads_count)
    }

    with open(DATA_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    res = run_etl()
    print("ETL Completed Successfully:", res)
