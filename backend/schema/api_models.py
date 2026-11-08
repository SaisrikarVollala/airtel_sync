"""
=============================================================================
SCHEMA: API Request & Response Contracts (api_models.py)
=============================================================================
Typed Pydantic models for incoming requests and outgoing responses
across all REST API endpoints.
=============================================================================
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="Customer message text")
    session_id: Optional[str] = Field(None, description="Active session ID")


class QuoteAcceptRequest(BaseModel):
    sessionId: str
    bundleCode: str
    bundleName: str
    monthlyCost: float
    contractMonths: int = 12
    customerSchema: Optional[Dict[str, Any]] = None


class QuoteRejectRequest(BaseModel):
    sessionId: str
    bundleCode: str
    rejectionReason: str
    customerFeedback: str = ""
    budgetOffered: Optional[float] = None


class OrderStatusUpdateRequest(BaseModel):
    newStatus: Optional[str] = None
    stageIndex: Optional[int] = None
    escalationNote: Optional[str] = None
    salesAgent: Optional[str] = "Sales Agent"


class WhatIfRequest(BaseModel):
    session_id: Optional[str] = None
    schema_data: Optional[Dict[str, Any]] = Field(None, alias="schema")
    max_installation_days: Optional[int] = None
    has_gstin: Optional[str] = None
    gstin: Optional[str] = None


class SegmentResolveRequest(BaseModel):
    business_type: str
