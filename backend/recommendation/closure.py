"""
Stage 5a: Dependency Closure Engine (closure.py)
Deterministically resolves product prerequisite rules ('requires_one_of').
Ensures every bundle is self-consistent and closed.
Loop-proof via banned set tracking.
"""

from typing import Dict, Any, List, Set, Tuple, Optional


class DependencyClosure:
    @classmethod
    def resolve_dependencies(
        cls,
        candidate_product_ids: Set[str],
        eligible_products_map: Dict[str, Dict[str, Any]],
        cohort_attach_rates: Optional[Dict[str, float]] = None
    ) -> Tuple[Set[str], Dict[str, str], List[Dict[str, Any]]]:
        """
        Closes dependency requirements for candidate products.
        Returns:
            final_product_ids: Set[str] of closed products
            auto_added_map: Dict[added_pid, for_pid]
            dropped_records: List of dropped product dicts with reason
        """
        if cohort_attach_rates is None:
            cohort_attach_rates = {}

        # 1. Filter initial set to strictly eligible products
        current_set = set(pid for pid in candidate_product_ids if pid in eligible_products_map)
        banned_set: Set[str] = set()
        auto_added: Dict[str, str] = {}
        dropped: List[Dict[str, Any]] = []

        # 2. Iterate to fixed point
        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            changed = False

            # Check all current products
            products_to_check = list(current_set)
            for pid in products_to_check:
                if pid in banned_set:
                    continue

                prod_info = eligible_products_map.get(pid)
                if not prod_info:
                    current_set.discard(pid)
                    changed = True
                    continue

                req_str = str(prod_info.get("requires_one_of") or "").strip()
                if not req_str:
                    continue

                # Parse requires_one_of: e.g. "P01|P02|P03|P05|P06"
                required_options = [opt.strip() for opt in req_str.split("|") if opt.strip()]

                # Is requirement satisfied by an already selected product?
                if any(opt in current_set for opt in required_options):
                    continue

                # Find eligible, not-banned candidates among required options
                eligible_options = [
                    opt for opt in required_options
                    if opt in eligible_products_map and opt not in banned_set
                ]

                if not eligible_options:
                    # Unsatisfiable dependency -> drop dependent product
                    current_set.discard(pid)
                    banned_set.add(pid)
                    dropped.append({
                        "product_id": pid,
                        "product_name": prod_info.get("product_name"),
                        "reason": "DEPENDENCY_UNSATISFIABLE",
                        "missing_prerequisites": required_options
                    })
                    changed = True
                    continue

                # Choose best prerequisite:
                # Priority: higher cohort attach rate -> cheaper -> lower product_id
                def prereq_sort_key(opt_id: str):
                    opt_info = eligible_products_map[opt_id]
                    attach = cohort_attach_rates.get(opt_id, 0.0)
                    price = float(opt_info.get("price_min_inr_per_month", 0) or opt_info.get("monthly_price_inr", 0))
                    return (-attach, price, opt_id)

                best_prereq = sorted(eligible_options, key=prereq_sort_key)[0]

                # Auto-add best prerequisite
                current_set.add(best_prereq)
                auto_added[best_prereq] = pid
                changed = True

            if not changed:
                break

        return current_set, auto_added, dropped


dependency_closure = DependencyClosure()

