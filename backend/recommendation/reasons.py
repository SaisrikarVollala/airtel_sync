"""
Stage 11: Structured Reason Code Generator (reasons.py)
Produces structured fact objects for explainability:
- NEED_MATCH {covered, missing}
- DEPENDENCY {auto_added, for}
- PEER_POPULARITY {pct, n, cohort_level}
- BUDGET {price, current_spend, typical_ratio, stretch}
- RETENTION {retention_pct, n}
- EXCLUSION {product, reason, unlock_hint}
- CONTRAST {vs_option, differences}
"""

from typing import Dict, Any, List


class ReasonCodeGenerator:
    @classmethod
    def generate_reasons(
        cls,
        bundle: Dict[str, Any],
        profile: Dict[str, Any],
        cohort_info: Dict[str, Any],
        cohort_stats: Dict[str, Any],
        ineligible_products: List[Dict[str, Any]],
        contrast_data: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Builds prioritized list of fact-grounded reason codes.
        """
        reasons = []

        products = bundle.get("products") or []
        quote = bundle.get("quote") or {}
        pids = set(p["product_id"] for p in products)
        cats = set(p["category"] for p in products)

        mapped_cats = set(profile.get("mapped_categories") or [])
        mapped_pids = set(profile.get("mapped_product_ids") or [])

        # 1. NEED_MATCH
        covered_cats = list(mapped_cats & cats)
        covered_pids = list(mapped_pids & pids)
        missing_cats = list(mapped_cats - cats)
        reasons.append({
            "code": "NEED_MATCH",
            "title": "Need Alignment",
            "facts": {
                "covered_categories": covered_cats,
                "covered_products": covered_pids,
                "uncovered_categories": missing_cats
            },
            "summary": f"Covers your requested {', '.join(covered_cats or ['telecom'])} requirements"
        })

        # 2. DEPENDENCY (Surprises / Auto-adds)
        for p in products:
            if p.get("auto_added_for"):
                reasons.append({
                    "code": "DEPENDENCY",
                    "title": "Required Pre-requisite Included",
                    "facts": {
                        "auto_added_product": p["product_name"],
                        "for_product": p["auto_added_for"]
                    },
                    "summary": f"Auto-included {p['product_name']} as required prerequisite for {p['auto_added_for']}"
                })

        # 3. PEER_POPULARITY (Only if cohort n >= min_sample 20)
        n = cohort_info.get("n", 0)
        cohort_level = cohort_info.get("level", 5)
        attach_rates = cohort_stats.get("attach_rates", {})
        if n >= 20:
            mean_attach = sum(attach_rates.get(pid, 0.0) for pid in pids) / max(1, len(pids))
            pct = int(mean_attach * 100)
            reasons.append({
                "code": "PEER_POPULARITY",
                "title": "Peer Business Adoption",
                "facts": {
                    "popularity_pct": pct,
                    "cohort_size": n,
                    "cohort_level": cohort_level
                },
                "summary": f"Commonly chosen by {pct}% of similar businesses in your peer cohort (n={n})"
            })

        # 4. BUDGET
        spend = float(profile.get("monthly_telecom_spend_inr") or 0)
        monthly_total = quote.get("monthly_total", 0)
        stretch = bundle.get("stretch", False)
        if spend > 0:
            ratio = round(monthly_total / spend, 2)
            reasons.append({
                "code": "BUDGET",
                "title": "Budget & Spend Fit",
                "facts": {
                    "monthly_price": monthly_total,
                    "current_spend": spend,
                    "spend_ratio": ratio,
                    "stretch": stretch
                },
                "summary": (
                    f"Monthly cost ₹{int(monthly_total)} represents {ratio}x your current spend"
                    + (" (Affordability stretch note applied)" if stretch else " (Within typical peer investment band)")
                )
            })

        # 5. RETENTION
        shrunk_ret = cohort_stats.get("shrunk_retention", {})
        if pids:
            mean_ret = sum(shrunk_ret.get(pid, 0.8) for pid in pids) / len(pids)
            ret_pct = int(mean_ret * 100)
            reasons.append({
                "code": "RETENTION",
                "title": "Historical Stability",
                "facts": {
                    "estimated_retention_pct": ret_pct,
                    "cohort_size": n
                },
                "summary": f"High satisfaction tier: businesses using these services show {ret_pct}% long-term retention"
            })

        # 6. EXCLUSION
        if ineligible_products:
            top_inelig = ineligible_products[:2]
            reasons.append({
                "code": "EXCLUSION",
                "title": "Excluded Products & Unlocks",
                "facts": {
                    "excluded": [
                        {
                            "product_name": item["product_name"],
                            "reasons": item["reasons"],
                            "unlock_hint": item["unlock_hint"]
                        }
                        for item in top_inelig
                    ]
                },
                "summary": f"{top_inelig[0]['product_name']} excluded: {top_inelig[0]['unlock_hint']}"
            })

        # 7. CONTRAST (if provided)
        if contrast_data:
            reasons.append({
                "code": "CONTRAST",
                "title": "Comparison vs Recommended",
                "facts": contrast_data,
                "summary": (
                    f"₹{abs(contrast_data.get('monthly_difference_inr', 0))} "
                    + ("cheaper per month" if contrast_data.get("monthly_difference_inr", 0) < 0 else "higher capacity")
                )
            })

        return reasons


reason_code_generator = ReasonCodeGenerator()

