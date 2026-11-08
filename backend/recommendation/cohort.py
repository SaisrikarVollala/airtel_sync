"""
Stage 2: Similar-Customer Cohort Matching with Back-off (cohort.py)
Finds lookalike customer leads using a 6-level back-off ladder.
Guarantees cohort size >= min_cohort (30) while reporting level and filters used.
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import yaml
from database.db_client import db_client

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

_thresholds_cache = None


def load_thresholds() -> Dict[str, Any]:
    global _thresholds_cache
    if _thresholds_cache is None:
        th_file = CONFIG_DIR / "thresholds.yaml"
        if th_file.exists():
            with open(th_file, "r", encoding="utf-8") as f:
                _thresholds_cache = yaml.safe_load(f) or {}
        else:
            _thresholds_cache = {"min_cohort": 30, "min_sample": 20}
    return _thresholds_cache


def get_employee_band(emp: int) -> str:
    # Standard MSME & SMB workforce sizing brackets according to Indian enterprise telecom tiers:
    # 1-5 (Micro / Sole Proprietor), 6-10 (Small Office), 11-25 (Mid-tier SMB),
    # 26-50 (Emerging Enterprise), 51+ (Large Enterprise / Multi-department)
    if emp <= 5:
        return "1-5"
    elif emp <= 10:
        return "6-10"
    elif emp <= 25:
        return "11-25"
    elif emp <= 50:
        return "26-50"
    return "51+"


def get_sites_band(sites: int) -> str:
    if sites <= 1:
        return "1"
    elif sites <= 3:
        return "2-3"
    elif sites <= 10:
        return "4-10"
    return "11+"


class CohortMatcher:
    @classmethod
    def match_cohort(
        cls,
        profile: Dict[str, Any],
        train_only: bool = False,
        cutoff_date: str = "2026-06-01"
    ) -> Dict[str, Any]:
        """
        Executes 6-level back-off ladder over historical leads with known bundles.
        Returns:
            level: int (1 to 6)
            n: int (number of matched leads)
            filters: list of active filter names
            leads: list of matched lead dicts
        """
        thresholds = load_thresholds()
        min_cohort = thresholds.get("min_cohort", 30)

        all_leads = list(db_client.leads.values())
        if not all_leads:
            return {"level": 6, "n": 0, "filters": ["all"], "leads": []}

        # Filter to leads with known bundles
        bundle_leads = [
            l for l in all_leads
            if l.get("bundle_products") and str(l.get("bundle_products")).strip()
        ]

        if train_only:
            bundle_leads = [
                l for l in bundle_leads
                if str(l.get("created_date", "")) < cutoff_date
            ]

        # Extract profile features
        target_segment = profile.get("segment", "Micro retail & services")
        target_tier = profile.get("city_tier", 1)
        target_emp_band = get_employee_band(int(profile.get("employee_count", 5)))
        target_sites_band = get_sites_band(int(profile.get("num_sites", 1)))
        target_gstin = str(profile.get("has_gstin") or "").strip().upper() in ["Y", "TRUE", "1"]

        def lead_gstin(l: Dict[str, Any]) -> bool:
            return str(l.get("has_gstin") or "").strip().upper() in ["Y", "TRUE", "1"]

        def lead_emp_band(l: Dict[str, Any]) -> str:
            val = l.get("employee_count")
            try:
                return get_employee_band(int(float(val)))
            except (ValueError, TypeError):
                return "1-5"

        def lead_sites_band(l: Dict[str, Any]) -> str:
            val = l.get("num_sites")
            try:
                return get_sites_band(int(float(val)))
            except (ValueError, TypeError):
                return "1"

        def lead_tier(l: Dict[str, Any]) -> int:
            val = l.get("city_tier")
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return 1

        # Match levels
        # Level 1: segment + tier + sites + employee_band + gstin
        c1 = [
            l for l in bundle_leads
            if l.get("segment") == target_segment
            and lead_tier(l) == target_tier
            and lead_sites_band(l) == target_sites_band
            and lead_emp_band(l) == target_emp_band
            and lead_gstin(l) == target_gstin
        ]
        if len(c1) >= min_cohort:
            return {
                "level": 1,
                "n": len(c1),
                "filters": ["segment", "city_tier", "sites_band", "employee_band", "has_gstin"],
                "leads": c1
            }

        # Level 2: drop employee band
        c2 = [
            l for l in bundle_leads
            if l.get("segment") == target_segment
            and lead_tier(l) == target_tier
            and lead_sites_band(l) == target_sites_band
            and lead_gstin(l) == target_gstin
        ]
        if len(c2) >= min_cohort:
            return {
                "level": 2,
                "n": len(c2),
                "filters": ["segment", "city_tier", "sites_band", "has_gstin"],
                "leads": c2
            }

        # Level 3: drop city tier
        c3 = [
            l for l in bundle_leads
            if l.get("segment") == target_segment
            and lead_sites_band(l) == target_sites_band
            and lead_gstin(l) == target_gstin
        ]
        if len(c3) >= min_cohort:
            return {
                "level": 3,
                "n": len(c3),
                "filters": ["segment", "sites_band", "has_gstin"],
                "leads": c3
            }

        # Level 4: drop gstin flag
        c4 = [
            l for l in bundle_leads
            if l.get("segment") == target_segment
            and lead_sites_band(l) == target_sites_band
        ]
        if len(c4) >= min_cohort:
            return {
                "level": 4,
                "n": len(c4),
                "filters": ["segment", "sites_band"],
                "leads": c4
            }

        # Level 5: segment only
        c5 = [l for l in bundle_leads if l.get("segment") == target_segment]
        if len(c5) >= min_cohort or len(c5) > 0:
            return {
                "level": 5,
                "n": len(c5),
                "filters": ["segment"],
                "leads": c5
            }

        # Level 6: all training leads with bundle
        return {
            "level": 6,
            "n": len(bundle_leads),
            "filters": ["all_customers"],
            "leads": bundle_leads
        }


cohort_matcher = CohortMatcher()

