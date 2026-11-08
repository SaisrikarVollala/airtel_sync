"""
Stage 13: Audit & Feedback Logging (logging.py)
Generates compliant, privacy-preserving rec_log entries:
- Masked profile snapshot (DPDP Act 2023)
- Version timestamps & catalogue hashes
- Candidates considered with scores
- Explanations and reason codes
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from kyc_verification.secure_vault import secure_vault


class RecommendationLogger:
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def log_recommendation(
        self,
        profile: Dict[str, Any],
        cohort_info: Dict[str, Any],
        options: List[Dict[str, Any]],
        candidates_scored: List[Dict[str, Any]],
        single_option_reason: str = None
    ) -> Dict[str, Any]:
        """
        Records structured audit record for the recommendation event.
        """
        # Mask identifiers in profile
        masked_profile = {
            "segment": profile.get("segment"),
            "city": profile.get("city"),
            "city_tier": profile.get("city_tier"),
            "employee_count": profile.get("employee_count"),
            "num_sites": profile.get("num_sites"),
            "has_gstin": profile.get("has_gstin_bool", False),
            "gstin_valid_for_sale": profile.get("gstin_valid_for_sale", False),
            "gstin_masked": secure_vault.mask_pii(profile.get("gstin", ""), "gstin") if profile.get("gstin") else None,
            "needs": profile.get("needs_raw", [])
        }

        # Catalogue hash
        cat_str = "catalogue_25_products_v2"
        cat_hash = hashlib.sha256(cat_str.encode()).hexdigest()[:8]

        log_entry = {
            "log_id": f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.logs)+1}",
            "timestamp": datetime.now().isoformat(),
            "profile_snapshot": masked_profile,
            "catalogue_version": cat_hash,
            "config_version": "1.0.0",
            "cohort": {
                "level": cohort_info.get("level"),
                "n": cohort_info.get("n"),
                "filters": cohort_info.get("filters")
            },
            "candidates_count": len(candidates_scored),
            "candidates_summary": [
                {
                    "signature": c.get("signature"),
                    "score": c.get("score"),
                    "family": c.get("family")
                }
                for c in candidates_scored[:5]
            ],
            "options_count": len(options),
            "options_shown": [
                {
                    "label": opt.get("label"),
                    "products": [p["product_id"] for p in opt.get("products", [])],
                    "monthly_total": opt.get("quote", {}).get("monthly_total"),
                    "score": opt.get("score"),
                    "explanation_source": opt.get("explanation", {}).get("source")
                }
                for opt in options
            ],
            "single_option_reason": single_option_reason
        }

        self.logs.append(log_entry)
        return log_entry

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.logs[-limit:]


recommendation_logger = RecommendationLogger()

