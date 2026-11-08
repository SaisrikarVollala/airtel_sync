"""
Stage 7: Multi-Factor Scoring Engine (scoring.py)
Scores candidate bundles using 5 normalized [0, 1] components:
- Need coverage (0.35)
- Budget fit (0.25) with asymmetric over/under penalties
- Retention (0.15)
- Popularity (0.15)
- NPS (0.10)
Includes stretch flag detection and complexity control for Micro enterprises.
"""

from typing import Dict, Any, List
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


def load_scoring_config():
    w_file = CONFIG_DIR / "weights.yaml"
    th_file = CONFIG_DIR / "thresholds.yaml"
    weights = {"need": 0.35, "budget": 0.25, "retention": 0.15, "popularity": 0.15, "nps": 0.10}
    thresholds = {
        "over_penalty": 1.0,
        "under_penalty": 0.5,
        "budget_tolerance": 0.10,
        "complexity_free_products": 4
    }
    if w_file.exists():
        with open(w_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            weights = data.get("scoring", weights)
    if th_file.exists():
        with open(th_file, "r", encoding="utf-8") as f:
            thresholds.update(yaml.safe_load(f) or {})
    return weights, thresholds


class BundleScorer:
    @classmethod
    def score_candidates(
        cls,
        candidates: List[Dict[str, Any]],
        profile: Dict[str, Any],
        cohort_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Calculates multidimensional score and attaches full component breakdown.
        """
        if not candidates:
            return []

        weights, thresholds = load_scoring_config()
        attach_rates = cohort_stats.get("attach_rates", {})
        shrunk_ret = cohort_stats.get("shrunk_retention", {})
        shrunk_nps = cohort_stats.get("shrunk_nps", {})

        # Stated needs to cover
        mapped_cats = profile.get("mapped_categories") or ["Connectivity"]
        mapped_pids = profile.get("mapped_product_ids") or []
        total_needs = len(mapped_cats) + len(mapped_pids)
        if total_needs == 0:
            total_needs = 1

        # Budget target
        spend = float(profile.get("monthly_telecom_spend_inr") or 0)
        spend_ratio_med = float(cohort_stats.get("median_spend_ratio", 2.5))
        if spend > 0:
            target_budget = spend * spend_ratio_med
        else:
            # Fallback to cohort median monthly bundle value (~2500 for micro, ~10000 for multi)
            target_budget = 3000.0 if "Micro" in str(profile.get("segment")) else 8000.0

        affordability_ceiling = float(cohort_stats.get("affordability_ceiling", 3.9))

        # First pass: compute raw popularity for normalisation
        raw_popularities = []
        for cand in candidates:
            pids = [p["product_id"] for p in cand["products"]]
            mean_att = sum(attach_rates.get(pid, 0.0) for pid in pids) / max(1, len(pids))
            raw_popularities.append(mean_att)
        max_pop = max(raw_popularities) if raw_popularities and max(raw_popularities) > 0 else 1.0

        scored_candidates = []

        for i, cand in enumerate(candidates):
            products = cand["products"]
            pids = [p["product_id"] for p in products]
            cats_in_bundle = set(p["category"] for p in products)
            pids_in_bundle = set(pids)

            # 1. Need coverage [0, 1]
            covered_count = 0
            for cat in mapped_cats:
                if cat in cats_in_bundle:
                    covered_count += 1
            for req_pid in mapped_pids:
                if req_pid in pids_in_bundle:
                    covered_count += 1
            need_score = min(1.0, covered_count / max(1, total_needs))

            # 2. Popularity [0, 1]
            pop_score = min(1.0, raw_popularities[i] / max_pop)

            # 3. Retention [0, 1]
            ret_vals = [shrunk_ret.get(pid, 0.8) for pid in pids]
            ret_score = min(1.0, max(0.0, sum(ret_vals) / max(1, len(ret_vals))))

            # 4. NPS [0, 1]
            nps_vals = [shrunk_nps.get(pid, 7.0) for pid in pids]
            nps_score = min(1.0, max(0.0, (sum(nps_vals) / max(1, len(nps_vals))) / 10.0))

            # 5. Budget fit [0, 1]
            effective_m = cand["quote"]["effective_monthly"]
            gap = (effective_m - target_budget) / target_budget
            tol = thresholds.get("budget_tolerance", 0.10)

            if abs(gap) <= tol:
                budget_fit = 1.0
            elif gap > 0:
                budget_fit = max(0.0, 1.0 - thresholds.get("over_penalty", 1.0) * (gap - tol))
            else:
                budget_fit = max(0.0, 1.0 - thresholds.get("under_penalty", 0.5) * (abs(gap) - tol))

            # Stretch check
            stretch = False
            if spend > 0:
                current_ratio = effective_m / spend
                if current_ratio > affordability_ceiling:
                    stretch = True

            # Complexity penalty for Micro segment (>4 items)
            complexity_penalty = 0.0
            if "Micro" in str(profile.get("segment")):
                excess = len(pids) - thresholds.get("complexity_free_products", 4)
                if excess > 0:
                    complexity_penalty = excess * 0.03

            # Total score
            raw_score = (
                weights.get("need", 0.35) * need_score +
                weights.get("budget", 0.25) * budget_fit +
                weights.get("retention", 0.15) * ret_score +
                weights.get("popularity", 0.15) * pop_score +
                weights.get("nps", 0.10) * nps_score -
                complexity_penalty
            )
            final_score = round(max(0.0, min(1.0, raw_score)), 4)

            cand_copy = dict(cand)
            cand_copy["score"] = final_score
            cand_copy["score_breakdown"] = {
                "need": round(need_score, 3),
                "budget": round(budget_fit, 3),
                "retention": round(ret_score, 3),
                "popularity": round(pop_score, 3),
                "nps": round(nps_score, 3)
            }
            cand_copy["stretch"] = stretch
            scored_candidates.append(cand_copy)

        # Sort: score DESC -> need_score DESC -> effective_monthly ASC
        scored_candidates.sort(
            key=lambda x: (
                x["score"],
                x["score_breakdown"]["need"],
                -x["quote"]["effective_monthly"]
            ),
            reverse=True
        )

        return scored_candidates


bundle_scorer = BundleScorer()

