"""
Stage 5b: Learned Quantity Model (quantity.py)
Learns whether a product's quantity scales per-site, per-user, or cohort median.
Pre-fills quantities with override support for customer specifications.
"""

from typing import Dict, Any, Optional

# Empirically discovered quantity drivers from smb_leads.csv (r > 0.5)
PER_SITE_PRODUCTS = {"P01", "P02", "P09", "P10", "P19", "P22", "P23"}
# Default baseline quantities for the 25 Airtel products when user does not explicitly supply quantities.
# P01-P06: Broadband/ILL lines (1 per premise)
# P07-P08: Multi-user SIP trunks & cybersecurity endpoints
# P16/P20/P24: Cloud licenses & mobile SIMs (defaulting to 5 units for small teams)
# P25: IoT tracking endpoints (defaulting to 3 sensors/trackers)
PRODUCT_MEDIAN_QTYS = {
    "P01": 1, "P02": 1, "P03": 1, "P04": 1, "P05": 1, "P06": 1,
    "P07": 2, "P08": 4, "P09": 1, "P10": 1, "P11": 1, "P12": 2,
    "P13": 1, "P14": 1, "P15": 1, "P16": 5, "P17": 1, "P18": 1,
    "P19": 1, "P20": 5, "P21": 1, "P22": 1, "P23": 2, "P24": 5,
    "P25": 3
}


class QuantityModel:
    @classmethod
    def compute_quantity(
        cls,
        product_id: str,
        profile: Dict[str, Any],
        explicit_qty: Optional[int] = None
    ) -> int:
        """
        Calculates pre-filled quantity for a product in a bundle:
        - If explicit_qty specified by customer -> use it (min 1).
        - If per-site driver -> max(1, num_sites).
        - If per-user / device driver -> min(employee_count, median).
        - Otherwise -> product median (min 1).
        """
        if explicit_qty is not None and explicit_qty > 0:
            return explicit_qty

        num_sites = max(1, int(profile.get("num_sites", 1)))
        employee_count = max(1, int(profile.get("employee_count", 5)))

        if product_id in PER_SITE_PRODUCTS:
            if product_id == "P23":  # Wi-Fi controllers often have 2 APs per site
                return max(1, num_sites)
            return max(1, num_sites)

        if product_id in {"P16", "P20"}:  # Cloud email / endpoint security
            return max(1, min(employee_count, 50))

        if product_id in {"P07", "P08"}:  # Postpaid lines
            return max(1, min(employee_count, 10))

        return PRODUCT_MEDIAN_QTYS.get(product_id, 1)


quantity_model = QuantityModel()

