"""
=============================================================================
AGENT: Deterministic Question Planner & Detector (question_planner.py)
=============================================================================
Evaluates customer discovery progress deterministically:
- Detects which required attributes are missing
- Calculates completion percentage (0% to 100%)
- Prioritizes asking ONE focused question at a time
- Provides the operational rationale behind why the field is required
=============================================================================
"""

from typing import List, Dict, Any, Optional
from schema.customer_profile import CustomerSchema

# Canonical discovery fields needed for 100% completion
REQUIRED_FIELDS = [
    'business_type',
    'employee_count',
    'num_sites',
    'city',
    'needs',
    'monthly_telecom_spend_inr',
    'has_gstin',
    'has_udyam',
    'max_installation_days'
]

# Canonical questions mapped to each field
QUESTION_MAP = {
    "business_type": "What type of business do you run?",
    "employee_count": "Approximately how many employees work in your business?",
    "num_sites": "How many branches or business locations do you currently operate?",
    "city": "Which city is your business located in?",
    "needs": "What business services are you looking for today? For example Internet, WiFi, CCTV or Cloud services.",
    "monthly_telecom_spend_inr": "What is your approximate monthly telecom spend or telecom budget?",
    "has_gstin": "Do you currently have a GST registration (GSTIN) for your business?",
    "has_udyam": "Is your business registered under Udyam (MSME)?",
    "max_installation_days": "Within how many days do you need the installation completed?"
}

# Rationale explaining why each field is prioritized
RATIONALE_MAP = {
    "business_type": "Business type is essential to identify commercial segment and baseline connectivity profile.",
    "employee_count": "Employee headcount determines bandwidth capacity and minimum seat requirements.",
    "num_sites": "Number of locations determines whether single-site fibre or multi-site SD-WAN failover is required.",
    "city": "City location is required to verify network coverage and city tier eligibility.",
    "needs": "Core business needs determine which product categories (Fibre, CCTV, SIMs, POS) must be included.",
    "monthly_telecom_spend_inr": "Monthly telecom spend or telecom budget is required to evaluate cost savings and fit suitable communication plans.",
    "has_gstin": "GST status determines tax credit eligibility and unlocks enterprise B2B products (e.g. 1G fibre & leased lines).",
    "has_udyam": "Udyam registration confirms MSME status and unlocks priority enterprise benefits.",
    "max_installation_days": "Installation timeline determines eligibility for plug-and-play wireless versus physical fibre lines."
}

# Deterministic priority sequence uses REQUIRED_FIELDS directly
PRIORITY_ORDER = REQUIRED_FIELDS


class QuestionPlanner:
    @classmethod
    def detect_missing_fields(cls, schema: CustomerSchema) -> Dict[str, Any]:
        """
        Evaluates schema completeness and returns missing fields.
        """
        data = schema.to_dict()
        missing = []

        for field in REQUIRED_FIELDS:
            val = data.get(field)

            if field == 'needs':
                if not val or not isinstance(val, list) or len(val) == 0:
                    missing.append(field)
                continue

            if field == 'monthly_telecom_spend_inr':
                telecom = data.get('monthly_telecom_spend_inr')
                overall = data.get('overall_budget')
                has_telecom = isinstance(telecom, (int, float)) and telecom > 0
                has_overall = isinstance(overall, (int, float)) and overall > 0
                if not has_telecom and not has_overall:
                    missing.append('monthly_telecom_spend_inr')
                continue

            if field in ['employee_count', 'num_sites', 'max_installation_days']:
                if val is None or not isinstance(val, (int, float)) or val <= 0:
                    missing.append(field)
                continue

            if field == 'has_gstin':
                g_val = data.get('has_gstin') or data.get('gstin')
                if not g_val or (isinstance(g_val, str) and not g_val.strip()):
                    missing.append('has_gstin')
                continue

            if field == 'has_udyam':
                u_val = data.get('has_udyam') or data.get('udyam_number')
                if not u_val or (isinstance(u_val, str) and not u_val.strip()):
                    missing.append('has_udyam')
                continue

            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field)

        return {
            "missing_fields": missing,
            "schema_complete": len(missing) == 0
        }

    @classmethod
    def calculate_completion_percentage(cls, schema: CustomerSchema) -> int:
        """Calculates discovery completion progress (0% to 100%)."""
        res = cls.detect_missing_fields(schema)
        total = len(REQUIRED_FIELDS)
        collected = total - len(res["missing_fields"])
        return max(0, min(100, int((collected / total) * 100)))

    @classmethod
    def plan_next_question(cls, missing_fields: List[str]) -> Optional[Dict[str, str]]:
        """Selects the single highest-priority question to ask next."""
        if not missing_fields:
            return None

        for field in PRIORITY_ORDER:
            if field in missing_fields:
                return {
                    "field": field,
                    "canonical_question": QUESTION_MAP.get(field, f"Could you please share your {field.replace('_', ' ')}?"),
                    "reason": RATIONALE_MAP.get(field, f"{field.replace('_', ' ')} is required to qualify your business.")
                }
        return None
