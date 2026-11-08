"""
=============================================================================
DATA PREPROCESSING: City-to-Tier Resolver (city_tier_mapping.py)
=============================================================================
Maps Indian cities to telecom network infrastructure tiers (Tier 1 vs Tier 2)
and states, based on precomputed city mappings.
=============================================================================
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "city_tier_mapping.json"


class CityTierService:
    def __init__(self):
        self.cities: Dict[str, Dict[str, Any]] = {}
        self.load_mapping()

    def load_mapping(self):
        """Loads city tier mappings from data/city_tier_mapping.json."""
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                    for item in entries:
                        name = item.get("city", "").strip().lower()
                        if name:
                            self.cities[name] = item
                        # Register aliases (e.g. Bangalore -> Bengaluru, Bombay -> Mumbai)
                        for alias in item.get("aliases", []):
                            a_name = alias.strip().lower()
                            if a_name and a_name not in self.cities:
                                self.cities[a_name] = item
            except Exception:
                pass

    def lookup(self, city_name: Optional[str]) -> Dict[str, Any]:
        """
        High-Accuracy City-to-Tier Resolver:
        1. Fast exact & alias dictionary match (<0.01ms)
        2. RapidFuzz Levenshtein string distance match (catches typos, phonetics, missing letters)
        3. Fallback to Tier 2 (National urban median)
        """
        if not city_name or not isinstance(city_name, str):
            return {"city": None, "city_tier": 2, "state": None, "matched": False, "match_type": "none"}

        cleaned = city_name.strip().lower()

        # Step 1: Direct match in authoritative 300-city registry
        if cleaned in self.cities:
            record = self.cities[cleaned]
            t_val = record.get("city_tier") if record.get("city_tier") is not None else record.get("tier", 2)
            return {
                "city": record.get("city"),
                "city_tier": int(t_val),
                "state": record.get("state"),
                "matched": True,
                "match_type": "exact",
                "confidence": 1.0
            }

        # Step 2: High-accuracy Fuzzy string matching for typos (e.g., 'Ahemadabad', 'Kollkata', 'Gurgon')
        if RAPIDFUZZ_AVAILABLE and self.cities:
            all_city_keys = list(self.cities.keys())
            best_match = process.extractOne(
                cleaned,
                all_city_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=75.0
            )
            if best_match:
                matched_key, score, _ = best_match
                record = self.cities[matched_key]
                t_val = record.get("city_tier") if record.get("city_tier") is not None else record.get("tier", 2)
                return {
                    "city": record.get("city"),
                    "city_tier": int(t_val),
                    "state": record.get("state"),
                    "matched": True,
                    "match_type": "fuzzy",
                    "similarity_score": round(score, 1),
                    "confidence": round(score / 100.0, 2)
                }

        # Step 3: Default fallback for unmapped towns in India
        return {"city": city_name, "city_tier": 2, "state": None, "matched": False, "match_type": "fallback", "confidence": 0.5}


city_tier_service = CityTierService()
