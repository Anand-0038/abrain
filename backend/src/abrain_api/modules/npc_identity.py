from typing import Literal

from pydantic import BaseModel, Field

NpcSpecialization = Literal["primary", "planner", "worker", "reviewer"]
WorkerSpecialization = Literal["planner", "worker", "reviewer"]
NpcAvatarKey = Literal["node", "scout", "orbiter"]
NpcAccessoryKey = Literal["none", "antenna", "satchel"]


class NpcAppearance(BaseModel):
    palette: str = Field(default="teal", min_length=1, max_length=32)
    avatar_key: NpcAvatarKey = "node"
    accessory_key: NpcAccessoryKey = "none"


class NpcIdentity(BaseModel):
    """Persistent brain identity with an ephemeral runtime session."""

    npc_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    appearance: NpcAppearance = Field(default_factory=NpcAppearance)
    role: str = Field(
        default="owner-context companion",
        min_length=1,
        max_length=160,
    )
    personality: str = Field(
        default="thoughtful, concise, and honest about uncertainty",
        min_length=1,
        max_length=240,
    )
    specialization: NpcSpecialization = "primary"
