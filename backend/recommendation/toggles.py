"""
Stage 12: Interactive Re-runs & What-If Simulation Engine (toggles.py)
Supports dynamic modifications:
- toggle_on(bundle, product_id): adds product, resolves dependencies, returns quote deltas
- toggle_off(bundle, product_id): removes product, cascades removal of orphans, warns on cascade
- edit_quantity(bundle, product_id, qty): re-prices and checks limits
- what_if(profile, changes): full pipeline simulation returning unlocked/locked product diff
"""

from typing import Dict, Any, List, Set, Optional
from database.db_client import db_client
from recommendation.closure import dependency_closure
from recommendation.pricing import pricing_engine
from recommendation.validator import bundle_validator
from recommendation.quantity import quantity_model


class ToggleEngine:
    @classmethod
    def toggle_on(
        cls,
        bundle: Dict[str, Any],
        product_id: str,
        profile: Dict[str, Any],
        cohort_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adds a product to the bundle, resolves prerequisite dependencies, and re-prices.
        """
        catalogue_map = {p["product_id"]: p for p in db_client.get_products()}
        current_products = bundle.get("products") or []
        current_pids = set(p["product_id"] for p in current_products)

        if product_id in current_pids:
            return {"bundle": bundle, "auto_added": [], "deltas": {}}

        # Target set
        target_pids = current_pids | {product_id}
        attach_rates = cohort_stats.get("attach_rates", {})

        closed_pids, auto_added, dropped = dependency_closure.resolve_dependencies(
            target_pids, catalogue_map, attach_rates
        )

        if product_id not in closed_pids:
            return {
                "success": False,
                "error": f"Product '{product_id}' cannot be added due to unsatisfiable dependencies."
            }

        # Build priced items
        new_items = []
        for pid in closed_pids:
            # Preserve existing qty if already present
            existing = next((p for p in current_products if p["product_id"] == pid), None)
            q = existing["qty"] if existing else quantity_model.compute_quantity(pid, profile)
            new_items.append({
                "product_id": pid,
                "qty": q,
                "auto_added_for": auto_added.get(pid)
            })

        priced = pricing_engine.price_bundle(
            new_items,
            price_position_t=cohort_stats.get("price_position_t", 0.5),
            eta_buffer_days=cohort_stats.get("eta_buffer_days", 2)
        )

        old_quote = bundle.get("quote") or {}
        deltas = {
            "monthly_delta": round(priced["monthly_total"] - old_quote.get("monthly_total", 0), 2),
            "setup_delta": round(priced["setup_total"] - old_quote.get("setup_total", 0), 2),
            "contract_change": priced["contract_months"] if priced["contract_months"] != old_quote.get("contract_months") else None,
            "eta_change": priced["eta_days"] - old_quote.get("eta_days", 0)
        }

        new_bundle = dict(bundle)
        new_bundle["products"] = priced["products"]
        new_bundle["quote"] = priced

        return {
            "success": True,
            "bundle": new_bundle,
            "auto_added": list(auto_added.keys()),
            "deltas": deltas
        }

    @classmethod
    def toggle_off(
        cls,
        bundle: Dict[str, Any],
        product_id: str,
        profile: Dict[str, Any],
        cohort_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Removes a product and cascade-prunes dependent products whose prerequisites vanished.
        """
        catalogue_map = {p["product_id"]: p for p in db_client.get_products()}
        current_products = bundle.get("products") or []
        current_pids = set(p["product_id"] for p in current_products)

        if product_id not in current_pids:
            return {"bundle": bundle, "auto_removed": [], "deltas": {}}

        remaining_pids = current_pids - {product_id}
        auto_removed = []

        # Cascade prune: repeat until no product has missing prerequisites
        cascade_pruned = True
        while cascade_pruned:
            cascade_pruned = False
            for pid in list(remaining_pids):
                cat_prod = catalogue_map.get(pid, {})
                req_str = str(cat_prod.get("requires_one_of") or "").strip()
                if req_str:
                    options = [opt.strip() for opt in req_str.split("|") if opt.strip()]
                    if not any(opt in remaining_pids for opt in options):
                        remaining_pids.remove(pid)
                        auto_removed.append({
                            "product_id": pid,
                            "product_name": cat_prod.get("product_name"),
                            "reason": f"Prerequisite '{product_id}' was removed"
                        })
                        cascade_pruned = True

        new_items = []
        for pid in remaining_pids:
            existing = next((p for p in current_products if p["product_id"] == pid), None)
            q = existing["qty"] if existing else 1
            new_items.append({"product_id": pid, "qty": q})

        priced = pricing_engine.price_bundle(
            new_items,
            price_position_t=cohort_stats.get("price_position_t", 0.5),
            eta_buffer_days=cohort_stats.get("eta_buffer_days", 2)
        )

        old_quote = bundle.get("quote") or {}
        deltas = {
            "monthly_delta": round(priced["monthly_total"] - old_quote.get("monthly_total", 0), 2),
            "setup_delta": round(priced["setup_total"] - old_quote.get("setup_total", 0), 2),
            "contract_change": priced["contract_months"] if priced["contract_months"] != old_quote.get("contract_months") else None,
            "eta_change": priced["eta_days"] - old_quote.get("eta_days", 0)
        }

        new_bundle = dict(bundle)
        new_bundle["products"] = priced["products"]
        new_bundle["quote"] = priced

        return {
            "success": True,
            "bundle": new_bundle,
            "auto_removed": auto_removed,
            "deltas": deltas,
            "cascade_warning": len(auto_removed) > 0
        }

    @classmethod
    def edit_quantity(
        cls,
        bundle: Dict[str, Any],
        product_id: str,
        qty: int,
        cohort_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates product quantity in bundle, re-validates limits, and re-prices.
        """
        if qty < 1:
            return {"success": False, "error": "Quantity must be at least 1"}

        current_products = bundle.get("products") or []
        found = False
        new_items = []
        for p in current_products:
            if p["product_id"] == product_id:
                found = True
                new_items.append({"product_id": p["product_id"], "qty": qty})
            else:
                new_items.append({"product_id": p["product_id"], "qty": p["qty"]})

        if not found:
            return {"success": False, "error": f"Product '{product_id}' not found in bundle"}

        priced = pricing_engine.price_bundle(
            new_items,
            price_position_t=cohort_stats.get("price_position_t", 0.5),
            eta_buffer_days=cohort_stats.get("eta_buffer_days", 2)
        )

        old_quote = bundle.get("quote") or {}
        deltas = {
            "monthly_delta": round(priced["monthly_total"] - old_quote.get("monthly_total", 0), 2),
            "setup_delta": round(priced["setup_total"] - old_quote.get("setup_total", 0), 2)
        }

        new_bundle = dict(bundle)
        new_bundle["products"] = priced["products"]
        new_bundle["quote"] = priced

        return {
            "success": True,
            "bundle": new_bundle,
            "deltas": deltas
        }


toggle_engine = ToggleEngine()

