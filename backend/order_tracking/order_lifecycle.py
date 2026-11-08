"""
=============================================================================
ORDER TRACKING: Order Lifecycle & Sales Operations (order_lifecycle.py)
=============================================================================
Manages the post-discovery commercial journey:
- Persistent SQL Database storage via db_client
- Dynamic SLA Contract Generation (99.5% for retail vs 99.9% for multi-branch)
- 4-Milestone Order Tracker:
  1. Pending
  2. Order Confirm (KYC Approved)
  3. Packed and Processed (Hardware & Splicing Dispatched)
  4. Delivered & Activated
- Admin / Operations message dispatch persisted to SQL database
=============================================================================
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.db_client import db_client


class OrderLifecycleService:
    def __init__(self):
        self.rejections: List[Dict[str, Any]] = []
        self._seed_initial_orders()

    def _seed_initial_orders(self):
        """Seeds default historical order S00060 into SQL database if not present."""
        if not db_client.get_order("S00060"):
            s60_order = {
                "order_id": "S00060",
                "session_id": "session_s60",
                "customer_name": "Balaji Dental Care LLP",
                "business_type": "Healthcare & Dental Clinic",
                "status": "Order Confirm",
                "current_stage_index": 1,
                "bundle_code": "BUNDLE-PRIMARY",
                "bundle_name": "Micro Retail & Services Growth Suite",
                "monthly_cost": 2499.0,
                "contract_months": 12,
                "contract_terms": {
                    "sla_uptime": "99.5% Standard Commercial Uptime SLA",
                    "mttr_hours": 8,
                    "billing_cycle": "Monthly Advance",
                    "notice_period_days": 30
                },
                "milestones": [
                    {
                        "stage": "PENDING",
                        "title": "Pending",
                        "description": "Your order is in review & verification",
                        "date_str": "Tue, May 21, 2024, 6:44:14 PM",
                        "completed": True,
                        "icon": "pending"
                    },
                    {
                        "stage": "CONFIRMED",
                        "title": "Order Confirm",
                        "description": "Your order has been verified & confirmed",
                        "date_str": "Thu, May 30, 2024, 9:42:58 AM",
                        "completed": True,
                        "icon": "confirm"
                    },
                    {
                        "stage": "PACKED",
                        "title": "Packed and Processed",
                        "description": "Hardware router & SIM kit dispatched",
                        "date_str": "Fri, May 31, 2024, 9:43:00 AM",
                        "completed": False,
                        "icon": "packed"
                    },
                    {
                        "stage": "DELIVERED",
                        "title": "Delivered",
                        "description": "Expected Delivery Date: Tue, Jun 04, 2024",
                        "date_str": "Expected: Jun 04, 2024",
                        "completed": False,
                        "icon": "delivered"
                    }
                ],
                "created_at": "Tue, May 21, 2024, 6:44:14 PM",
                "updated_at": "Thu, May 30, 2024, 9:42:58 AM"
            }
            db_client.save_order(s60_order)

    def accept_quote(
        self,
        session_id: str,
        bundle_code: str,
        bundle_name: str,
        monthly_cost: float,
        contract_months: int = 12,
        customer_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates an accepted commercial order, persists directly to the SQL database.
        """
        existing_orders = db_client.get_all_orders()
        order_num = f"S{str(len(existing_orders) + 60).zfill(5)}"
        now = datetime.now()
        now_str = now.strftime("%a, %b %d, %Y, %I:%M:%S %p")

        profile = customer_schema or {}
        b_name = profile.get("business_name") or profile.get("contact_name") or "Enterprise Client"
        b_type = profile.get("business_type") or "Retail & Services"
        segment = profile.get("segment") or "Micro Retail & Services"

        if "Multi-site" in segment or "Manufacturing" in segment:
            sla_uptime = "99.9% High-Availability Mission-Critical SLA"
            mttr_hours = 4
        else:
            sla_uptime = "99.5% Standard Commercial Uptime SLA"
            mttr_hours = 8

        milestones = [
            {
                "stage": "PENDING",
                "title": "Pending",
                "description": "Your order is in review & verification",
                "date_str": now_str,
                "completed": True,
                "icon": "pending"
            },
            {
                "stage": "CONFIRMED",
                "title": "Order Confirm",
                "description": "Your order has been verified & confirmed",
                "date_str": "In verification",
                "completed": False,
                "icon": "confirm"
            },
            {
                "stage": "PACKED",
                "title": "Packed and Processed",
                "description": "Hardware router & SIM kit dispatched",
                "date_str": "Pending dispatch",
                "completed": False,
                "icon": "packed"
            },
            {
                "stage": "DELIVERED",
                "title": "Delivered",
                "description": f"Expected: {now.strftime('%b %d, %Y')} + 5 days",
                "date_str": "Scheduled",
                "completed": False,
                "icon": "delivered"
            }
        ]

        order = {
            "order_id": order_num,
            "session_id": session_id,
            "customer_name": b_name,
            "business_type": b_type,
            "status": "Pending",
            "current_stage_index": 0,
            "bundle_code": bundle_code,
            "bundle_name": bundle_name,
            "monthly_cost": monthly_cost,
            "contract_months": contract_months,
            "contract_terms": {
                "sla_uptime": sla_uptime,
                "mttr_hours": mttr_hours,
                "billing_cycle": "Monthly Advance",
                "notice_period_days": 30
            },
            "milestones": milestones,
            "created_at": now_str,
            "updated_at": now.isoformat()
        }

        saved = db_client.save_order(order)

        # Record customer decision as ACCEPTED in PostgreSQL analytics table
        db_client.save_customer_decision(
            session_id=session_id,
            customer_name=b_name,
            business_type=b_type,
            decision_type="ACCEPTED",
            bundle_code=bundle_code,
            bundle_name=bundle_name,
            monthly_cost=monthly_cost,
            ai_response_insights={
                "order_id": order_num,
                "contract_months": contract_months,
                "sla_uptime": sla_uptime,
                "status": "Commercial Contract Signed"
            }
        )

        return {"success": True, "order": saved}

    def reject_quote(
        self,
        session_id: str,
        bundle_code: str,
        rejection_reason: str,
        customer_feedback: str = "",
        budget_offered: Optional[float] = None
    ) -> Dict[str, Any]:
        """Records structured rejection feedback in memory and Cloud PostgreSQL."""
        record = {
            "rejection_id": f"REJ-{uuid.uuid4().hex[:6].upper()}",
            "session_id": session_id,
            "bundle_code": bundle_code,
            "rejection_reason": rejection_reason,
            "customer_feedback": customer_feedback,
            "budget_offered": budget_offered,
            "created_at": datetime.now().isoformat()
        }
        self.rejections.append(record)

        # Record customer decision as REJECTED in PostgreSQL analytics table
        db_client.save_customer_decision(
            session_id=session_id,
            customer_name="Customer",
            decision_type="REJECTED",
            bundle_code=bundle_code,
            rejection_reason=rejection_reason,
            customer_feedback=customer_feedback,
            budget_offered=budget_offered,
            ai_response_insights={
                "rejection_id": record["rejection_id"],
                "reason": rejection_reason,
                "feedback": customer_feedback,
                "budget_offered": budget_offered
            }
        )

        return {"success": True, "record": record}

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves order tracking details directly from the SQL database."""
        return db_client.get_order(order_id)

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Returns all placed customer orders queried directly from the SQL database."""
        return db_client.get_all_orders()

    def get_sales_dashboard(self) -> Dict[str, Any]:
        """Returns aggregated sales metrics, active AI escalations, and orders."""
        all_orders = db_client.get_all_orders()
        db_escalations = db_client.get_all_ai_escalations()

        # Seed default realistic escalations if table is empty
        if not db_escalations:
            default_seeds = [
                {
                    "escalation_id": "ESC-AI-201",
                    "customer_name": "Balaji Dental Care LLP",
                    "session_id": "cust-balaji-01",
                    "priority": "HIGH",
                    "status": "AWAITING_AGENT",
                    "ai_confidence_score": 0.42,
                    "confidence_band": "LOW_CONFIDENCE",
                    "trigger_reason": "Ambiguous Bandwidth & Complex Multi-Site Topology",
                    "what_ai_could_not_extract": ["Exact intra-site latency requirement", "Private MPLS vs Internet Leased Line preference", "On-premise firewall hardware vendor"],
                    "ai_discovery_summary": "Customer operates clinic with dental imaging units across Kochi and Pune. Stated need for 200 Mbps with failover, but did not confirm if branches need direct Layer-2 bridging or IPsec overlay.",
                    "recommended_action": "Enterprise Sales Specialist consultation required to size dedicated symmetric leased line and configure SD-WAN controller.",
                    "timestamp": "Today at 05:42 PM"
                },
                {
                    "escalation_id": "ESC-AI-202",
                    "customer_name": "Mahalaxmi Textiles & Garments",
                    "session_id": "cust-textile-09",
                    "priority": "MEDIUM",
                    "status": "OPEN",
                    "ai_confidence_score": 0.58,
                    "confidence_band": "MODERATE_RISK",
                    "trigger_reason": "Budget Constraint vs SLA Expectation Mismatch",
                    "what_ai_could_not_extract": ["Annual commercial turnover band", "Existing telecom contract exit penalties"],
                    "ai_discovery_summary": "Customer requested 99.9% optical leased line with 24-hour MTTR SLA, but indicated budget under ₹2,000/mo which is below base commercial leased line tariff.",
                    "recommended_action": "Offer Biz 5G AirFiber 100 with failover as cost-effective alternative or negotiate 24-month contract discount.",
                    "timestamp": "Today at 06:15 PM"
                },
                {
                    "escalation_id": "ESC-AI-203",
                    "customer_name": "Shree Ganesh Agro Logistics",
                    "session_id": "cust-agro-14",
                    "priority": "HIGH",
                    "status": "IN_REVIEW",
                    "ai_confidence_score": 0.35,
                    "confidence_band": "CRITICAL_ESCALATION",
                    "trigger_reason": "KYC Document Flag: Address Mismatch & Expired Bill",
                    "what_ai_could_not_extract": ["Current registered principal place of business electricity account number"],
                    "ai_discovery_summary": "Uploaded electricity bill exceeded 90-day validity window (dated 140 days ago) and trade name on GST certificate had slight constitution variance.",
                    "recommended_action": "Request updated utility bill dated within 90 days or municipal tax receipt for principal depot.",
                    "timestamp": "Today at 06:28 PM"
                }
            ]
            for s in default_seeds:
                db_client.save_ai_escalation(s)
            db_escalations = default_seeds

        return {
            "total_leads": 5000,
            "activated_leads": 368 + len(all_orders),
            "conversion_rate_percent": 7.4,
            "avg_lead_to_activation_days": 17.6,
            "recent_orders": all_orders[:10],
            "rejections": self.rejections[-10:],
            "active_escalations": db_escalations
        }

    def send_admin_message(
        self,
        session_id: str,
        customer_name: str,
        message: str,
        bundle_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stores message directly in the persistent SQL database."""
        msg_record = {
            "message_id": f"MSG-{uuid.uuid4().hex[:6].upper()}",
            "session_id": session_id,
            "customer_name": customer_name,
            "message": message,
            "timestamp": datetime.now().strftime("%I:%M %p")
        }
        saved = db_client.save_admin_message(msg_record)
        return {"success": True, "message": saved}

    def get_customer_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Queries messages sent by Admin to this customer directly from the SQL database."""
        return db_client.get_admin_messages(session_id)

    def update_order_stage(self, order_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates order status directly in the SQL database."""
        status_to_idx = {
            "pending": 0,
            "order confirm": 1,
            "confirmed": 1,
            "packed and processed": 2,
            "packed": 2,
            "in progress": 2,
            "delivered": 3,
            "activated": 3
        }

        new_status = updates.get("newStatus") or updates.get("status")
        stage_idx = updates.get("stageIndex")

        if new_status and stage_idx is None:
            stage_idx = status_to_idx.get(new_status.lower(), 1)

        updated = db_client.update_order_status(order_id, new_status, stage_idx)
        return updated


order_lifecycle_service = OrderLifecycleService()
