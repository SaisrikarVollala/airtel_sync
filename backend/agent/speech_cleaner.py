"""
=============================================================================
AGENT: Speech Cleaner & Identifier Protector (speech_cleaner.py)
=============================================================================
Sanitizes raw speech transcripts produced by Sarvam Speech-to-Text:
- Converts spoken punctuation ("forward slash", "dash", "hyphen") to natural language
- Strictly protects 15-character GSTINs and 19-character Udyam registration IDs
  so regex shields prevent identifier corruption.
=============================================================================
"""

import re


class SpeechCleaner:
    # 15-character official Indian GSTIN format
    GSTIN_REGEX = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b', re.IGNORECASE)

    # Official MSME Udyam registration format (e.g. UDYAM-MH-01-0012345 or UDYAM-00-1234567)
    UDYAM_REGEX = re.compile(r'\bUDYAM-[A-Z0-9-]+\b', re.IGNORECASE)

    @classmethod
    def clean(cls, text: str) -> str:
        """
        Cleans transcripts into natural spoken text without altering IDs.
        """
        if not text or not isinstance(text, str):
            return ""

        # Step 1: Shield GSTIN & Udyam identifiers
        udyam_matches = cls.UDYAM_REGEX.findall(text)
        gstin_matches = cls.GSTIN_REGEX.findall(text)

        protected_tokens = {}
        for i, match in enumerate(udyam_matches):
            token = f"TOKENXUDYAMX{i}X"
            protected_tokens[token] = match
            text = text.replace(match, token)

        for i, match in enumerate(gstin_matches):
            token = f"TOKENXGSTINX{i}X"
            protected_tokens[token] = match
            text = text.replace(match, token)

        # Step 2: Replace spoken words
        text = re.sub(r'\b(forward\s+slash|slash|backslash)\b', ' and ', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(hyphen|dash)\b', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\bunderscore\b', ' ', text, flags=re.IGNORECASE)

        # Step 3: Replace literal slashes and hyphens between words
        text = re.sub(r'([A-Za-z0-9])\s*/\s*([A-Za-z0-9])', r'\1 and \2', text)
        text = re.sub(r'([A-Za-z0-9])\s*[-_]\s*([A-Za-z0-9])', r'\1 \2', text)

        # Step 4: Common Indic spoken abbreviations
        text = re.sub(r'\b(lakh|lacs)\b', 'lakh', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(cr|crore)\b', 'crore', text, flags=re.IGNORECASE)

        # Step 5: Restore shielded tokens
        for token, original in protected_tokens.items():
            text = text.replace(token, original)

        return re.sub(r'\s+', ' ', text).strip()
