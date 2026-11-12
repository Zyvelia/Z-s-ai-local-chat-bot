from pydantic import BaseModel, Field

class CharacterModelIn(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=160)

class ConversationModelIn(BaseModel):
    inference_model: str | None = Field(default=None, min_length=1, max_length=160)
    generation_preset: str | None = Field(default=None, pattern="^(balanced|creative|precise|roleplay|custom)$")
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0.05, le=1)
    context_window: int | None = Field(default=None, ge=512, le=131072)
    response_length: int | None = Field(default=None, ge=64, le=2048)
