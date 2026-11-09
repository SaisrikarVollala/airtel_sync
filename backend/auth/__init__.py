"""
Authentication package for Airtel Sync using Supabase Auth.
"""

from .supabase_auth import (
    get_current_user,
    get_optional_user,
    require_admin,
    supabase_auth_service,
)

__all__ = [
    "get_current_user",
    "get_optional_user",
    "require_admin",
    "supabase_auth_service",
]

