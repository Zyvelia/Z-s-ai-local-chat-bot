from typing import Literal
from pydantic import BaseModel, Field

class UserRestriction(BaseModel):
    suspend: bool
    days: int | None = Field(None, ge=1, le=365)
    reason: str = Field("", max_length=500)

class CharacterModeration(BaseModel):
    status: Literal["active", "hidden", "removed"]
    reason: str = Field(..., min_length=3, max_length=500)

class ReportDecision(BaseModel):
    status: Literal["reviewing", "resolved", "dismissed"]
    note: str = Field("", max_length=1000)

class AppealSubmission(BaseModel):
    character_id: str | None = None
    reason: str = Field(..., min_length=10, max_length=2000)

class AppealDecision(BaseModel):
    status: Literal["accepted", "rejected"]
    response: str = Field(..., min_length=3, max_length=2000)
