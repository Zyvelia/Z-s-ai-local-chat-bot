from pydantic import BaseModel, Field, ConfigDict, field_validator
import re

class PublicProfile(BaseModel):
    user_id: str
    handle: str
    display_name: str
    bio: str
    avatar_url: str
    follower_count: int = 0
    is_following: bool = False

class ProfileEdit(BaseModel):
    handle: str = Field(min_length=3, max_length=32)
    bio: str = Field(default="", max_length=1000)
    avatar_url: str = Field(default="", max_length=500)
    @field_validator("handle")
    @classmethod
    def valid_handle(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,31}", value):
            raise ValueError("Handle must start with a letter and contain only lowercase letters, numbers and _")
        return value
    @field_validator("avatar_url")
    @classmethod
    def valid_avatar(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("Avatar URL must use HTTPS")
        return value

class CollectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=400)

class CollectionOut(CollectionIn):
    id: str
    model_config = ConfigDict(from_attributes=True)

class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)

class ReportIn(BaseModel):
    reason: str
    details: str = Field(default="", max_length=1000)
    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value):
        if value not in ("spam", "harassment", "sexual_content", "violence", "impersonation", "other"):
            raise ValueError("Unsupported report reason")
        return value

class CharacterDiscovery(BaseModel):
    id: str
    creator_id: str
    name: str
    tagline: str
    tags: list[str]
    favorites: int
    chats: int
    average_rating: float | None
    rating_count: int
    is_favorite: bool = False

class SearchPage(BaseModel):
    items: list[CharacterDiscovery]
    total: int
    limit: int
    offset: int
