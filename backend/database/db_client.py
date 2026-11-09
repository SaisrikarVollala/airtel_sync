"""
=============================================================================
DATABASE: Unified Supabase Cloud Database Client (db_client.py)
=============================================================================
Exclusive persistent database client for Airtel Sync powered by Supabase.
All data persistence, CRUD operations, transactions, and audit records
operate solely via Supabase PostgreSQL.
=============================================================================
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

try:
    from supabase import create_client, Client
    SUPABASE_CLIENT_AVAILABLE = True
except ImportError:
    SUPABASE_CLIENT_AVAILABLE = False


class DatabaseClient:
    """
    Centralized Supabase client for all persistent storage operations.
    No in-memory fallback stores, no SQLite, and no Neon.
    """

    def __init__(self):
        self.supabase_url: Optional[str] = (
            os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
        )
        self.supabase_key: Optional[str] = (
            os.getenv("SUPABASE_SECRET_KEY") or
            os.getenv("SUPABASE_ANON_KEY") or
            os.getenv("SUPABASE_PUBLISHABLE_KEY") or
            os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
        )
        self.client: Optional[Client] = None
        self.is_connected: bool = False

        self._init_supabase()

    def _init_supabase(self):
        """Initializes the official Supabase client."""
        if not SUPABASE_CLIENT_AVAILABLE:
            print("❌ Warning: supabase Python package not installed.")
            self.is_connected = False
            return

        if not self.supabase_url or not self.supabase_key:
            print("⚠️ Warning: Supabase credentials (SUPABASE_URL, SUPABASE_ANON_KEY) are missing in environment.")
            self.is_connected = False
            return

        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            self.is_connected = True
        except Exception as e:
            print(f"❌ Failed to initialize Supabase client: {e}")
            self.client = None
            self.is_connected = False

    def get_client(self) -> Client:
        """Returns active Supabase client or raises explicit error if unavailable."""
        if not self.client:
            raise RuntimeError(
                "Supabase is not configured or unavailable. Please verify SUPABASE_URL and SUPABASE_ANON_KEY in .env."
            )
        return self.client

    # =========================================================================
    # 1. PRODUCT CATALOGUE
    # =========================================================================

    def get_products(self) -> List[Dict[str, Any]]:
        """Retrieves all active catalogue products from Supabase."""
        try:
            client = self.get_client()
            res = client.table("product_catalogue").select("*").order("product_id").execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching products from Supabase: {e}")
            return []

    # =========================================================================
    # 2. OFFICIAL REGISTRIES (GSTIN & UDYAM)
    # =========================================================================

    def find_gstin(self, gstin: Optional[str]) -> Optional[Dict[str, Any]]:
        """Queries the official GSTIN registry in Supabase."""
        if not gstin:
            return None
        clean_gstin = gstin.strip().upper()
        try:
            client = self.get_client()
            res = client.table("gstin_registry").select("*").eq("gstin", clean_gstin).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            print(f"Database error querying GSTIN '{clean_gstin}' from Supabase: {e}")
            return None

    def find_udyam(self, udyam_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Queries the official MSME Udyam registry in Supabase."""
        if not udyam_number:
            return None
        clean_udyam = udyam_number.strip().upper()
        try:
            client = self.get_client()
            res = client.table("udyam_registry").select("*").eq("udyam_number", clean_udyam).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            print(f"Database error querying Udyam '{clean_udyam}' from Supabase: {e}")
            return None

    # =========================================================================
    # 3. SMB LEADS & COHORT DATA
    # =========================================================================

    def get_lead_by_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a historical enterprise lead by ID from Supabase."""
        try:
            client = self.get_client()
            res = client.table("smb_leads").select("*").eq("lead_id", lead_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Database error fetching lead {lead_id} from Supabase: {e}")
            return None

    def get_all_leads(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """Retrieves historical leads from Supabase for cohort matching and statistical models."""
        try:
            client = self.get_client()
            res = client.table("smb_leads").select("*").limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching leads from Supabase: {e}")
            return []

    # =========================================================================
    # 4. CUSTOMER ORDERS & LIFECYCLE (OMS)
    # =========================================================================

    def save_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Persists or updates customer order in Supabase orders table."""
        order_id = order.get("order_id") or f"S{uuid.uuid4().hex[:5].upper()}"
        payload = {
            "order_id": order_id,
            "session_id": order.get("session_id", "session-default"),
            "user_id": order.get("user_id"),
            "customer_name": order.get("customer_name", "Valued Enterprise Client"),
            "business_type": order.get("business_type"),
            "status": order.get("status", "Pending"),
            "current_stage_index": order.get("current_stage_index", 0),
            "bundle_code": order.get("bundle_code"),
            "bundle_name": order.get("bundle_name"),
            "monthly_cost": order.get("monthly_cost", 0.0),
            "contract_months": order.get("contract_months", 12),
            "contract_terms": order.get("contract_terms", {}),
            "milestones": order.get("milestones", []),
            "updated_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            res = client.table("orders").upsert(payload, on_conflict="order_id").execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving order {order_id} to Supabase: {e}")
            return payload

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Queries all orders from Supabase."""
        try:
            client = self.get_client()
            res = client.table("orders").select("*").order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching orders from Supabase: {e}")
            return []

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetches single order by ID from Supabase."""
        try:
            client = self.get_client()
            res = client.table("orders").select("*").eq("order_id", order_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Database error fetching order {order_id} from Supabase: {e}")
            return None

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        stage_index: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates milestone stage and status in Supabase orders table."""
        existing = self.get_order(order_id)
        if not existing:
            return None

        milestones = existing.get("milestones") or []
        idx = stage_index if stage_index is not None else existing.get("current_stage_index", 0)

        # Update milestones array
        for i, m in enumerate(milestones):
            if i <= idx:
                m["completed"] = True
            else:
                m["completed"] = False

        updates = {
            "status": new_status,
            "current_stage_index": idx,
            "milestones": milestones,
            "updated_at": datetime.now().isoformat()
        }
        client = self.get_client()
        res = client.table("orders").update(updates).eq("order_id", order_id).execute()
        return res.data[0] if res.data else None

    # =========================================================================
    # 5. ADMIN / OPERATIONS MESSAGES
    # =========================================================================

    def save_admin_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Stores admin communication message in Supabase."""
        payload = {
            "message_id": message.get("message_id") or f"MSG-{uuid.uuid4().hex[:6].upper()}",
            "session_id": message.get("session_id", "session-default"),
            "customer_name": message.get("customer_name", "Customer"),
            "message": message.get("message", ""),
            "bundle_code": message.get("bundle_code"),
            "timestamp": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            res = client.table("admin_messages").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving admin message to Supabase: {e}")
            return payload

    def get_admin_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves admin messages for a customer session from Supabase."""
        try:
            client = self.get_client()
            res = client.table("admin_messages").select("*").eq("session_id", session_id).order("timestamp").execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching admin messages from Supabase: {e}")
            return []

    # =========================================================================
    # 6. ENCRYPTED KYC & DPDP CONSENT (DPDP ACT 2023)
    # =========================================================================

    def save_kyc_record(self, record: Dict[str, Any]) -> str:
        """Stores AES-256-GCM encrypted KYC verification record in Supabase."""
        rec_id = record.get("id") or f"KYC-{uuid.uuid4().hex[:12].upper()}"
        payload = {
            "id": rec_id,
            "session_id": record.get("session_id", "session-default"),
            "applicant_id": record.get("applicant_id", "K01"),
            "doc_type": record.get("doc_type", "gstin"),
            "masked_identifier": record.get("extracted_identifier") or record.get("masked_identifier") or "",
            "encrypted_payload": record.get("ciphertext") or record.get("encrypted_payload") or "",
            "iv": record.get("iv", ""),
            "sha256_hash": record.get("sha256") or record.get("sha256_hash") or "",
            "verification_status": record.get("status") or record.get("verification_status") or "VERIFIED",
            "registry_matched": bool(record.get("registry_matched", True)),
            "tamper_detected": bool(record.get("tamper_detected", False)),
            "dpdp_consent_logged": bool(record.get("dpdp_consent_logged", True)),
            "metadata_json": json.dumps(record.get("registry_record") or {})
        }
        try:
            client = self.get_client()
            client.table("kyc_records").upsert(payload, on_conflict="id").execute()
        except Exception as e:
            print(f"Database error saving KYC record {rec_id} to Supabase: {e}")
        return rec_id

    def get_kyc_records(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries encrypted KYC verification records from Supabase."""
        try:
            client = self.get_client()
            query = client.table("kyc_records").select("*").order("created_at", desc=True)
            if session_id:
                query = query.eq("session_id", session_id)
            res = query.execute()
            records = res.data or []
            for r in records:
                if r.get("metadata_json"):
                    try:
                        r["registry_record"] = json.loads(r["metadata_json"])
                    except Exception:
                        r["registry_record"] = {}
            return records
        except Exception as e:
            print(f"Database error fetching KYC records from Supabase: {e}")
            return []

    def log_dpdp_consent(self, consent: Dict[str, Any]) -> Dict[str, Any]:
        """Stores explicit customer DPDP Act 2023 consent into Supabase."""
        payload = {
            "session_id": consent.get("session_id", "session-default"),
            "user_id": consent.get("user_id", "customer"),
            "purpose": consent.get("purpose", "KYC_VERIFICATION"),
            "language": consent.get("language", "en"),
            "consent_status": consent.get("status") or consent.get("consent_status") or "GRANTED",
            "terms_version": consent.get("terms_version", "2026.1"),
            "timestamp": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            res = client.table("dpdp_consent_logs").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error logging DPDP consent to Supabase: {e}")
            return payload

    def get_dpdp_consents(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries customer DPDP consent records from Supabase."""
        try:
            client = self.get_client()
            query = client.table("dpdp_consent_logs").select("*").order("timestamp", desc=True)
            if session_id:
                query = query.eq("session_id", session_id)
            res = query.execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching DPDP consents from Supabase: {e}")
            return []

    # =========================================================================
    # 7. AI ESCALATIONS & CUSTOMER DECISIONS
    # =========================================================================

    def save_ai_escalation(self, esc: Dict[str, Any]) -> Dict[str, Any]:
        """Stores AI escalation record in Supabase."""
        payload = {
            "escalation_id": esc.get("escalation_id") or f"ESC-{uuid.uuid4().hex[:8].upper()}",
            "session_id": esc.get("session_id", "session-default"),
            "customer_name": esc.get("customer_name", "Valued Client"),
            "priority": esc.get("priority", "HIGH"),
            "status": esc.get("status", "AWAITING_AGENT"),
            "ai_confidence_score": float(esc.get("ai_confidence_score", 0.5)),
            "confidence_band": esc.get("confidence_band", "LOW_CONFIDENCE"),
            "trigger_reason": esc.get("trigger_reason", "Ambiguous business parameters"),
            "what_ai_could_not_extract_json": json.dumps(esc.get("what_ai_could_not_extract") or []),
            "ai_discovery_summary": esc.get("ai_discovery_summary", ""),
            "recommended_action": esc.get("recommended_action", "")
        }
        try:
            client = self.get_client()
            res = client.table("ai_escalations").upsert(payload, on_conflict="escalation_id").execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving AI escalation to Supabase: {e}")
            return payload

    def get_all_ai_escalations(self) -> List[Dict[str, Any]]:
        """Retrieves all AI escalations from Supabase."""
        try:
            client = self.get_client()
            res = client.table("ai_escalations").select("*").order("created_at", desc=True).execute()
            escalations = res.data or []
            for e in escalations:
                if e.get("what_ai_could_not_extract_json"):
                    try:
                        e["what_ai_could_not_extract"] = json.loads(e["what_ai_could_not_extract_json"])
                    except Exception:
                        e["what_ai_could_not_extract"] = []
            return escalations
        except Exception as e:
            print(f"Database error fetching escalations from Supabase: {e}")
            return []

    def save_customer_decision(
        self,
        session_id: str,
        customer_name: str,
        decision_type: str,
        business_type: Optional[str] = None,
        bundle_code: Optional[str] = None,
        bundle_name: Optional[str] = None,
        monthly_cost: Optional[float] = None,
        ai_response_insights: Optional[Dict[str, Any]] = None,
        rejection_reason: Optional[str] = None,
        customer_feedback: Optional[str] = None,
        budget_offered: Optional[float] = None,
        escalation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stores customer decision (ACCEPTED / REJECTED / ESCALATED) in Supabase."""
        payload = {
            "decision_id": f"DEC-{uuid.uuid4().hex[:8].upper()}",
            "session_id": session_id,
            "customer_name": customer_name,
            "business_type": business_type,
            "decision_type": decision_type,
            "bundle_code": bundle_code,
            "bundle_name": bundle_name,
            "monthly_cost": monthly_cost,
            "ai_response_insights_json": json.dumps(ai_response_insights or {}),
            "rejection_reason": rejection_reason,
            "customer_feedback": customer_feedback,
            "budget_offered": budget_offered,
            "escalation_id": escalation_id
        }
        try:
            client = self.get_client()
            res = client.table("customer_decisions").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving customer decision to Supabase: {e}")
            return payload

    def get_customer_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries customer decisions from Supabase."""
        try:
            client = self.get_client()
            res = client.table("customer_decisions").select("*").order("created_at", desc=True).limit(limit).execute()
            decisions = res.data or []
            for d in decisions:
                if d.get("ai_response_insights_json"):
                    try:
                        d["ai_response_insights"] = json.loads(d["ai_response_insights_json"])
                    except Exception:
                        d["ai_response_insights"] = {}
            return decisions
        except Exception as e:
            print(f"Database error fetching customer decisions from Supabase: {e}")
            return []

    # =========================================================================
    # 8. USER PROFILES, CARTS, CONVERSATIONS, & NEEDS
    # =========================================================================

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetches customer discovery profile from Supabase."""
        try:
            client = self.get_client()
            res = client.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                schema_dict = {}
                if row.get("customer_schema_json"):
                    try:
                        schema_dict = json.loads(row["customer_schema_json"])
                    except Exception:
                        schema_dict = {}
                return {
                    "user_id": user_id,
                    "email": row.get("email", ""),
                    "business_name": row.get("business_name", ""),
                    "customer_schema": schema_dict
                }
            return {"user_id": user_id, "customer_schema": {}}
        except Exception as e:
            print(f"Database error fetching user profile from Supabase: {e}")
            return {"user_id": user_id, "customer_schema": {}}

    def save_user_profile(
        self,
        user_id: str,
        email: str = "",
        business_name: str = "",
        schema_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Persists customer profile and discovery schema in Supabase."""
        payload = {
            "user_id": user_id,
            "email": email,
            "business_name": business_name,
            "customer_schema_json": json.dumps(schema_dict or {}),
            "updated_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            res = client.table("user_profiles").upsert(payload, on_conflict="user_id").execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving user profile to Supabase: {e}")
            return payload

    def get_user_cart(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetches persistent cart items for user from Supabase."""
        try:
            client = self.get_client()
            res = client.table("user_carts").select("*").eq("user_id", user_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                if row.get("cart_items_json"):
                    try:
                        return json.loads(row["cart_items_json"])
                    except Exception:
                        return []
            return []
        except Exception as e:
            print(f"Database error fetching cart from Supabase: {e}")
            return []

    def save_user_cart(self, user_id: str, cart_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stores persistent cart items into Supabase."""
        payload = {
            "user_id": user_id,
            "cart_items_json": json.dumps(cart_items or []),
            "updated_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            client.table("user_carts").upsert(payload, on_conflict="user_id").execute()
        except Exception as e:
            print(f"Database error saving user cart to Supabase: {e}")
        return cart_items

    def save_user_conversation(
        self,
        user_id: str,
        session_id: str,
        sender: str,
        message: str,
        pipeline_trace: Any = None
    ):
        """Appends conversational turn into Supabase user_conversations table."""
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "sender": sender,
            "message": message,
            "pipeline_trace_json": json.dumps(pipeline_trace, default=str) if pipeline_trace else None,
            "created_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            client.table("user_conversations").insert(payload).execute()
        except Exception as e:
            print(f"Database error saving user conversation to Supabase: {e}")

    def get_user_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches conversation history for user from Supabase."""
        try:
            client = self.get_client()
            res = client.table("user_conversations").select("*").eq("user_id", user_id).order("created_at").limit(limit).execute()
            convs = res.data or []
            for c in convs:
                if c.get("pipeline_trace_json"):
                    try:
                        c["pipeline_trace"] = json.loads(c["pipeline_trace_json"])
                    except Exception:
                        c["pipeline_trace"] = None
            return convs
        except Exception as e:
            print(f"Database error fetching conversations from Supabase: {e}")
            return []

    def add_customer_need(
        self,
        user_id: str,
        need_name: str,
        product_id: Optional[str] = None,
        category: Optional[str] = None,
        source: str = "chat_ai"
    ) -> Dict[str, Any]:
        """Persists accepted customer requirement into Supabase customer_needs table."""
        payload = {
            "user_id": user_id,
            "product_id": product_id,
            "need_name": need_name,
            "category": category or "Telecom & Connectivity",
            "source": source,
            "created_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            res = client.table("customer_needs").insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Database error saving customer need to Supabase: {e}")
            return payload

    def get_customer_needs(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all accepted needs for user from Supabase."""
        try:
            client = self.get_client()
            res = client.table("customer_needs").select("*").eq("user_id", user_id).order("created_at").execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching customer needs from Supabase: {e}")
            return []

    def clear_user_all_data(self, user_id: str, session_id: Optional[str] = None) -> bool:
        """Completely purges all customer records from Supabase tables."""
        try:
            client = self.get_client()
            client.table("user_profiles").delete().eq("user_id", user_id).execute()
            client.table("user_carts").delete().eq("user_id", user_id).execute()
            client.table("user_conversations").delete().eq("user_id", user_id).execute()
            client.table("customer_needs").delete().eq("user_id", user_id).execute()
            if session_id:
                client.table("kyc_records").delete().eq("session_id", session_id).execute()
                client.table("dpdp_consent_logs").delete().eq("session_id", session_id).execute()
            return True
        except Exception as e:
            print(f"Database error purging user data from Supabase: {e}")
            return False

    # =========================================================================
    # 9. RECOMMENDATION AUDIT LOGGING
    # =========================================================================

    def save_recommendation_log(self, record: Dict[str, Any]) -> str:
        """Stores structured recommendation audit record into Supabase."""
        log_id = record.get("log_id") or f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        payload = {
            "log_id": log_id,
            "user_id": record.get("user_id"),
            "session_id": record.get("session_id"),
            "profile_snapshot": record.get("profile_snapshot", {}),
            "catalogue_version": record.get("catalogue_version", "v2"),
            "config_version": record.get("config_version", "1.0.0"),
            "cohort_info": record.get("cohort", {}),
            "candidates_count": record.get("candidates_count", 0),
            "candidates_summary": record.get("candidates_summary", []),
            "options_count": record.get("options_count", 0),
            "options_shown": record.get("options_shown", []),
            "single_option_reason": record.get("single_option_reason"),
            "created_at": datetime.now().isoformat()
        }
        try:
            client = self.get_client()
            client.table("recommendation_logs").insert(payload).execute()
        except Exception as e:
            print(f"Database error saving recommendation log to Supabase: {e}")
        return log_id

    def get_recommendation_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries recommendation audit records from Supabase."""
        try:
            client = self.get_client()
            res = client.table("recommendation_logs").select("*").order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching recommendation logs from Supabase: {e}")
            return []

    # =========================================================================
    # 10. STATISTICS & TABLE EXPLORER
    # =========================================================================

    @property
    def leads(self) -> Dict[str, Dict[str, Any]]:
        """Dynamic access to leads from Supabase."""
        rows = self.get_all_leads()
        return {r.get("lead_id", str(i)): r for i, r in enumerate(rows)}

    @property
    def bundle_statistics(self) -> List[Dict[str, Any]]:
        """Dynamic access to bundle statistics from Supabase."""
        return self.get_bundle_statistics()

    @property
    def product_statistics(self) -> List[Dict[str, Any]]:
        """Dynamic access to product statistics from Supabase."""
        return self.get_product_statistics()

    @property
    def city_tiers(self) -> Dict[str, Dict[str, Any]]:
        """Dynamic access to city tiers from Supabase."""
        rows = self.get_table_rows("city_tier_mapping")
        return {r.get("city", ""): r for r in rows}

    def get_bundle_statistics(self) -> List[Dict[str, Any]]:
        """Fetches bundle statistics from Supabase."""
        try:
            client = self.get_client()
            res = client.table("bundle_statistics").select("*").execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching bundle stats from Supabase: {e}")
            return []

    def get_product_statistics(self) -> List[Dict[str, Any]]:
        """Fetches product statistics from Supabase."""
        try:
            client = self.get_client()
            res = client.table("product_statistics").select("*").execute()
            return res.data or []
        except Exception as e:
            print(f"Database error fetching product stats from Supabase: {e}")
            return []

    def get_table_rows(self, table_name: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Queries rows directly from any table in Supabase for the visual database explorer."""
        try:
            client = self.get_client()
            res = client.table(table_name).select("*").limit(limit).execute()
            return res.data or []
        except Exception as e:
            print(f"Database error querying table '{table_name}' from Supabase: {e}")
            return []

    def get_status(self) -> Dict[str, Any]:
        """Queries live Supabase connection status and table row counts."""
        if not self.is_connected or not self.client:
            return {
                "connected": False,
                "engine": "Supabase Cloud PostgreSQL (Exclusive Database)",
                "error": "Supabase credentials missing or client uninitialized."
            }

        counts = {}
        target_tables = [
            "product_catalogue", "gstin_registry", "udyam_registry", "smb_leads",
            "orders", "ai_escalations", "customer_decisions", "kyc_records",
            "dpdp_consent_logs", "user_profiles", "user_conversations"
        ]
        for t in target_tables:
            try:
                # PostgREST head request count
                res = self.client.table(t).select("*", count="exact").limit(0).execute()
                counts[t] = res.count if res.count is not None else 0
            except Exception:
                counts[t] = 0

        return {
            "connected": True,
            "engine": "Supabase Cloud PostgreSQL",
            "provider": "Supabase",
            "endpoint": self.supabase_url,
            "auth_provider": "Supabase Auth",
            "counts": counts
        }


db_client = DatabaseClient()
