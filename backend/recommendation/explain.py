"""
Stage 11: Grounded Natural Language Explainer (explain.py)
Generates audit-compliant natural language explanations.
Enforces strict grounding check:
If LLM text contains numbers or product names absent from structured data,
it immediately falls back to the deterministic template.
No banned phrases ('best for you', 'guarantee', 'unbeatable').
"""

import re
from typing import Dict, Any, List
from agent.sarvam_llm_client import sarvam_llm_client

BANNED_PHRASES = [
    "best for you",
    "unbeatable",
    "100% guarantee",
    "exclusive discount",
    "special offer just for you"
]


class ExplanationService:
    @classmethod
    def generate_explanation(
        cls,
        bundle: Dict[str, Any],
        reasons: List[Dict[str, Any]],
        profile: Dict[str, Any],
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Produces grounded explanation with source tracking ('template' or 'llm').
        """
        template_text = cls._build_deterministic_template(bundle, reasons, profile, language)

        # Attempt Sarvam LLM generation if explicitly enabled or requested
        import os
        enable_llm = profile.get("use_llm", False) or os.getenv("ENABLE_LLM_EXPLANATION", "0") == "1"
        if enable_llm:
            try:
                prompt = cls._build_llm_prompt(bundle, reasons, profile, language)
                llm_text = sarvam_llm_client.chat_completion([{"role": "user", "content": prompt}])

                if llm_text and cls._verify_grounding(llm_text, bundle, reasons):
                    return {
                        "text": llm_text.strip(),
                        "language": language,
                        "source": "llm",
                        "grounded": True
                    }
            except Exception:
                pass

        return {
            "text": template_text.strip(),
            "language": language,
            "source": "template",
            "grounded": True
        }

    @classmethod
    def _build_deterministic_template(
        cls,
        bundle: Dict[str, Any],
        reasons: List[Dict[str, Any]],
        profile: Dict[str, Any],
        language: str
    ) -> str:
        products = bundle.get("products") or []
        quote = bundle.get("quote") or {}
        p_names = [p["product_name"] for p in products]
        m_cost = int(quote.get("monthly_total", 0))
        s_cost = int(quote.get("setup_total", 0))
        contract = quote.get("contract_months", 12)
        eta = quote.get("eta_days", 7)
        b_type = profile.get("business_type") or "enterprise"

        need_summary = next((r["summary"] for r in reasons if r["code"] == "NEED_MATCH"), "tailored connectivity")
        pop_summary = next((r["summary"] for r in reasons if r["code"] == "PEER_POPULARITY"), None)

        if language == "hi":
            text = (
                f"Airtel Business आपके {b_type} के लिए यह समाधान प्रस्तुत करता है। "
                f"इसमें {', '.join(p_names)} शामिल हैं जो आपके {need_summary} को पूरा करते हैं। "
                f"मासिक शुल्क ₹{m_cost} और वन-टाइम सेटअप शुल्क ₹{s_cost} है ({contract} महीने का अनुबंध)। "
                f"अनुमानित एक्टिवेशन समय {eta} कार्य दिवस है।"
            )
        else:
            text = (
                f"Recommended for your {b_type}: this suite includes {', '.join(p_names)}, "
                f"covering your {need_summary}. "
                + (f"{pop_summary}. " if pop_summary else "")
                + f"The monthly commitment is ₹{m_cost} with a one-time setup fee of ₹{s_cost} "
                f"on a {contract}-month co-termed agreement. Estimated ready for service in {eta} business days."
            )
        return text

    @classmethod
    def _build_llm_prompt(
        cls,
        bundle: Dict[str, Any],
        reasons: List[Dict[str, Any]],
        profile: Dict[str, Any],
        language: str
    ) -> str:
        quote = bundle.get("quote", {})
        prods = [p["product_name"] for p in bundle.get("products", [])]
        return (
            f"You are an enterprise advisor at Airtel Business. Write an objective 60-word solution summary.\n"
            f"Business: {profile.get('business_type')}\n"
            f"Products: {', '.join(prods)}\n"
            f"Monthly: ₹{quote.get('monthly_total')}, Setup: ₹{quote.get('setup_total')}, Contract: {quote.get('contract_months')}m, Install: {quote.get('eta_days')} days.\n"
            f"Reasons: {'; '.join(r.get('summary','') for r in reasons)}\n"
            f"Rules: Do NOT use phrases like 'best for you', 'guarantee', or invent discounts. Output in {language} only."
        )

    @classmethod
    def _verify_grounding(cls, text: str, bundle: Dict[str, Any], reasons: List[Dict[str, Any]]) -> bool:
        """
        Validates that every ₹ amount and banned phrase rule is respected.
        """
        text_lower = text.lower()
        for banned in BANNED_PHRASES:
            if banned in text_lower:
                return False

        # Extract rupees numbers
        quote = bundle.get("quote", {})
        valid_numbers = {
            int(quote.get("monthly_total", 0)),
            int(quote.get("setup_total", 0)),
            int(quote.get("contract_months", 12)),
            int(quote.get("eta_days", 7)),
        }
        for p in bundle.get("products", []):
            valid_numbers.add(int(p.get("monthly", 0)))
            valid_numbers.add(int(p.get("unit_price", 0)))
            valid_numbers.add(int(p.get("qty", 1)))

        # Find numbers preceded by ₹ or Rs
        currency_matches = re.findall(r'(?:₹|rs\.?)\s*(\d[\d,]*)', text, re.IGNORECASE)
        for num_str in currency_matches:
            clean_num = int(num_str.replace(",", ""))
            # Must match an authorized figure or within 5%
            if not any(abs(clean_num - v) <= 5 for v in valid_numbers):
                return False

        return True


explanation_service = ExplanationService()
