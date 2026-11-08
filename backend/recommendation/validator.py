"""
Stage 5c: Bundle Validator (validator.py)
Non-negotiable single validator gate:
Every bundle produced by ANY path (advisor, toggle, stepper, back-office)
must pass validate_bundle(). Zero violations is required.
"""

from typing import Dict, Any, List, Set
from database.db_client import db_client
from recommendation.eligibility import eligibility_engine


class BundleValidator:
    VIOLATION_EMPTY_BUNDLE = "EMPTY_BUNDLE"
    VIOLATION_DUPLICATE_PRODUCT = "DUPLICATE_PRODUCT"
    VIOLATION_INELIGIBLE_PRODUCT = "INELIGIBLE_PRODUCT"
    VIOLATION_UNSATISFIED_DEPENDENCY = "UNSATISFIED_DEPENDENCY"
    VIOLATION_INVALID_QUANTITY = "INVALID_QUANTITY"
    VIOLATION_CONTRACT_TOO_SHORT = "CONTRACT_TOO_SHORT"
    VIOLATION_PRICE_OUT_OF_BOUNDS = "PRICE_OUT_OF_BOUNDS"

    @classmethod
    def validate_bundle(
        cls,
        profile: Dict[str, Any],
        bundle: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validates a bundle against customer profile and catalogue constraints.
        Returns: list of violation dicts [{code, product_id, message}]. Empty list = PASS.
        """
        violations = []
        products = bundle.get("products") or []

        # 1. Non-empty check
        if not products:
            violations.append({
                "code": cls.VIOLATION_EMPTY_BUNDLE,
                "message": "Bundle must contain at least one product"
            })
            return violations

        catalogue_map = {p["product_id"]: p for p in db_client.get_products()}

        seen_pids: Set[str] = set()
        product_ids_in_bundle: Set[str] = set()

        for item in products:
            pid = item.get("product_id")
            if not pid or pid not in catalogue_map:
                violations.append({
                    "code": cls.VIOLATION_INELIGIBLE_PRODUCT,
                    "product_id": pid,
                    "message": f"Product '{pid}' not found in catalogue"
                })
                continue

            # Duplicate check
            if pid in seen_pids:
                violations.append({
                    "code": cls.VIOLATION_DUPLICATE_PRODUCT,
                    "product_id": pid,
                    "message": f"Duplicate product '{pid}' in bundle"
                })
            seen_pids.add(pid)
            product_ids_in_bundle.add(pid)

            cat_prod = catalogue_map[pid]

            # 2. Eligibility check
            is_elig, reasons, _ = eligibility_engine.evaluate_product(cat_prod, profile)
            if not is_elig:
                violations.append({
                    "code": cls.VIOLATION_INELIGIBLE_PRODUCT,
                    "product_id": pid,
                    "reasons": reasons,
                    "message": f"Product '{pid}' is ineligible: {', '.join(reasons)}"
                })

            # 3. Quantity check
            qty = item.get("qty", 1)
            if not isinstance(qty, (int, float)) or qty < 1:
                violations.append({
                    "code": cls.VIOLATION_INVALID_QUANTITY,
                    "product_id": pid,
                    "qty": qty,
                    "message": f"Quantity for '{pid}' must be an integer >= 1"
                })

            # 4. Unit price bounds check
            unit_price = item.get("unit_price")
            if unit_price is not None:
                p_min = float(cat_prod.get("price_min_inr_per_month") or cat_prod.get("monthly_price_inr") or 0)
                p_max = float(cat_prod.get("price_max_inr_per_month") or cat_prod.get("monthly_price_inr") or p_min)
                # Allow small float epsilon of 1.0 rupee
                if float(unit_price) < (p_min - 1.0) or float(unit_price) > (p_max + 1.0):
                    violations.append({
                        "code": cls.VIOLATION_PRICE_OUT_OF_BOUNDS,
                        "product_id": pid,
                        "unit_price": unit_price,
                        "bounds": [p_min, p_max],
                        "message": f"Unit price ₹{unit_price} is out of catalogue range [₹{p_min}, ₹{p_max}]"
                    })

        # 5. Dependency closure check
        for pid in product_ids_in_bundle:
            cat_prod = catalogue_map[pid]
            req_str = str(cat_prod.get("requires_one_of") or "").strip()
            if req_str:
                required_options = [opt.strip() for opt in req_str.split("|") if opt.strip()]
                if not any(opt in product_ids_in_bundle for opt in required_options):
                    violations.append({
                        "code": cls.VIOLATION_UNSATISFIED_DEPENDENCY,
                        "product_id": pid,
                        "requires_one_of": required_options,
                        "message": f"Product '{pid}' requires at least one of {required_options} in the same bundle"
                    })

        # 6. Contract minimum check
        bundle_contract = bundle.get("contract_months")
        if bundle_contract is not None:
            for pid in product_ids_in_bundle:
                cat_prod = catalogue_map[pid]
                min_contract = int(cat_prod.get("min_contract_months") or cat_prod.get("contract_months") or 1)
                if bundle_contract < min_contract:
                    violations.append({
                        "code": cls.VIOLATION_CONTRACT_TOO_SHORT,
                        "product_id": pid,
                        "bundle_contract": bundle_contract,
                        "min_contract": min_contract,
                        "message": f"Bundle contract ({bundle_contract}m) is less than product '{pid}' minimum ({min_contract}m)"
                    })

        return violations


bundle_validator = BundleValidator()

