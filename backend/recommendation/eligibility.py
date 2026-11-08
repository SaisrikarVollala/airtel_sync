"""
Stage 1: Hard-rule Eligibility Engine (eligibility.py)
Evaluates catalogue eligibility rules deterministically.
No ineligible product is ever recommended. Keeps reasons and unlock hints for all products.
"""

from typing import Dict, Any, List, Tuple
from database.db_client import db_client


class EligibilityEngine:
    REASON_TIER_NOT_AVAILABLE = "TIER_NOT_AVAILABLE"
    REASON_MIN_EMPLOYEES = "MIN_EMPLOYEES"
    REASON_MIN_SITES = "MIN_SITES"
    REASON_NEEDS_GSTIN = "NEEDS_GSTIN"

    @classmethod
    def evaluate_product(
        cls,
        product: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> Tuple[bool, List[str], str]:
        """
        Evaluates eligibility for a single product against the normalized customer profile.
        Returns: (eligible: bool, reasons: list of violation codes, unlock_hint: str)
        """
        reasons = []
        unlock_hint = ""

        try:
            city_tier = int(float(profile.get("city_tier", 1) or 1))
        except (ValueError, TypeError):
            city_tier = 1

        try:
            employee_count = int(float(profile.get("employee_count", 5) or 5))
        except (ValueError, TypeError):
            employee_count = 5

        try:
            num_sites = int(float(profile.get("num_sites", 1) or 1))
        except (ValueError, TypeError):
            num_sites = 1
        gstin_valid_for_sale = profile.get("gstin_valid_for_sale")
        if gstin_valid_for_sale is None:
            has_flag = str(profile.get("has_gstin") or "").strip().upper() in ["Y", "TRUE", "1", "YES"]
            gstin_valid_for_sale = has_flag or bool(profile.get("gstin"))

        # 1. City Tier check
        tiers = product.get("available_city_tiers") or []
        tier_match = city_tier in tiers or str(city_tier) in [str(t) for t in tiers] or len(tiers) == 0
        if not tier_match:
            reasons.append(cls.REASON_TIER_NOT_AVAILABLE)

        # 2. Min Employees check
        min_emp = product.get("min_employees", 1)
        if employee_count < min_emp:
            reasons.append(cls.REASON_MIN_EMPLOYEES)

        # 3. Min Sites check
        min_sites = product.get("min_sites", 1)
        if num_sites < min_sites:
            reasons.append(cls.REASON_MIN_SITES)

        # 4. GSTIN check
        req_gstin = str(product.get("requires_gstin", "N")).strip().upper() == "Y"
        if req_gstin and not gstin_valid_for_sale:
            reasons.append(cls.REASON_NEEDS_GSTIN)

        # Generate unlock hint if only 1 failure
        if len(reasons) == 1:
            r = reasons[0]
            if r == cls.REASON_NEEDS_GSTIN:
                unlock_hint = "Unlocks with an active GSTIN"
            elif r == cls.REASON_MIN_SITES:
                unlock_hint = f"Requires {min_sites}+ business sites"
            elif r == cls.REASON_MIN_EMPLOYEES:
                unlock_hint = f"Requires {min_emp}+ staff members"
            elif r == cls.REASON_TIER_NOT_AVAILABLE:
                unlock_hint = f"Available in Tier {';'.join(str(t) for t in tiers)} cities"
        elif len(reasons) > 1:
            hints = []
            if cls.REASON_NEEDS_GSTIN in reasons:
                hints.append("active GSTIN")
            if cls.REASON_MIN_SITES in reasons:
                hints.append(f"{min_sites}+ sites")
            if cls.REASON_MIN_EMPLOYEES in reasons:
                hints.append(f"{min_emp}+ staff")
            unlock_hint = "Requires: " + ", ".join(hints)

        eligible = len(reasons) == 0
        return eligible, reasons, unlock_hint

    @classmethod
    def filter_catalogue(
        cls,
        profile: Dict[str, Any],
        catalogue: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs eligibility across the entire product catalogue.
        Returns:
            eligible_products: list of products that passed all checks
            ineligible_products: list of dicts with product, reasons, unlock_hint
            unlockable_with_gstin: product_ids that fail ONLY on NEEDS_GSTIN
            need_unmet: list of needs with no eligible products
        """
        if catalogue is None:
            catalogue = db_client.get_products()

        eligible = []
        ineligible = []
        unlockable_with_gstin = []

        for p in catalogue:
            is_elig, reasons, hint = cls.evaluate_product(p, profile)
            if is_elig:
                eligible.append(dict(p))
            else:
                ineligible.append({
                    "product_id": p.get("product_id"),
                    "product_name": p.get("product_name"),
                    "category": p.get("category"),
                    "reasons": reasons,
                    "unlock_hint": hint,
                    "product": dict(p)
                })
                if reasons == [cls.REASON_NEEDS_GSTIN]:
                    unlockable_with_gstin.append(p.get("product_id"))

        # Check unmet stated needs
        mapped_cats = profile.get("mapped_categories") or []
        mapped_pids = profile.get("mapped_product_ids") or []
        eligible_pids = set(p["product_id"] for p in eligible)
        eligible_cats = set(p["category"] for p in eligible)

        need_unmet = []
        for cat in mapped_cats:
            if cat not in eligible_cats:
                need_unmet.append({"type": "category", "need": cat, "reason": "No eligible products in category"})
        for pid in mapped_pids:
            if pid not in eligible_pids:
                inelig_info = next((item for item in ineligible if item["product_id"] == pid), None)
                need_unmet.append({
                    "type": "product",
                    "need": pid,
                    "reasons": inelig_info["reasons"] if inelig_info else ["INELIGIBLE"],
                    "unlock_hint": inelig_info["unlock_hint"] if inelig_info else ""
                })

        return {
            "eligible_products": eligible,
            "ineligible_products": ineligible,
            "unlockable_with_gstin": unlockable_with_gstin,
            "need_unmet": need_unmet
        }


eligibility_engine = EligibilityEngine()
