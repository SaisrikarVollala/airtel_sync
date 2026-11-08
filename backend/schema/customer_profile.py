"""
=============================================================================
SCHEMA: Customer Profile (customer_profile.py)
=============================================================================
Pydantic v2 schema representing the comprehensive 23-field customer profile
collected during Phase 1 Conversational Discovery for Airtel Business.

Includes:
- Strict field typing
- Automatic numeric coercion (handles strings with commas like "10,000")
- Safe merging (new turns don't overwrite existing valid data with nulls)
=============================================================================
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class CustomerSchema(BaseModel):
    # Identifiers
    lead_id: Optional[str] = None
    business_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None

    # Classification & Location
    business_type: Optional[str] = None
    segment: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    city_tier: Optional[int] = None
    preferred_language: Optional[str] = None

    # Scale & Infrastructure
    employee_count: Optional[int] = None
    num_sites: Optional[int] = None
    annual_turnover_band: Optional[str] = None
    current_internet: Optional[str] = None
    current_provider: Optional[str] = None

    # Commercials & Requirements
    monthly_telecom_spend_inr: Optional[float] = None
    overall_budget: Optional[float] = None
    needs: List[str] = Field(default_factory=list)

    # Compliance & Identifiers
    has_gstin: Optional[str] = None  # "Y" or "N"
    gstin: Optional[str] = None
    has_udyam: Optional[str] = None  # "Y" or "N"
    udyam_number: Optional[str] = None
    max_installation_days: Optional[int] = None

    # -------------------------------------------------------------------------
    # Numeric Coercion Validators
    # -------------------------------------------------------------------------
    @field_validator("employee_count", "num_sites", "city_tier", "max_installation_days", mode="before")
    @classmethod
    def coerce_to_int(cls, value: Any) -> Optional[int]:
        """Converts strings, floats, or commas to clean integers."""
        if value is None or value == "":
            return None
        try:
            cleaned = str(value).replace(",", "").strip()
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None

    @field_validator("monthly_telecom_spend_inr", "overall_budget", mode="before")
    @classmethod
    def coerce_to_float(cls, value: Any) -> Optional[float]:
        """Converts currency strings or numbers to clean floats."""
        if value is None or value == "":
            return None
        try:
            cleaned = str(value).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @field_validator("needs", mode="before")
    @classmethod
    def coerce_needs_list(cls, value: Any) -> List[str]:
        """Ensures needs is always a clean list of strings."""
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if item]
        if isinstance(value, str):
            return [item.strip() for item in value.split(";") if item.strip()]
        return []

    # -------------------------------------------------------------------------
    # Safe Merging Helper
    # -------------------------------------------------------------------------
    def merge_updates(self, updates: Dict[str, Any]) -> "CustomerSchema":
        """
        Safely applies newly extracted facts without overwriting previously
        collected valid information with empty or null values.
        """
        data = self.model_dump()
        for key, val in updates.items():
            if val is not None and val != "":
                if key == "needs":
                    existing = set(data.get("needs") or [])
                    new_items = val if isinstance(val, list) else [val]
                    existing.update([n for n in new_items if n])
                    data["needs"] = list(existing)
                else:
                    data[key] = val
        return CustomerSchema(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Returns standard dictionary representation."""
        return self.model_dump()
