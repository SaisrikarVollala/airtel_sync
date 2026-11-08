"""
=============================================================================
AGENT: Multi-Turn Session Memory (session_memory.py)
=============================================================================
Thread-safe session storage holding customer schemas, multi-turn history,
and pipeline state per customer session.
=============================================================================
"""

import uuid
from typing import Dict, Any, List, Optional
from schema.customer_profile import CustomerSchema


class ConversationSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.schema = CustomerSchema()
        self.history: List[Dict[str, str]] = []
        self.recommendations: Optional[Any] = None

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})


class SessionMemory:
    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: Optional[str] = None) -> ConversationSession:
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> ConversationSession:
        self._sessions[session_id] = ConversationSession(session_id)
        return self._sessions[session_id]


session_memory = SessionMemory()
