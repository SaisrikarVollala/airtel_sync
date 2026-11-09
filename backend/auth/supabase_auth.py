"""
=============================================================================
AUTHENTICATION: Supabase Auth Service & JWT Verification (supabase_auth.py)
=============================================================================
Validates Supabase-issued access tokens and manages user authentication
strictly through Supabase Auth. No local secondary JWT issuance.
=============================================================================
"""

import os
import jwt
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Admin emails configured for administrative authorization
ADMIN_EMAILS = [
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "admin@airtel.com,ops@airtel.com,noc@airtel.com").split(",") if e.strip()
]

security = HTTPBearer(auto_error=False)


class SupabaseAuthService:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            self.client: Optional[Client] = None
        else:
            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def _get_client(self) -> Client:
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase credentials (SUPABASE_URL, SUPABASE_ANON_KEY) are not configured."
            )
        return self.client

    def sign_up(self, email: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Registers a new user in Supabase Auth."""
        client = self._get_client()
        try:
            credentials = {
                "email": email,
                "password": password,
            }
            if metadata:
                credentials["options"] = {"data": metadata}
            res = client.auth.sign_up(credentials)
            user_data = {
                "id": res.user.id if res.user else None,
                "email": res.user.email if res.user else email,
                "metadata": res.user.user_metadata if res.user else metadata,
            }
            token = res.session.access_token if res.session else None
            return {
                "success": True,
                "user": user_data,
                "token": token,
                "message": "User registered successfully." if token else "Registration successful. Please verify your email if required."
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supabase registration error: {str(e)}"
            )

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticates user against Supabase Auth and returns Supabase-issued session & tokens."""
        client = self._get_client()
        try:
            res = client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if not res.session or not res.session.access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed: No access token issued by Supabase."
                )

            user = res.user
            user_meta = user.user_metadata or {}
            app_meta = user.app_metadata or {}
            
            # Resolve role from Supabase metadata or admin list
            is_admin = (
                user.email.lower() in ADMIN_EMAILS or
                app_meta.get("role") == "admin" or
                user_meta.get("role") == "admin"
            )
            role = "admin" if is_admin else "user"

            return {
                "success": True,
                "token": res.session.access_token,
                "refresh_token": res.session.refresh_token,
                "expires_at": res.session.expires_at,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user_meta.get("name") or ("Airtel Administrator" if is_admin else "Airtel Customer"),
                    "role": role,
                    "app_metadata": app_meta,
                    "user_metadata": user_meta
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            err_msg = str(e)
            if "Email not confirmed" in err_msg:
                # If Supabase email confirmation is pending
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email confirmation required by Supabase Auth before sign in."
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Supabase authentication failed: {err_msg}"
            )

    def sign_out(self, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Signs out current session from Supabase Auth."""
        client = self._get_client()
        try:
            client.auth.sign_out()
            return {"success": True, "message": "Successfully logged out from Supabase Auth."}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supabase sign-out error: {str(e)}"
            )

    def reset_password(self, email: str) -> Dict[str, Any]:
        """Triggers password reset email via Supabase Auth."""
        client = self._get_client()
        try:
            client.auth.reset_password_for_email(email)
            return {"success": True, "message": "Password reset instructions sent via Supabase."}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password reset error: {str(e)}"
            )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Validates Supabase-issued access token.
        First tries Supabase Auth server validation via client.auth.get_user(token).
        Also verifies JWT claims with SUPABASE_JWT_SECRET if available.
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization token."
            )

        # 1. Try Supabase Auth API verification
        if self.client:
            try:
                user_res = self.client.auth.get_user(token)
                if user_res and user_res.user:
                    u = user_res.user
                    user_meta = u.user_metadata or {}
                    app_meta = u.app_metadata or {}
                    is_admin = (
                        (u.email and u.email.lower() in ADMIN_EMAILS) or
                        app_meta.get("role") == "admin" or
                        user_meta.get("role") == "admin"
                    )
                    return {
                        "id": u.id,
                        "sub": u.id,
                        "email": u.email,
                        "role": "admin" if is_admin else (app_meta.get("role") or "authenticated"),
                        "app_metadata": app_meta,
                        "user_metadata": user_meta
                    }
            except Exception:
                pass

        # 2. Try Supabase JWT Secret verification
        if SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
                )
                user_id = payload.get("sub") or payload.get("id")
                email = payload.get("email", "")
                app_meta = payload.get("app_metadata", {})
                user_meta = payload.get("user_metadata", {})
                is_admin = (
                    (email and email.lower() in ADMIN_EMAILS) or
                    app_meta.get("role") == "admin" or
                    user_meta.get("role") == "admin" or
                    payload.get("role") == "admin"
                )
                return {
                    "id": user_id,
                    "sub": user_id,
                    "email": email,
                    "role": "admin" if is_admin else "authenticated",
                    "app_metadata": app_meta,
                    "user_metadata": user_meta
                }
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Supabase access token has expired."
                )
            except jwt.PyJWTError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid Supabase JWT token: {str(e)}"
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate Supabase access token."
        )


supabase_auth_service = SupabaseAuthService()


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Dict[str, Any]:
    """FastAPI Dependency: Requires valid Supabase Auth access token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required."
        )
    return supabase_auth_service.verify_token(credentials.credentials)


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[Dict[str, Any]]:
    """FastAPI Dependency: Returns authenticated user or None for guest sessions."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return supabase_auth_service.verify_token(credentials.credentials)
    except HTTPException:
        # Invalid credentials provided
        return None


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """FastAPI Dependency: Requires verified Supabase Auth administrator role."""
    role = user.get("role")
    app_meta = user.get("app_metadata", {})
    user_meta = user.get("user_metadata", {})
    email = (user.get("email") or "").lower()

    is_admin = (
        role == "admin" or
        app_meta.get("role") == "admin" or
        user_meta.get("role") == "admin" or
        email in ADMIN_EMAILS
    )

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required. User is not an authorized administrator."
        )
    return user

