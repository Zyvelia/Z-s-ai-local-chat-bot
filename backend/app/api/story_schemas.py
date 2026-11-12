"""Validated payloads for per-conversation interactive stories."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class StorySettings(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(default="", max_length=2000)
    objective: str = Field(default="", max_length=500)
    chapter: int = Field(default=1, ge=1, le=1000)
    status: Literal["active", "paused", "completed"] = "active"

class SceneIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    setting: str = Field(default="", max_length=1200)
    goal: str = Field(default="", max_length=500)

class RelationshipIn(BaseModel):
    affinity: int = Field(default=0, ge=-100, le=100)
    trust: int = Field(default=0, ge=-100, le=100)
    notes: str = Field(default="", max_length=600)

class EmotionIn(BaseModel):
    emotion: Literal["neutral", "joy", "sadness", "anger", "fear", "surprise", "affection", "curiosity", "anxiety", "resolve"] = "neutral"
    intensity: int = Field(default=50, ge=0, le=100)
    notes: str = Field(default="", max_length=400)

class EventIn(BaseModel):
    kind: Literal["milestone", "decision", "discovery", "relationship", "scene"] = "milestone"
    title: str = Field(min_length=1, max_length=120)
    details: str = Field(default="", max_length=1000)

class ScenarioIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(default="", max_length=2000)
    opening_scene: str = Field(default="", max_length=1200)
    objective: str = Field(default="", max_length=500)

class StoryOut(StorySettings):
    conversation_id: str
    current_scene_id: str | None
    model_config = ConfigDict(from_attributes=True)

class SceneOut(SceneIn):
    id: str
    position: int
    model_config = ConfigDict(from_attributes=True)

class RelationshipOut(RelationshipIn):
    id: str
    character_id: str
    model_config = ConfigDict(from_attributes=True)

class EmotionOut(EmotionIn):
    character_id: str
    model_config = ConfigDict(from_attributes=True)

class EventOut(EventIn):
    id: str
    scene_id: str | None
    model_config = ConfigDict(from_attributes=True)

class ScenarioOut(ScenarioIn):
    id: str
    model_config = ConfigDict(from_attributes=True)
