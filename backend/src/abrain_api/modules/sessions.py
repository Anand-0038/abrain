from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SessionStatus = Literal["fresh", "active", "terminated"]


class AgentSession(BaseModel):
    """A runtime session; persistence belongs to the future memory adapter, not this shell."""

    session_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)
    status: SessionStatus
    started_at: datetime
    terminated_at: datetime | None = None
