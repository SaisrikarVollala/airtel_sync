"""
Stage 4: Candidate Generation Engine (candidates.py)
Generates bundle candidates from three orthogonal families:
1. Need-based builds: Lean, Best Fit, Complete
2. Proven historical bundles: top bundles in cohort
3. Cohort-core bundle: high-attach foundation
Deduplicates and runs dependency closure + quantity sizing.
"""

from typing import Dict, Any, List, Set
from database.db_client import db_client
from recommendation.closure import dependency_closure
from recommendation.quantity import quantity_model
from recommendation.validator import bundle_validator
from recommendation.pricing import pricing_engine


class CandidateGenerator:
    @classmethod
    def generate_candidates(
        cls,
        profile: Dict[str, Any],
        eligible_products: List[Dict[str, Any]],
        cohort_stats: Dict[str, Any],
        max_candidates: int = 40
    ) -> List[Dict[str, Any]]:
        """
        Produces deduplicated, validated candidate bundles.
        """
        eligible_map = {p["product_id"]: p for p in eligible_products}
        attach_rates = cohort_stats.get("attach_rates", {})
        top_bundles = cohort_stats.get("top_bundles", [])

        mapped_cats = profile.get("mapped_categories") or ["Connectivity"]
        mapped_pids = profile.get("mapped_product_ids") or []

        candidate_sets: List[Dict[str, Any]] = []

        # ---------------------------------------------------------------------
        # Family A: Need-Based Builds (Lean, Best Fit, Complete)
        # ---------------------------------------------------------------------
        lean_set: Set[str] = set()
        best_fit_set: Set[str] = set()

        # Group eligible products by category
        cat_to_prods: Dict[str, List[Dict[str, Any]]] = {}
        for p in eligible_products:
            cat_to_prods.setdefault(p.get("category", "Connectivity"), []).append(p)

        # For each needed category or explicit product ID
        for cat in mapped_cats:
            available = cat_to_prods.get(cat, [])
            if not available:
                continue

            # Lean: cheapest
            cheapest = sorted(
                available,
                key=lambda x: (float(x.get("price_min_inr_per_month", 0)), float(x.get("one_time_setup_inr", 0)), x.get("product_id"))
            )[0]
            lean_set.add(cheapest["product_id"])

            # Best fit: highest cohort attach rate
            highest_attach = sorted(
                available,
                key=lambda x: (-attach_rates.get(x["product_id"], 0.0), float(x.get("price_min_inr_per_month", 0)))
            )[0]
            best_fit_set.add(highest_attach["product_id"])

        # Also add directly requested product IDs if eligible
        for pid in mapped_pids:
            if pid in eligible_map:
                lean_set.add(pid)
                best_fit_set.add(pid)

        # Complete: best fit + top 2 highest attached eligible extras
        complete_set = set(best_fit_set)
        extras = sorted(
            [p for p in eligible_products if p["product_id"] not in complete_set],
            key=lambda x: -attach_rates.get(x["product_id"], 0.0)
        )[:2]
        for ex in extras:
            complete_set.add(ex["product_id"])

        if lean_set:
            candidate_sets.append({"family": "lean", "pids": lean_set})
        if best_fit_set:
            candidate_sets.append({"family": "best_fit", "pids": best_fit_set})
        if complete_set:
            candidate_sets.append({"family": "complete", "pids": complete_set})

        # ---------------------------------------------------------------------
        # Family B: Proven Bundles from Cohort
        # ---------------------------------------------------------------------
        for bp_str, freq in top_bundles[:10]:
            p_items = [part.split("x")[0].strip() for part in bp_str.split(";") if part.strip()]
            valid_pids = set(pid for pid in p_items if pid in eligible_map)
            # Add back best fit for any uncovered need
            for pid in best_fit_set:
                valid_pids.add(pid)
            if valid_pids:
                candidate_sets.append({"family": "proven", "pids": valid_pids})

        # ---------------------------------------------------------------------
        # Family C: Cohort Core Foundation
        # ---------------------------------------------------------------------
        core_set = set(
            pid for pid, rate in attach_rates.items()
            if rate >= 0.5 and pid in eligible_map
        )
        if core_set:
            candidate_sets.append({"family": "cohort_core", "pids": core_set | best_fit_set})

        # ---------------------------------------------------------------------
        # Deduplication & Closure + Sizing + Validation
        # ---------------------------------------------------------------------
        seen_signatures: Set[str] = set()
        validated_candidates: List[Dict[str, Any]] = []

        price_t = cohort_stats.get("price_position_t", 0.5)
        eta_buffer = cohort_stats.get("eta_buffer_days", 2)

        for cand in candidate_sets:
            initial_pids = cand["pids"]
            # 1. Dependency closure
            closed_pids, auto_added, dropped = dependency_closure.resolve_dependencies(
                initial_pids, eligible_map, attach_rates
            )

            if not closed_pids:
                continue

            sig = ";".join(sorted(list(closed_pids)))
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            # 2. Sizing quantities
            items_with_qty = []
            for pid in sorted(list(closed_pids)):
                q = quantity_model.compute_quantity(pid, profile)
                items_with_qty.append({
                    "product_id": pid,
                    "qty": q,
                    "auto_added_for": auto_added.get(pid)
                })

            # 3. Price bundle
            priced = pricing_engine.price_bundle(
                items_with_qty,
                price_position_t=price_t,
                eta_buffer_days=eta_buffer
            )

            # 4. Validate through single gate
            bundle_to_validate = {
                "products": priced["products"],
                "contract_months": priced["contract_months"]
            }
            violations = bundle_validator.validate_bundle(profile, bundle_to_validate)
            if violations:
                continue  # Discard invalid bundles

            validated_candidates.append({
                "family": cand["family"],
                "signature": sig,
                "products": priced["products"],
                "quote": priced,
                "auto_added": auto_added,
                "product_ids": closed_pids
            })

            if len(validated_candidates) >= max_candidates:
                break

        return validated_candidates


candidate_generator = CandidateGenerator()

