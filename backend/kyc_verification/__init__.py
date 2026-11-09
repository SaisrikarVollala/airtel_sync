"""
Smart Digital KYC Verification & DPDP-Compliant Vault Package
"""

from .secure_vault import secure_vault, SecureVault
from .smart_kyc_verifier import smart_kyc_verifier, find_applicant_files, SmartKYCVerifier
from .smart_kyc_service import smart_kyc_service, SmartKYCService
from .s3_storage import secure_s3_service, SecureS3Service

__all__ = [
    "secure_vault",
    "SecureVault",
    "smart_kyc_verifier",
    "find_applicant_files",
    "SmartKYCVerifier",
    "smart_kyc_service",
    "SmartKYCService",
    "secure_s3_service",
    "SecureS3Service",
]

