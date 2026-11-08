"""
Stage 8: Diversity Re-Ranking and Top-2 Selection (diversify.py)
Implements Maximal Marginal Relevance (MMR) with Jaccard overlap constraint (< 0.8).
Ensures Option A (Recommended) and Option B (Alternative) are meaningfully differentiated.
Provides purpose labels and single-option explanation if diversity is impossible.
"""

from typing import Dict, Any, List, Tuple, Optional


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


class DiversitySelector:
    @classmethod
    def select_top_2(
        cls,
        scored_candidates: List[Dict[str, Any]],
        mmr_lambda: float = 0.7,
        max_overlap: float = 0.8
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Selects Top 2 diverse options using MMR.
        Returns: (options: list of 1 or 2 options, single_option_reason: str or None)
        """
        if not scored_candidates:
            return [], "No valid eligible bundles found"

        # Option A: Absolute best score
        opt_a = scored_candidates[0]
        set_a = set(p["product_id"] for p in opt_a["products"])

        # Label Option A
        opt_a["label"] = "Recommended"
        opt_a["purpose"] = "Primary Growth Suite (Best Overall Match)"

        if len(scored_candidates) == 1:
            return [opt_a], "Only one valid bundle configuration available for this business profile"

        # Find Option B via MMR
        best_b = None
        best_mmr_score = -999.0

        for cand in scored_candidates[1:]:
            set_cand = set(p["product_id"] for p in cand["products"])
            sim = jaccard_similarity(set_a, set_cand)

            # Hard constraint: Jaccard < max_overlap (0.8) or different contract
            different_contract = cand["quote"]["contract_months"] != opt_a["quote"]["contract_months"]
            if sim >= max_overlap and not different_contract:
                continue

            mmr = mmr_lambda * cand["score"] - (1.0 - mmr_lambda) * sim
            if mmr > best_mmr_score:
                best_mmr_score = mmr
                best_b = cand

        if best_b is None:
            # Check if any candidate has any difference
            for cand in scored_candidates[1:]:
                set_cand = set(p["product_id"] for p in cand["products"])
                if set_cand != set_a:
                    best_b = cand
                    break

        if best_b is None:
            return [opt_a], "All eligible products collapsed to a single valid configuration"

        # Label Option B
        set_b = set(p["product_id"] for p in best_b["products"])
        cost_a = opt_a["quote"]["monthly_total"]
        cost_b = best_b["quote"]["monthly_total"]

        excluded_in_b = [p["product_name"] for p in opt_a["products"] if p["product_id"] not in set_b]
        added_in_b = [p["product_name"] for p in best_b["products"] if p["product_id"] not in set_a]

        if cost_b < cost_a:
            best_b["label"] = "Value Essential"
            best_b["purpose"] = "Cost-Optimized Alternative (Lower Monthly Commitment)"
        else:
            best_b["label"] = "Comprehensive Tier"
            best_b["purpose"] = "High-Capacity Expansion Tier"

        best_b["contrast_vs_a"] = {
            "monthly_difference_inr": round(cost_b - cost_a, 2),
            "excludes_from_primary": excluded_in_b,
            "adds_to_primary": added_in_b
        }

        return [opt_a, best_b], None


diversity_selector = DiversitySelector()

