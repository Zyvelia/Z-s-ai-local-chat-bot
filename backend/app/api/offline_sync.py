"""Account-scoped conflict-aware synchronization for offline-safe metadata.

Only conversation title/archive edits are accepted from the offline queue.
Deleting chats, editing AI messages, uploading media, or generating AI replies
must be performed online by their existing endpoints.
"""
from uuid import UUID
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import User, Conversation, SyncMutation

router = APIRouter(prefix="/api/v1/sync", tags=["offline sync"])


class SafeMetadataEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    base_revision: int = Field(ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    is_archived: bool | None = None

    @model_validator(mode="after")
    def validate_safe_edit(self):
        if self.title is None and self.is_archived is None:
            raise ValueError("At least one offline-safe field is required")
        return self


def snapshot(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "is_archived": conversation.is_archived,
        "metadata_revision": conversation.metadata_revision,
    }


@router.get("/conversations/{conversation_id}")
async def get_sync_state(conversation_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
    if row is None:
        raise HTTPException(404, "Conversation not found")
    return snapshot(row)


@router.post("/conversations/{conversation_id}/metadata")
async def apply_metadata_edit(conversation_id: str, payload: SafeMetadataEdit,
                              user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
    if row is None:
        raise HTTPException(404, "Conversation not found")
    mutation_id = str(payload.operation_id)
    canonical = payload.model_dump(mode="json", exclude={"operation_id"})
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    previous = await db.get(SyncMutation, mutation_id)
    if previous is not None:
        if (previous.user_id != user.id or previous.conversation_id != conversation_id
                or previous.base_revision != payload.base_revision or previous.payload_digest != digest):
            raise HTTPException(409, "Operation ID already used")
        # The same submitted operation is an idempotent acknowledgement.
        # Clients must reconcile with the current server revision afterward.
        return {"status": "already_applied", **snapshot(row), "applied_revision": previous.resulting_revision}

    changes = {"metadata_revision": Conversation.metadata_revision + 1}
    if payload.title is not None:
        changes["title"] = payload.title
    if payload.is_archived is not None:
        changes["is_archived"] = payload.is_archived
    updated = await db.execute(update(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user.id,
        Conversation.metadata_revision == payload.base_revision
    ).values(**changes).returning(Conversation.id))
    if updated.scalar_one_or_none() is None:
        await db.rollback()
        latest = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
        if latest is None:
            raise HTTPException(404, "Conversation not found")
        raise HTTPException(409, detail={"code": "revision_conflict", "server": snapshot(latest)})
    receipt = SyncMutation(id=mutation_id, user_id=user.id, conversation_id=conversation_id,
                           base_revision=payload.base_revision, resulting_revision=payload.base_revision+1,
                           payload_digest=digest)
    db.add(receipt)
    await db.commit()
    await db.refresh(row)
    return {"status": "applied", **snapshot(row), "applied_revision": payload.base_revision+1}
