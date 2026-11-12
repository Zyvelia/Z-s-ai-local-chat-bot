from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, Integer, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def now_utc():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspension_reason: Mapped[str] = mapped_column(String(500), default="", nullable=False)

class Character(Base):
    __tablename__ = "characters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    personality: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(Text, default="")
    greeting: Mapped[str] = mapped_column(Text, default="Hello!")
    template_key: Mapped[str] = mapped_column(String(40), default="custom")
    advanced_definition: Mapped[str] = mapped_column(Text, default="")
    greetings: Mapped[list] = mapped_column(JSON, default=list)
    example_dialogue: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    preferred_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    voice_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    appearance_description: Mapped[str] = mapped_column(String(1500), default="")
    appearance_style: Mapped[str] = mapped_column(String(32), default="classic")
    accent_color: Mapped[str] = mapped_column(String(7), default="#6750A4")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    moderation_status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), index=True)
    persona_id: Mapped[str | None] = mapped_column(ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    chat_mode: Mapped[str] = mapped_column(String(12), default="single")
    group_scenario: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(120), default="New chat")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    auto_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    active_leaf_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    inference_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    top_p: Mapped[float | None] = mapped_column(nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_preset: Mapped[str] = mapped_column(String(32), default="balanced")
    response_length: Mapped[int] = mapped_column(Integer, default=384)
    roleplay_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    background_media_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    metadata_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

class SyncMutation(Base):
    """Idempotency receipts for explicit offline-safe conversation metadata edits."""
    __tablename__ = "sync_mutations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    speaker_character_id: Mapped[str | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class ConversationMemory(Base):
    __tablename__ = "conversation_memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="")
    through_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

class LearnedMemory(Base):
    __tablename__ = "learned_memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(24), default="fact")
    content: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class LorebookEntry(Base):
    __tablename__ = "lorebook_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    keywords: Mapped[str] = mapped_column(String(400), default="")
    content: Mapped[str] = mapped_column(String(1600))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Persona(Base):
    __tablename__ = "personas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    biography: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class GroupParticipant(Base):
    __tablename__ = "group_participants"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


# v0.7 public-community data. Profiles deliberately expose no email addresses.
class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    handle: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    bio: Mapped[str] = mapped_column(String(1000), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")

class Favorite(Base):
    __tablename__ = "character_favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Collection(Base):
    __tablename__ = "character_collections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class CollectionItem(Base):
    __tablename__ = "collection_items"
    collection_id: Mapped[str] = mapped_column(ForeignKey("character_collections.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class CreatorFollow(Base):
    __tablename__ = "creator_follows"
    follower_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (CheckConstraint("follower_id <> creator_id", name="ck_no_self_follow"),)

class CharacterRating(Base):
    __tablename__ = "character_ratings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (CheckConstraint("stars BETWEEN 1 AND 5", name="ck_rating_range"),)

class CommunityReport(Base):
    __tablename__ = "community_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    details: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("reporter_id", "character_id", name="uq_report_once"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ModerationAppeal(Base):
    __tablename__ = "moderation_appeals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    character_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    response: Mapped[str] = mapped_column(String(2000), default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str | None] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    persona_id: Mapped[str | None] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(90), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class VoiceClip(Base):
    """Private, server-generated voice for an assistant message."""
    __tablename__ = "voice_clips"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    voice_id: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(90), unique=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


# v1.5: all story data belongs to a private conversation, not to the public character.
class StoryState(Base):
    __tablename__ = "story_states"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), default="Untitled story")
    premise: Mapped[str] = mapped_column(String(2000), default="")
    objective: Mapped[str] = mapped_column(String(500), default="")
    chapter: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    current_scene_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

class StoryScene(Base):
    __tablename__ = "story_scenes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    setting: Mapped[str] = mapped_column(String(1200), default="")
    goal: Mapped[str] = mapped_column(String(500), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class StoryRelationship(Base):
    __tablename__ = "story_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    affinity: Mapped[int] = mapped_column(Integer, default=0)
    trust: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(String(600), default="")
    __table_args__ = (UniqueConstraint("conversation_id", "character_id", name="uq_story_relationship"),
        CheckConstraint("affinity BETWEEN -100 AND 100", name="ck_story_affinity"),
        CheckConstraint("trust BETWEEN -100 AND 100", name="ck_story_trust"))

class StoryEmotion(Base):
    __tablename__ = "story_emotions"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    emotion: Mapped[str] = mapped_column(String(24), default="neutral")
    intensity: Mapped[int] = mapped_column(Integer, default=50)
    notes: Mapped[str] = mapped_column(String(400), default="")
    __table_args__ = (CheckConstraint("intensity BETWEEN 0 AND 100", name="ck_story_emotion_intensity"),)

class StoryEvent(Base):
    __tablename__ = "story_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("story_scenes.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), default="milestone")
    title: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class StoryScenario(Base):
    __tablename__ = "story_scenarios"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    premise: Mapped[str] = mapped_column(String(2000), default="")
    opening_scene: Mapped[str] = mapped_column(String(1200), default="")
    objective: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
