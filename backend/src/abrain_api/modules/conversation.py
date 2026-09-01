from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Speaker = Literal["owner", "npc"]


class ConversationTurn(BaseModel):
    """Transient conversation data; it is not a durable memory record."""

    turn_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    speaker: Speaker
    text: str = Field(min_length=1)
    occurred_at: datetime
