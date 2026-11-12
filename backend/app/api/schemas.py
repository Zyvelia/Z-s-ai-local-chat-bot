from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ExampleTurn(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in ("user", "assistant"):
            raise ValueError("Example role must be user or assistant")
        return value


class CreatorFields(BaseModel):
    template_key: str = Field(default="custom", min_length=1, max_length=40)
    advanced_definition: str = Field(default="", max_length=10000)
    greetings: list[str] = Field(default_factory=list, max_length=8)
    example_dialogue: list[ExampleTurn] = Field(default_factory=list, max_length=16)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("greetings")
    @classmethod
    def validate_greetings(cls, values: list[str]) -> list[str]:
        if any(not v.strip() or len(v) > 2000 for v in values):
            raise ValueError("Each greeting must be 1–2000 characters")
        return [v.strip() for v in values]

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip().lower() for v in values]
        if any(not v or len(v) > 32 for v in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("Tags must be unique and 1–32 characters")
        return cleaned


class CharacterIn(CreatorFields):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(default="", max_length=200)
    personality: str = Field(min_length=1, max_length=8000)
    scenario: str = Field(default="", max_length=4000)
    greeting: str = Field(default="Hello!", max_length=2000)
    preferred_model: str | None = Field(default=None, max_length=160)
    is_public: bool = False
    appearance_description: str = Field(default="", max_length=1500)
    appearance_style: str = Field(default="classic", pattern="^(classic|cinematic|anime|illustrated|realistic)$")
    accent_color: str = Field(default="#6750A4", pattern=r"^#[0-9a-fA-F]{6}$")

class CharacterOut(CharacterIn):
    id: str
    creator_id: str
    model_config = ConfigDict(from_attributes=True)

class CharacterEdit(BaseModel):
    template_key: str | None = Field(default=None, min_length=1, max_length=40)
    advanced_definition: str | None = Field(default=None, max_length=10000)
    greetings: list[str] | None = Field(default=None, max_length=8)
    example_dialogue: list[ExampleTurn] | None = Field(default=None, max_length=16)
    tags: list[str] | None = Field(default=None, max_length=10)

    @field_validator("greetings")
    @classmethod
    def validate_greetings(cls, values: list[str] | None) -> list[str] | None:
        return CreatorFields.validate_greetings(values) if values is not None else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        return CreatorFields.validate_tags(values) if values is not None else None

    name: str | None = Field(default=None, min_length=1, max_length=80)
    tagline: str | None = Field(default=None, max_length=200)
    personality: str | None = Field(default=None, min_length=1, max_length=8000)
    scenario: str | None = Field(default=None, max_length=4000)
    greeting: str | None = Field(default=None, max_length=2000)
    preferred_model: str | None = Field(default=None, max_length=160)
    is_public: bool | None = None
    appearance_description: str | None = Field(default=None, max_length=1500)
    appearance_style: str | None = Field(default=None, pattern="^(classic|cinematic|anime|illustrated|realistic)$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

class ConversationEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    is_archived: bool | None = None
    auto_memory: bool | None = None
    inference_model: str | None = Field(default=None, max_length=160)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0.05, le=1)
    context_window: int | None = Field(default=None, ge=512, le=131072)
    generation_preset: str | None = Field(default=None, pattern="^(balanced|creative|precise|roleplay|custom)$")
    response_length: int | None = Field(default=None, ge=64, le=2048)
    roleplay_mode: bool | None = None
    persona_id: str | None = None

class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=1200)

class MemoryOut(MemoryIn):
    id: str
    conversation_id: str
    model_config = ConfigDict(from_attributes=True)

class ConversationIn(BaseModel):
    character_id: str
    persona_id: str | None = None
    greeting_index: int = Field(default=0, ge=0, le=7)


class PreviewIn(BaseModel):
    character: CharacterIn
    message: str = Field(min_length=1, max_length=1000)


class PreviewOut(BaseModel):
    reply: str


class CharacterImportIn(BaseModel):
    character: CharacterIn


class CharacterExportOut(BaseModel):
    format: str = "character-chat-v1"
    character: CharacterIn

class ConversationOut(BaseModel):
    id: str
    persona_id: str | None = None
    chat_mode: str = "single"
    group_scenario: str = ""
    character_id: str
    title: str
    is_archived: bool
    auto_memory: bool
    active_leaf_id: str | None = None
    response_length: int
    inference_model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    context_window: int | None = None
    generation_preset: str = "balanced"
    roleplay_mode: bool
    background_media_id: str | None = None
    metadata_revision: int = 0
    model_config = ConfigDict(from_attributes=True)

class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

class MessageOut(BaseModel):
    id: str
    speaker_character_id: str | None = None
    role: str
    content: str
    parent_id: str | None = None
    model_config = ConfigDict(from_attributes=True)

class LearnedMemoryOut(BaseModel):
    id: str
    conversation_id: str
    category: str
    content: str
    model_config = ConfigDict(from_attributes=True)

class LearnedMemoryEdit(BaseModel):
    content: str = Field(min_length=1, max_length=400)

class SummaryOut(BaseModel):
    content: str
    through_message_id: str | None = None

class LorebookIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    keywords: str = Field(default="", max_length=400)
    content: str = Field(min_length=1, max_length=1600)

class LorebookOut(LorebookIn):
    id: str
    character_id: str
    model_config = ConfigDict(from_attributes=True)

class MessageEdit(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

class BranchIn(BaseModel):
    message_id: str

class RegenerateIn(BaseModel):
    assistant_id: str

class SelectAlternativeIn(BaseModel):
    assistant_id: str


class PersonaIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    biography: str = Field(default="", max_length=3000)
    avatar_url: str = Field(default="", max_length=500)

    @field_validator("avatar_url")
    @classmethod
    def safe_avatar_url(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("Avatar URL must use HTTPS")
        return value

class PersonaEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    biography: str | None = Field(default=None, max_length=3000)
    avatar_url: str | None = Field(default=None, max_length=500)

    @field_validator("avatar_url")
    @classmethod
    def safe_avatar_url(cls, value: str | None) -> str | None:
        return PersonaIn.safe_avatar_url(value) if value is not None else None

class PersonaOut(PersonaIn):
    id: str
    model_config = ConfigDict(from_attributes=True)

class PersonaSelection(BaseModel):
    persona_id: str | None = None

class GroupConversationIn(BaseModel):
    character_ids: list[str] = Field(min_length=2, max_length=6)
    title: str = Field(default="Group roleplay", min_length=1, max_length=120)
    scenario: str = Field(default="", max_length=4000)
    persona_id: str | None = None

    @field_validator("character_ids")
    @classmethod
    def unique_participants(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids):
            raise ValueError("Characters must be unique")
        return ids

class GroupParticipantOut(BaseModel):
    character_id: str
    name: str
    position: int

class GroupTurnIn(BaseModel):
    character_id: str | None = None  # None selects round-robin next character.
