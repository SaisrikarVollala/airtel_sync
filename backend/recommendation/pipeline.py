"""
RECOMMENDATION PIPELINE: Full 14-Stage Orchestrator (pipeline.py)
Implements the hybrid, knowledge-based recommendation pipeline:
- Knowledge-based hard rules (eligibility, dependencies, validator)
- Stated need-based relevance
- Lookalike cohort collaboration with 6-level back-off
- 5-factor scoring & MMR diversity top-2
- Structured reason codes & grounded explanations
- Standard Output Contract matching reccomendation.md
"""

from typing import Dict, Any, List, Optional
from database.db_client import db_client
from recommendation.needs import normalise_profile, validate_profile_readiness
from recommendation.eligibility import eligibility_engine
from recommendation.cohort import cohort_matcher
from recommendation.stats import cohort_stats_service
from recommendation.candidates import candidate_generator
from recommendation.scoring import bundle_scorer
from recommendation.diversify import diversity_selector
from recommendation.addons import addon_engine
from recommendation.reasons import reason_code_generator
from recommendation.explain import explanation_service
from recommendation.logging import recommendation_logger


class RecommendationPipeline:
    def recommend(
        self,
        raw_profile: Dict[str, Any],
        language: str = "en",
        train_only: bool = False
    ) -> Dict[str, Any]:
        """
        Executes end-to-end recommendation pipeline.
        """
        # ---------------------------------------------------------------------
        # STAGE 0: Profile Normalisation & Readiness Validation
        # ---------------------------------------------------------------------
        profile = normalise_profile(raw_profile)
        ready, missing_fields, next_question = validate_profile_readiness(profile)

        profile_used = {
            "business_name": profile.get("business_name"),
            "business_type": profile.get("business_type"),
            "segment": profile.get("segment"),
            "city": profile.get("city"),
            "city_tier": profile.get("city_tier"),
            "employee_count": profile.get("employee_count"),
            "num_sites": profile.get("num_sites"),
            "has_gstin": profile.get("has_gstin_bool", False),
            "gstin_valid_for_sale": profile.get("gstin_valid_for_sale", False),
            "monthly_telecom_spend_inr": profile.get("monthly_telecom_spend_inr"),
            "needs": profile.get("needs_raw", [])
        }

        if not ready:
            return {
                "ready": False,
                "profile_used": profile_used,
                "missing_fields": missing_fields,
                "next_question": next_question,
                "options": [],
                "warnings": ["PROFILE_INCOMPLETE"]
            }

        # ---------------------------------------------------------------------
        # STAGE 1: Hard-Rule Eligibility
        # ---------------------------------------------------------------------
        elig_result = eligibility_engine.filter_catalogue(profile)
        eligible_products = elig_result["eligible_products"]
        ineligible_products = elig_result["ineligible_products"]
        unlockable_with_gstin = elig_result["unlockable_with_gstin"]

        # ---------------------------------------------------------------------
        # STAGE 2: Similar-Customer Cohort with 6-Level Back-off
        # ---------------------------------------------------------------------
        cohort_res = cohort_matcher.match_cohort(profile, train_only=train_only)
        cohort_leads = cohort_res.get("leads", [])

        cohort_info = {
            "level": cohort_res["level"],
            "n": cohort_res["n"],
            "filters": cohort_res["filters"]
        }

        # ---------------------------------------------------------------------
        # STAGE 3: Cohort Statistics & Empirical Learning
        # ---------------------------------------------------------------------
        cohort_stats = cohort_stats_service.compute_cohort_stats(cohort_leads)

        # ---------------------------------------------------------------------
        # STAGE 4 & 5: Candidate Generation, Closure, Quantities, Validation
        # ---------------------------------------------------------------------
        validated_candidates = candidate_generator.generate_candidates(
            profile=profile,
            eligible_products=eligible_products,
            cohort_stats=cohort_stats,
            max_candidates=40
        )

        # ---------------------------------------------------------------------
        # STAGE 7: Multi-Factor Scoring
        # ---------------------------------------------------------------------
        scored_candidates = bundle_scorer.score_candidates(
            candidates=validated_candidates,
            profile=profile,
            cohort_stats=cohort_stats
        )

        # ---------------------------------------------------------------------
        # STAGE 8: Diversity Re-Ranking & Top-2 Selection (MMR)
        # ---------------------------------------------------------------------
        top_options, single_option_reason = diversity_selector.select_top_2(scored_candidates)

        # ---------------------------------------------------------------------
        # STAGE 9, 10, 11: Add-ons, Quote assembly, Reasons, Explanations
        # ---------------------------------------------------------------------
        assembled_options = []
        for opt in top_options:
            # 1. Generate 3 tiers of add-ons
            addons = addon_engine.generate_addons(
                base_option=opt,
                eligible_products=eligible_products,
                profile=profile,
                cohort_stats=cohort_stats
            )

            # 2. Generate structured reason codes
            reasons = reason_code_generator.generate_reasons(
                bundle=opt,
                profile=profile,
                cohort_info=cohort_info,
                cohort_stats=cohort_stats,
                ineligible_products=ineligible_products,
                contrast_data=opt.get("contrast_vs_a")
            )

            # 3. Generate grounded natural language explanation
            explanation = explanation_service.generate_explanation(
                bundle=opt,
                reasons=reasons,
                profile=profile,
                language=language
            )

            # 4. Excluded products for this option
            excluded_info = [
                {
                    "product_id": inelig["product_id"],
                    "product_name": inelig["product_name"],
                    "reasons": inelig["reasons"],
                    "unlock_hint": inelig["unlock_hint"]
                }
                for inelig in ineligible_products[:4]
            ]

            assembled_options.append({
                "label": opt.get("label", "Recommended"),
                "purpose": opt.get("purpose", "Comprehensive Solution"),
                "products": opt["products"],
                "quote": opt["quote"],
                "score": opt["score"],
                "score_breakdown": opt["score_breakdown"],
                "stretch": opt.get("stretch", False),
                "reasons": reasons,
                "explanation": explanation,
                "addons": addons,
                "excluded": excluded_info
            })

        # ---------------------------------------------------------------------
        # STAGE 13: Audit & Feedback Logging
        # ---------------------------------------------------------------------
        recommendation_logger.log_recommendation(
            profile=profile,
            cohort_info=cohort_info,
            options=assembled_options,
            candidates_scored=scored_candidates,
            single_option_reason=single_option_reason
        )

        warnings = []
        if cohort_stats.get("price_position_t") == 0.5:
            warnings.append("PRICE_POSITION_FALLBACK")
        if not profile.get("gstin_valid_for_sale"):
            warnings.append("GSTIN_UNAVAILABLE_LOCKS_ENTERPRISE_PRODUCTS")

        return {
            "ready": True,
            "profile_used": profile_used,
            "cohort": cohort_info,
            "options": assembled_options,
            "single_option_reason": single_option_reason,
            "unlockable": {
                "with_gstin": unlockable_with_gstin
            },
            "warnings": warnings,
            "versions": {
                "catalogue": "25_products_v2",
                "config": "1.0.0",
                "stats_cutoff": "2026-05-31" if train_only else "2026-06-30"
            }
        }


recommendation_pipeline = RecommendationPipeline()

