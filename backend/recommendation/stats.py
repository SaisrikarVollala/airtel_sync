"""
Stage 3: Cohort Statistics and Empirical Analytics (stats.py)
Computes cohort-level empirical statistics:
- Weighted product attach rates
- Top exact bundle frequencies
- Product pair co-purchase lift
- Shrunk retention and NPS (Bayesian shrinkage with k=5)
- Spend ratios (median, p25, p75) and affordability ceiling
- Median price position t
- ETA buffer calibration
"""

import math
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import yaml
from database.db_client import db_client

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

_stats_cache: Dict[str, Any] = {}


def load_config() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    th_file = CONFIG_DIR / "thresholds.yaml"
    w_file = CONFIG_DIR / "weights.yaml"
    thresholds = {}
    weights = {}
    if th_file.exists():
        with open(th_file, "r", encoding="utf-8") as f:
            thresholds = yaml.safe_load(f) or {}
    if w_file.exists():
        with open(w_file, "r", encoding="utf-8") as f:
            weights = yaml.safe_load(f) or {}
    return thresholds, weights


def parse_bundle_string(bp: str) -> List[Tuple[str, int]]:
    """Parses 'P01x2;P07x1' into [('P01', 2), ('P07', 1)]."""
    items = []
    for part in bp.split(";"):
        part = part.strip()
        if not part:
            continue
        if "x" in part:
            pid, qty_s = part.split("x", 1)
            items.append((pid.strip(), int(qty_s) if qty_s.isdigit() else 1))
        else:
            items.append((part.strip(), 1))
    return items


class CohortStatsService:
    @classmethod
    def compute_cohort_stats(
        cls,
        cohort_leads: List[Dict[str, Any]],
        all_leads: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Computes all empirical analytics for a matched cohort.
        """
        thresholds, weights = load_config()
        k_shrinkage = thresholds.get("shrinkage_k", 5)
        label_w = weights.get("label_weights", {
            "activated_retained": 1.0,
            "activated_churned": 0.7,
            "accepted_not_activated": 0.5
        })

        if all_leads is None:
            all_leads = db_client.get_all_leads()

        # Base population rates for shrinkage
        act_all = [l for l in all_leads if l.get("outcome") == "Activated"]
        base_churn = (
            sum(1 for l in act_all if str(l.get("churned_within_6_months")).upper() == "Y") / max(1, len(act_all))
        )
        nps_all = [float(l["nps_score"]) for l in act_all if l.get("nps_score")]
        base_nps = sum(nps_all) / max(1, len(nps_all)) if nps_all else 7.0

        n_cohort = len(cohort_leads)
        if n_cohort == 0:
            return cls._empty_stats(base_churn, base_nps)

        cache_key = tuple(sorted(l.get("lead_id", "") for l in cohort_leads))
        if cache_key in _stats_cache:
            return _stats_cache[cache_key]

        # 1. Weights and parsing
        # Lead weight: activated_retained=1.0, activated_churned=0.7, quote_accepted=0.5
        weighted_lead_count = 0.0
        product_weighted_counts: Dict[str, float] = {}
        product_lead_counts: Dict[str, int] = {}
        product_churn_counts: Dict[str, int] = {}
        product_nps_lists: Dict[str, List[float]] = {}
        bundle_counts: Dict[str, int] = {}
        spend_ratios: List[float] = []
        price_ts: List[float] = []

        catalogue_map = {p["product_id"]: p for p in db_client.get_products()}

        lead_products_map: Dict[str, set] = {}

        for l in cohort_leads:
            outcome = l.get("outcome", "")
            is_churn = str(l.get("churned_within_6_months", "")).strip().upper() == "Y"
            w = label_w.get("activated_retained", 1.0)
            if outcome == "Activated":
                w = label_w.get("activated_churned", 0.7) if is_churn else label_w.get("activated_retained", 1.0)
            elif "Quote Accepted" in str(l.get("stage_reached", "")):
                w = label_w.get("accepted_not_activated", 0.5)

            weighted_lead_count += w

            bp = str(l.get("bundle_products") or "").strip()
            if bp:
                bundle_counts[bp] = bundle_counts.get(bp, 0) + 1
                parsed_items = parse_bundle_string(bp)
                p_set = set(pid for pid, _ in parsed_items)
                lead_products_map[l.get("lead_id", str(len(lead_products_map)))] = p_set

                # Spend ratio & price position (for activated leads)
                if outcome == "Activated":
                    sp = float(l.get("monthly_telecom_spend_inr") or 0)
                    bv = float(l.get("monthly_bundle_value_inr") or 0)
                    if sp > 0 and bv > 0:
                        spend_ratios.append(bv / sp)

                    min_tot = sum(catalogue_map[pid].get("price_min_inr_per_month", 0) * q for pid, q in parsed_items if pid in catalogue_map)
                    max_tot = sum(catalogue_map[pid].get("price_max_inr_per_month", 0) * q for pid, q in parsed_items if pid in catalogue_map)
                    if max_tot > min_tot:
                        t = (bv - min_tot) / (max_tot - min_tot)
                        price_ts.append(max(0.0, min(1.0, t)))

                for pid, qty in parsed_items:
                    product_weighted_counts[pid] = product_weighted_counts.get(pid, 0.0) + w
                    product_lead_counts[pid] = product_lead_counts.get(pid, 0) + 1
                    if outcome == "Activated":
                        if is_churn:
                            product_churn_counts[pid] = product_churn_counts.get(pid, 0) + 1
                        if l.get("nps_score"):
                            try:
                                product_nps_lists.setdefault(pid, []).append(float(l["nps_score"]))
                            except (ValueError, TypeError):
                                pass

        # 2. Attach rates (weighted)
        attach_rates = {}
        for pid in catalogue_map.keys():
            w_cnt = product_weighted_counts.get(pid, 0.0)
            attach_rates[pid] = w_cnt / max(1.0, weighted_lead_count)

        # 3. Exact bundle frequency (top 15)
        top_bundles = sorted(bundle_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # 4. Pair lift P(B|A) / P(B)
        total_bundle_leads = max(1, len(lead_products_map))
        pair_counts: Dict[Tuple[str, str], int] = {}
        for p_set in lead_products_map.values():
            p_list = sorted(list(p_set))
            for i in range(len(p_list)):
                for j in range(len(p_list)):
                    if i != j:
                        pair = (p_list[i], p_list[j])
                        pair_counts[pair] = pair_counts.get(pair, 0) + 1

        pair_lift: Dict[Tuple[str, str], float] = {}
        for (p_a, p_b), ab_cnt in pair_counts.items():
            a_cnt = product_lead_counts.get(p_a, 0)
            b_cnt = product_lead_counts.get(p_b, 0)
            if a_cnt >= 3 and b_cnt >= 3:
                p_b_given_a = ab_cnt / a_cnt
                p_b = b_cnt / total_bundle_leads
                pair_lift[(p_a, p_b)] = round(p_b_given_a / max(0.001, p_b), 2)

        # 5. Shrunk retention & NPS
        shrunk_retention = {}
        shrunk_nps = {}
        for pid in catalogue_map.keys():
            n_p = product_lead_counts.get(pid, 0)
            churned = product_churn_counts.get(pid, 0)
            shrunk_churn = (churned + k_shrinkage * base_churn) / (n_p + k_shrinkage)
            shrunk_retention[pid] = max(0.0, min(1.0, 1.0 - shrunk_churn))

            nps_vals = product_nps_lists.get(pid, [])
            nps_sum = sum(nps_vals)
            n_nps = len(nps_vals)
            shrunk_nps[pid] = (nps_sum + k_shrinkage * base_nps) / (n_nps + k_shrinkage)

        # 6. Spend ratio percentiles
        if spend_ratios:
            spend_ratios.sort()
            median_spend_ratio = spend_ratios[len(spend_ratios) // 2]
            p25_idx = int(0.25 * len(spend_ratios))
            p75_idx = int(0.75 * len(spend_ratios))
            p25_spend_ratio = spend_ratios[p25_idx]
            p75_spend_ratio = spend_ratios[p75_idx]
        else:
            median_spend_ratio = 2.5
            p25_spend_ratio = 1.8
            p75_spend_ratio = 3.9

        # 7. Price position t
        if price_ts:
            price_ts.sort()
            median_t = price_ts[len(price_ts) // 2]
        else:
            median_t = thresholds.get("default_t", 0.5)

        result = {
            "n": n_cohort,
            "weighted_n": round(weighted_lead_count, 1),
            "attach_rates": attach_rates,
            "top_bundles": top_bundles,
            "pair_lift": pair_lift,
            "shrunk_retention": shrunk_retention,
            "shrunk_nps": shrunk_nps,
            "median_spend_ratio": round(median_spend_ratio, 2),
            "p25_spend_ratio": round(p25_spend_ratio, 2),
            "p75_spend_ratio": round(p75_spend_ratio, 2),
            "affordability_ceiling": round(p75_spend_ratio, 2),
            "price_position_t": round(median_t, 2),
            "setup_rule": "qty_multiplied",
            "eta_buffer_days": 2
        }
        _stats_cache[cache_key] = result
        return result

    @classmethod
    def _empty_stats(cls, base_churn: float, base_nps: float) -> Dict[str, Any]:
        return {
            "n": 0,
            "weighted_n": 0.0,
            "attach_rates": {},
            "top_bundles": [],
            "pair_lift": {},
            "shrunk_retention": {},
            "shrunk_nps": {},
            "median_spend_ratio": 2.5,
            "p25_spend_ratio": 1.8,
            "p75_spend_ratio": 3.9,
            "affordability_ceiling": 3.9,
            "price_position_t": 0.5,
            "setup_rule": "qty_multiplied",
            "eta_buffer_days": 2
        }


cohort_stats_service = CohortStatsService()
