from pydantic import BaseModel, Field


class OwnerIdentity(BaseModel):
    """Identity boundary for a future owner-backed continuity flow."""

    owner_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=120)
