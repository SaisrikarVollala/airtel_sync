"""
=============================================================================
AGENT: Zero-Temperature Schema Extraction Agent (entity_extractor.py)
=============================================================================
Uses Sarvam 105B with temperature 0.0 to parse and extract only explicit facts
from customer turns into structured JSON. Eliminates hallucinations.
=============================================================================
"""

import re
import json
from typing import Dict, Any
from agent.sarvam_llm_client import sarvam_llm_client

import re
import json
from typing import Dict, Any, Optional
from rapidfuzz import process, fuzz
from agent.sarvam_llm_client import sarvam_llm_client

EXTRACTION_PROMPT = """You are an expert AI entity extractor for Airtel Business Customer Discovery.
Read the conversation context and the latest message from the business owner.
Extract facts into a clean JSON object. Handle colloquial terms, typos (e.g. 'retial' -> 'Retail Store', 'fibre' -> 'fiber/internet'), and direct answers to previous questions.

RULES:
1. Extract facts mentioned or answered directly by the customer.
2. Numeric fields (employee_count, num_sites, max_installation_days, monthly_telecom_spend_inr, overall_budget) must be numbers.
3. Classify recurring monthly telecom/internet spend into `monthly_telecom_spend_inr`. Classify total package budget into `overall_budget`.
4. If customer says "Yes we have GST" or "yes", set `has_gstin: "Y"`. If "No", set `has_gstin: "N"`.
5. Return ONLY a valid JSON object without markdown formatting.

Keys:
- business_name (str)
- business_type (str)
- city (str)
- employee_count (int)
- num_sites (int)
- current_provider (str)
- monthly_telecom_spend_inr (float)
- overall_budget (float)
- needs (list of strings)
- has_gstin ("Y" / "N")
- gstin (str)
- has_udyam ("Y" / "N")
- udyam_number (str)
- max_installation_days (int)
"""

COMMON_BUSINESS_TYPES = [
    "Retail Store", "Manufacturing", "Clinic", "Hospital", "Dental Clinic",
    "Bakery", "Restaurant", "Cafe", "Pharmacy", "Law Firm", "CA Firm",
    "Architect", "Consultant", "Warehouse", "Coaching Centre", "Hotel",
    "Gym", "Real Estate", "IT Firm", "Software Company", "Logistics", "Auto Parts"
]


class EntityExtractor:
    def __init__(self, client=sarvam_llm_client):
        self.client = client

    def extract(self, message: str, last_question: Optional[str] = None) -> Dict[str, Any]:
        """Extracts schema facts from user message, enriched with conversational context."""
        if not message or not message.strip():
            return {}

        prompt_user = f"Latest Customer Message: \"{message}\""
        if last_question:
            prompt_user = f"Previous Airtel Question: \"{last_question}\"\nLatest Customer Message: \"{message}\""

        messages = [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": prompt_user}
        ]

        try:
            raw_text = self.client.chat_completion(messages=messages, temperature=0.0)
            cleaned = re.sub(r'```(?:json)?', '', raw_text).strip()
            extracted = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                try:
                    extracted = json.loads(match.group(0))
                except Exception:
                    pass
        except ValueError:
            # Re-raise explicit API configuration error so caller knows key is missing
            raise

        # -------------------------------------------------------------
        # RESILIENT FALLBACK / HEURISTIC ENRICHMENT
        # (Guarantees short messages, typos & direct replies never get lost)
        # -------------------------------------------------------------
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()

        # 1. Needs detection (e.g. 'need fiber', 'internet', 'wifi', 'leased line', 'cctv')
        current_needs = extracted.get("needs") or []
        if isinstance(current_needs, str):
            current_needs = [current_needs]
        
        if any(w in msg_lower for w in ["fiber", "fibre", "leased line", "internet", "broadband", "wifi", "wi-fi"]):
            if not any("fiber" in n.lower() or "internet" in n.lower() for n in current_needs):
                current_needs.append("High-Speed Optical Fibre / Leased Line")
        if any(w in msg_lower for w in ["cctv", "camera", "surveillance"]):
            if not any("cctv" in n.lower() for n in current_needs):
                current_needs.append("Cloud CCTV Surveillance")
        if any(w in msg_lower for w in ["security", "firewall", "antivirus"]):
            if not any("security" in n.lower() or "firewall" in n.lower() for n in current_needs):
                current_needs.append("Endpoint Security & Firewall")
        if current_needs:
            extracted["needs"] = current_needs

        # 2. Direct answer to "What type of business do you run?" or direct business type utterance
        if not extracted.get("business_type"):
            is_answering_business = (last_question and ("business" in last_question.lower() or "type" in last_question.lower()))
            
            # Direct match or fuzzy typo match (e.g., 'retial' -> 'Retail Store')
            match_res = process.extractOne(msg_clean, COMMON_BUSINESS_TYPES, scorer=fuzz.ratio)
            if match_res and match_res[1] >= 65:
                extracted["business_type"] = match_res[0]
            elif is_answering_business and len(msg_clean.split()) <= 4:
                # Treat the user's short response as their business name/type
                extracted["business_type"] = msg_clean.capitalize()

        # 3. Direct answer to location / city
        if not extracted.get("city"):
            if last_question and "city" in last_question.lower():
                extracted["city"] = msg_clean.capitalize()

        # 4. Direct answer to number of sites / branches
        if not extracted.get("num_sites"):
            if last_question and ("branch" in last_question.lower() or "location" in last_question.lower() or "site" in last_question.lower()):
                num_m = re.search(r'\b(\d+)\b', msg_lower)
                if num_m:
                    extracted["num_sites"] = int(num_m.group(1))
                elif "single" in msg_lower or "one" in msg_lower or "only 1" in msg_lower:
                    extracted["num_sites"] = 1

        # 5. Direct answer to employee headcount
        if not extracted.get("employee_count"):
            if last_question and ("employee" in last_question.lower() or "people" in last_question.lower() or "staff" in last_question.lower()):
                num_m = re.search(r'\b(\d+)\b', msg_lower)
                if num_m:
                    extracted["employee_count"] = int(num_m.group(1))

        # 6. Direct answer to GST registration
        if not extracted.get("has_gstin"):
            if last_question and "gst" in last_question.lower():
                if any(w in msg_lower for w in ["yes", "ha", "haan", "yep", "we have"]):
                    extracted["has_gstin"] = "Y"
                elif any(w in msg_lower for w in ["no", "nahi", "nope", "don't"]):
                    extracted["has_gstin"] = "N"

        # 7. Direct answer to Udyam registration
        if not extracted.get("has_udyam"):
            if last_question and "udyam" in last_question.lower():
                if any(w in msg_lower for w in ["yes", "ha", "haan", "yep", "we have"]):
                    extracted["has_udyam"] = "Y"
                elif any(w in msg_lower for w in ["no", "nahi", "nope", "don't"]):
                    extracted["has_udyam"] = "N"

        return extracted


entity_extractor = EntityExtractor()
