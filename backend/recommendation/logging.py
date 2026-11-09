"""
Stage 13: Audit & Feedback Logging (logging.py)
Generates compliant, privacy-preserving rec_log entries:
- Masked profile snapshot (DPDP Act 2023)
- Version timestamps & catalogue hashes
- Candidates considered with scores
- Explanations and reason codes
- Persistent storage in Supabase recommendation_logs table
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List
from kyc_verification.secure_vault import secure_vault
from database.db_client import db_client


class RecommendationLogger:
    def log_recommendation(
        self,
        profile: Dict[str, Any],
        cohort_info: Dict[str, Any],
        options: List[Dict[str, Any]],
        candidates_scored: List[Dict[str, Any]],
        single_option_reason: str = None
    ) -> Dict[str, Any]:
        """
        Records structured audit record for the recommendation event into Supabase.
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

        log_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        log_entry = {
            "log_id": log_id,
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

        try:
            db_client.save_recommendation_log(log_entry)
        except Exception as e:
            print(f"Warning: Failed to save recommendation log to Supabase: {e}")

        return log_entry

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries persistent recommendation logs from Supabase."""
        return db_client.get_recommendation_logs(limit=limit)


recommendation_logger = RecommendationLogger()
