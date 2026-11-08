"""
Stage 6 and Stage 10: Pricing, Contract Co-Terming, and Installation ETA (pricing.py)
Computes:
- Line item pricing with cohort position t: unit_price = price_min + t * (price_max - price_min)
- Contract co-terming: contract_months = max(min_contract_months)
- Dependency-aware critical path installation ETA
- Tax calculation (18% GST) and first-year total
"""

import math
from typing import Dict, Any, List, Optional
from database.db_client import db_client


class PricingEngine:
    # 18% statutory Goods and Services Tax (GST) mandatory on telecommunications and IT services in India
    DEFAULT_TAX_RATE = 0.18

    @classmethod
    def price_bundle(
        cls,
        product_items: List[Dict[str, Any]],
        price_position_t: float = 0.5,
        eta_buffer_days: int = 2
    ) -> Dict[str, Any]:
        """
        Computes line items, totals, contract duration, tax, and ETA critical path.
        """
        catalogue_map = {p["product_id"]: p for p in db_client.get_products()}

        priced_products = []
        monthly_total = 0.0
        setup_total = 0.0
        min_contracts = []
        install_days_map = {}

        for item in product_items:
            pid = item["product_id"]
            qty = max(1, int(item.get("qty", 1)))
            cat_prod = catalogue_map.get(pid, {})

            p_min = float(cat_prod.get("price_min_inr_per_month") or cat_prod.get("monthly_price_inr") or 0)
            p_max = float(cat_prod.get("price_max_inr_per_month") or cat_prod.get("monthly_price_inr") or p_min)

            # Price position formula
            t = max(0.0, min(1.0, float(price_position_t)))
            unit_price = round(p_min + t * (p_max - p_min))
            line_monthly = round(unit_price * qty, 2)
            unit_setup = float(cat_prod.get("one_time_setup_inr", 0))
            line_setup = round(unit_setup * qty, 2)

            contract_m = int(cat_prod.get("min_contract_months") or cat_prod.get("contract_months") or 12)
            min_contracts.append(contract_m)

            install_days = int(cat_prod.get("typical_install_days", 5))
            install_days_map[pid] = install_days

            monthly_total += line_monthly
            setup_total += line_setup

            priced_products.append({
                "product_id": pid,
                "product_name": cat_prod.get("product_name", pid),
                "category": cat_prod.get("category", "General"),
                "qty": qty,
                "unit": cat_prod.get("unit", "per site"),
                "unit_price": unit_price,
                "monthly": line_monthly,
                "setup": line_setup,
                "auto_added_for": item.get("auto_added_for")
            })

        # Co-termed contract
        contract_months = max(min_contracts) if min_contracts else 12

        # Effective monthly for scoring
        effective_monthly = round(monthly_total + (setup_total / max(1, contract_months)), 2)

        # Tax calculation
        tax_amount = round(monthly_total * cls.DEFAULT_TAX_RATE, 2)
        setup_tax = round(setup_total * cls.DEFAULT_TAX_RATE, 2)
        total_monthly_with_tax = round(monthly_total + tax_amount, 2)
        first_year_total = round((setup_total + setup_tax) + 12 * total_monthly_with_tax, 2)

        # Installation ETA calculation along dependency chains
        # finish(p) = install_days(p) + max(finish(prereq in bundle))
        bundle_pids = set(p["product_id"] for p in priced_products)
        finish_times: Dict[str, int] = {}

        # Topological pass
        for p in priced_products:
            pid = p["product_id"]
            cat_prod = catalogue_map.get(pid, {})
            req_str = str(cat_prod.get("requires_one_of") or "").strip()
            prereqs_in_bundle = [
                opt.strip() for opt in req_str.split("|")
                if opt.strip() in bundle_pids
            ] if req_str else []

            prereq_max_finish = max((finish_times.get(pr, 0) for pr in prereqs_in_bundle), default=0)
            finish_times[pid] = install_days_map.get(pid, 5) + prereq_max_finish

        if finish_times:
            critical_product = max(finish_times.items(), key=lambda x: x[1])
            eta_days = critical_product[1] + eta_buffer_days
            eta_critical_path = critical_product[0]
        else:
            eta_days = 7
            eta_critical_path = None

        return {
            "products": priced_products,
            "monthly_total": round(monthly_total, 2),
            "setup_total": round(setup_total, 2),
            "contract_months": contract_months,
            "effective_monthly": effective_monthly,
            "tax": {
                "rate": cls.DEFAULT_TAX_RATE,
                "monthly_amount": tax_amount,
                "setup_amount": setup_tax,
                "inclusive": False
            },
            "total_monthly_with_tax": total_monthly_with_tax,
            "first_year_total": first_year_total,
            "eta_days": eta_days,
            "eta_critical_path": eta_critical_path
        }


pricing_engine = PricingEngine()

