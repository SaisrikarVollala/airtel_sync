"""
=============================================================================
SMART KYC: Secure Vault & DPDP Compliance Service (secure_vault.py)
=============================================================================
Provides DPDP Act 2023 compliant PII masking, AES-256-GCM document encryption,
and audit logging.
=============================================================================
"""

import os
import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 256-bit AES master key derived or generated
VAULT_KEY = os.getenv("VAULT_AES_KEY")
if VAULT_KEY:
    try:
        AES_KEY = bytes.fromhex(VAULT_KEY)
    except Exception:
        AES_KEY = hashlib.sha256(VAULT_KEY.encode()).digest()
else:
    # Deterministic default key for local/demo runs
    AES_KEY = hashlib.sha256(b"airtel-sync-enterprise-vault-secret-2026").digest()


class SecureVault:
    def __init__(self):
        self.aesgcm = AESGCM(AES_KEY)

    def mask_pii(self, val: str, field_type: str = "generic") -> str:
        """
        DPDP Act 2023 compliant PII masking.
        - GSTIN (15 chars): Shows first 2 (state) and last 3 chars, masks middle (e.g., 29*****1Z5)
        - Udyam (19 chars): Shows prefix & last 2 chars (e.g., UDYAM-**-**-*****45)
        - Aadhaar (12 digits): Shows last 4 digits (e.g., ********1234)
        - PAN (10 chars): Shows first 2 and last 2 chars (e.g., AB*****34F)
        """
        if not val or not isinstance(val, str):
            return ""
        s = val.strip()
        t = field_type.lower()

        if t == "gstin" and len(s) == 15:
            return f"{s[:2]}*****{s[-3:]}"
        elif "udyam" in t:
            parts = s.split("-")
            if len(parts) >= 4:
                return f"{parts[0]}-**-**-*****{parts[-1][-2:]}"
            return f"{s[:6]}*****{s[-2:]}" if len(s) > 8 else "****"
        elif "aadhaar" in t or "uid" in t:
            clean = s.replace(" ", "").replace("-", "")
            return f"********{clean[-4:]}" if len(clean) >= 4 else "********"
        elif "pan" in t and len(s) == 10:
            return f"{s[:2]}*****{s[-2:]}"
        elif "phone" in t or "mobile" in t:
            return f"******{s[-4:]}" if len(s) >= 4 else "******"
        elif "email" in t and "@" in s:
            name, dom = s.split("@", 1)
            return f"{name[:2]}***@{dom}"

        # Generic masking
        if len(s) <= 4:
            return "****"
        return f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"

    def encrypt_document_bytes(self, data: bytes) -> Dict[str, str]:
        """
        Encrypts raw bytes using AES-256-GCM with a unique 96-bit IV.
        Returns ciphertext (hex), IV (hex), and SHA-256 hash.
        """
        if not data:
            return {"ciphertext": "", "iv": "", "sha256": ""}
        iv = os.urandom(12)  # 96-bit IV recommended for GCM
        ciphertext = self.aesgcm.encrypt(iv, data, None)
        sha256 = hashlib.sha256(data).hexdigest()
        return {
            "ciphertext": ciphertext.hex(),
            "iv": iv.hex(),
            "sha256": sha256
        }

    def decrypt_document_bytes(self, ciphertext_hex: str, iv_hex: str) -> bytes:
        """Decrypts AES-256-GCM ciphertext."""
        iv = bytes.fromhex(iv_hex)
        ciphertext = bytes.fromhex(ciphertext_hex)
        return self.aesgcm.decrypt(iv, ciphertext, None)

    def log_consent(
        self,
        session_id: str,
        user_id: str,
        purpose: str = "KYC_VERIFICATION",
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Records customer explicit consent for DPDP Act 2023 compliance.
        Persists into Supabase via db_client.
        """
        from database.db_client import db_client
        record = {
            "session_id": session_id,
            "user_id": user_id,
            "purpose": purpose,
            "language": language,
            "status": "GRANTED",
            "timestamp": datetime.now().isoformat(),
            "terms_version": "2026.1"
        }
        return db_client.log_dpdp_consent(record)


secure_vault = SecureVault()

