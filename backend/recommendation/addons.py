"""
Stage 9: Add-on Generation & Ranking Engine (addons.py)
Generates 3 tiers of add-ons:
1. Required: dependency prerequisites (already in bundle, labelled)
2. Recommended: meets unmet needs or high cohort lift (max 5, ranked)
3. Optional upgrades: valid catalogue items not in core bundle
Computes exact commercial deltas (monthly, setup, contract change, ETA impact).
"""

from typing import Dict, Any, List, Set
from database.db_client import db_client
from recommendation.closure import dependency_closure
from recommendation.pricing import pricing_engine
from recommendation.quantity import quantity_model


class AddonEngine:
    @classmethod
    def generate_addons(
        cls,
        base_option: Dict[str, Any],
        eligible_products: List[Dict[str, Any]],
        profile: Dict[str, Any],
        cohort_stats: Dict[str, Any],
        max_recommended: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Builds {required: [], recommended: [], optional: []} add-on structures.
        """
        eligible_map = {p["product_id"]: p for p in eligible_products}
        pair_lift = cohort_stats.get("pair_lift", {})
        shrunk_ret = cohort_stats.get("shrunk_retention", {})
        attach_rates = cohort_stats.get("attach_rates", {})

        base_quote = base_option["quote"]
        base_monthly = base_quote["monthly_total"]
        base_setup = base_quote["setup_total"]
        base_contract = base_quote["contract_months"]
        base_eta = base_quote["eta_days"]

        base_pids = set(p["product_id"] for p in base_option["products"])
        base_cats = set(p["category"] for p in base_option["products"])

        mapped_cats = profile.get("mapped_categories") or []
        mapped_pids = profile.get("mapped_product_ids") or []

        # 1. Required items (auto-added items already inside base bundle)
        required_items = []
        for p in base_option["products"]:
            if p.get("auto_added_for"):
                required_items.append({
                    "product_id": p["product_id"],
                    "product_name": p["product_name"],
                    "qty": p["qty"],
                    "monthly": p["monthly"],
                    "setup": p["setup"],
                    "auto_added_for": p["auto_added_for"],
                    "reason": f"Required prerequisite for {p['auto_added_for']}"
                })

        # 2. Add-on candidates (eligible products not in bundle)
        addon_candidates = [
            p for p in eligible_products
            if p["product_id"] not in base_pids
        ]

        scored_addons = []

        spend = float(profile.get("monthly_telecom_spend_inr") or 0)
        target = spend * float(cohort_stats.get("median_spend_ratio", 2.5)) if spend > 0 else 5000.0

        for addon in addon_candidates:
            addon_id = addon["product_id"]
            # Test dependency closure with addon
            trial_set = base_pids | {addon_id}
            closed_set, auto_added, dropped = dependency_closure.resolve_dependencies(
                trial_set, eligible_map, attach_rates
            )

            if addon_id not in closed_set:
                continue  # Add-on dependency dropped it

            # What new products are dragged in?
            dragged_in = list(closed_set - base_pids - {addon_id})

            # Price trial bundle
            trial_items = []
            for pid in closed_set:
                q = quantity_model.compute_quantity(pid, profile)
                trial_items.append({"product_id": pid, "qty": q})

            trial_quote = pricing_engine.price_bundle(
                trial_items,
                price_position_t=cohort_stats.get("price_position_t", 0.5),
                eta_buffer_days=cohort_stats.get("eta_buffer_days", 2)
            )

            monthly_delta = round(trial_quote["monthly_total"] - base_monthly, 2)
            setup_delta = round(trial_quote["setup_total"] - base_setup, 2)
            contract_change = (
                trial_quote["contract_months"]
                if trial_quote["contract_months"] > base_contract
                else None
            )
            eta_change = max(0, trial_quote["eta_days"] - base_eta)

            # Ranking features
            # Unmet need check
            meets_unmet_need = (
                (addon.get("category") in mapped_cats and addon.get("category") not in base_cats) or
                (addon_id in mapped_pids)
            )

            # Max lift vs base products
            lifts = [
                pair_lift.get((base_p, addon_id), 1.0)
                for base_p in base_pids
            ]
            max_lift = max(lifts) if lifts else 1.0
            norm_lift = min(1.0, max(0.0, (max_lift - 1.0) / 2.0))

            # Retention delta
            addon_ret = shrunk_ret.get(addon_id, 0.8)
            base_mean_ret = sum(shrunk_ret.get(p, 0.8) for p in base_pids) / max(1, len(base_pids))
            ret_delta = max(0.0, min(1.0, (addon_ret - base_mean_ret) + 0.5))

            # Budget headroom
            new_eff = trial_quote["effective_monthly"]
            headroom = max(0.0, min(1.0, 1.0 - max(0.0, (new_eff - target) / target)))

            # Composite ranking score: 0.40 unmet_need + 0.30 norm_lift + 0.15 ret + 0.15 headroom
            score = (
                (0.40 if meets_unmet_need else 0.0) +
                0.30 * norm_lift +
                0.15 * ret_delta +
                0.15 * headroom
            )

            reason_str = ""
            if meets_unmet_need:
                reason_str = f"Covers your requested {addon.get('category')} solution"
            elif max_lift >= 1.2:
                reason_str = f"Frequently attached together by similar businesses ({max_lift:.1f}x lift)"
            else:
                reason_str = "Complementary digital capability"

            scored_addons.append({
                "product_id": addon_id,
                "product_name": addon.get("product_name"),
                "category": addon.get("category"),
                "monthly_delta": monthly_delta,
                "setup_delta": setup_delta,
                "contract_change": contract_change,
                "eta_change": eta_change,
                "also_adds": dragged_in,
                "score": round(score, 3),
                "is_recommended": meets_unmet_need or max_lift >= 1.2,
                "reason": {
                    "code": "NEED_MATCH" if meets_unmet_need else "CO_PURCHASE_LIFT",
                    "text": reason_str
                }
            })

        # Sort by score DESC
        scored_addons.sort(key=lambda x: x["score"], reverse=True)

        recommended = [a for a in scored_addons if a["is_recommended"]][:max_recommended]
        recommended_pids = set(a["product_id"] for a in recommended)
        optional = [a for a in scored_addons if a["product_id"] not in recommended_pids]

        return {
            "required": required_items,
            "recommended": recommended,
            "optional": optional
        }


addon_engine = AddonEngine()

