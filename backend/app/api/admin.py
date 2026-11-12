"""v0.9 admin, appeal and privacy routes. Admin authorization is mandatory server-side."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import current_user, authenticated_user
from app.models.entities import (
    User, Character, Conversation, Message, Persona, GroupParticipant, ConversationMemory,
    ConversationSummary, LearnedMemory, LorebookEntry, Favorite, Collection, CollectionItem,
    UserProfile, CreatorFollow, CharacterRating, CommunityReport, AuditLog, ModerationAppeal, MediaAsset, VoiceClip,
)
from app.api.admin_schemas import (
    UserRestriction, CharacterModeration, ReportDecision, AppealSubmission, AppealDecision,
)

router = APIRouter(prefix="/api/v1", tags=["administration"])

def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user

def audit(db: AsyncSession, actor: User, action: str, kind: str, target: str, details=None):
    db.add(AuditLog(actor_id=actor.id, action=action, target_type=kind,
                    target_id=target, details=details or {}))

@router.get("/admin/dashboard")
async def dashboard(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    async def count(table):
        return (await db.scalar(select(func.count()).select_from(table))) or 0
    return {"users": await count(User), "characters": await count(Character),
            "conversations": await count(Conversation), "open_reports": (await db.scalar(
                select(func.count()).select_from(CommunityReport).where(CommunityReport.status == "open"))) or 0,
            "open_appeals": (await db.scalar(select(func.count()).select_from(ModerationAppeal).where(ModerationAppeal.status == "open"))) or 0}

@router.get("/admin/users")
async def users(q: str = Query("", max_length=100), limit: int = Query(30, ge=1, le=100),
                offset: int = Query(0, ge=0), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(User)
    if q.strip(): stmt = stmt.where(User.email.ilike("%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
    rows = (await db.scalars(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))).all()
    return [{"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role,
             "is_suspended": u.is_suspended, "suspended_until": u.suspended_until} for u in rows]

@router.put("/admin/users/{user_id}/restriction")
async def restrict_user(user_id: str, payload: UserRestriction, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target = await db.get(User, user_id)
    if not target: raise HTTPException(404, "User not found")
    if target.role == "admin": raise HTTPException(403, "Admin accounts cannot be suspended through this endpoint")
    target.is_suspended = payload.suspend
    target.suspended_until = datetime.now(timezone.utc) + timedelta(days=payload.days) if payload.suspend and payload.days else None
    target.suspension_reason = payload.reason if payload.suspend else ""
    audit(db, admin, "user.restriction", "user", user_id, {"suspended": payload.suspend, "days": payload.days, "reason": payload.reason})
    await db.commit()
    return {"status": "suspended" if payload.suspend else "active"}

@router.put("/admin/characters/{character_id}/moderation")
async def moderate_character(character_id: str, payload: CharacterModeration, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target = await db.get(Character, character_id)
    if not target: raise HTTPException(404, "Character not found")
    previous = target.moderation_status
    target.moderation_status = payload.status
    audit(db, admin, "character.moderate", "character", character_id,
          {"from": previous, "to": payload.status, "reason": payload.reason})
    await db.commit()
    return {"status": target.moderation_status}

@router.get("/admin/reports")
async def reports(status: str = Query("open", pattern="^(open|reviewing|resolved|dismissed|all)$"),
                  limit: int = Query(50, ge=1, le=100), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(CommunityReport)
    if status != "all": stmt = stmt.where(CommunityReport.status == status)
    records = (await db.scalars(stmt.order_by(CommunityReport.created_at.desc()).limit(limit))).all()
    return [{"id": r.id, "character_id": r.character_id, "reporter_id": r.reporter_id,
             "reason": r.reason, "details": r.details, "status": r.status} for r in records]

@router.put("/admin/reports/{report_id}")
async def review_report(report_id: str, payload: ReportDecision, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    item = await db.get(CommunityReport, report_id)
    if not item: raise HTTPException(404, "Report not found")
    item.status = payload.status
    audit(db, admin, "report.review", "report", report_id, payload.model_dump())
    await db.commit()
    return {"status": item.status}

@router.post("/appeals", status_code=201)
async def appeal(payload: AppealSubmission, user: User = Depends(authenticated_user), db: AsyncSession = Depends(get_db)):
    if payload.character_id:
        character = await db.get(Character, payload.character_id)
        if not character or character.creator_id != user.id or character.moderation_status == "active":
            raise HTTPException(404, "No moderated character owned by you")
    count = await db.scalar(select(func.count()).select_from(ModerationAppeal).where(
        ModerationAppeal.user_id == user.id, ModerationAppeal.status == "open"))
    if (count or 0) >= 3: raise HTTPException(429, "Too many open appeals")
    a = ModerationAppeal(user_id=user.id, **payload.model_dump())
    db.add(a)
    await db.commit()
    return {"id": a.id, "status": a.status}

@router.get("/appeals/mine")
async def my_appeals(user: User = Depends(authenticated_user), db: AsyncSession = Depends(get_db)):
    records = (await db.scalars(select(ModerationAppeal).where(ModerationAppeal.user_id == user.id)
            .order_by(ModerationAppeal.created_at.desc()).limit(50))).all()
    return [{"id": a.id, "character_id": a.character_id, "reason": a.reason, "status": a.status,
             "response": a.response} for a in records]

@router.get("/admin/appeals")
async def appeals(status: str = Query("open", pattern="^(open|accepted|rejected|all)$"),
                  admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(ModerationAppeal)
    if status != "all": stmt = stmt.where(ModerationAppeal.status == status)
    records = (await db.scalars(stmt.order_by(ModerationAppeal.created_at.desc()).limit(100))).all()
    return [{"id": a.id, "user_id": a.user_id, "character_id": a.character_id,
             "reason": a.reason, "status": a.status, "response": a.response} for a in records]

@router.put("/admin/appeals/{appeal_id}")
async def resolve_appeal(appeal_id: str, payload: AppealDecision, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(ModerationAppeal, appeal_id)
    if not a: raise HTTPException(404, "Appeal not found")
    a.status = payload.status
    a.response = payload.response
    a.reviewed_by = admin.id
    audit(db, admin, "appeal.resolve", "appeal", appeal_id, payload.model_dump())
    await db.commit()
    return {"status": a.status}

@router.get("/admin/audit")
async def audit_events(limit: int = Query(50, ge=1, le=200), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    records = (await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).all()
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "target_type": a.target_type,
             "target_id": a.target_id, "details": a.details, "created_at": a.created_at} for a in records]

@router.get("/privacy/export")
async def data_export(user: User = Depends(authenticated_user), db: AsyncSession = Depends(get_db)):
    """Export the requesting user's private chats and authored content; no other users' private chats."""
    owned_chars = (await db.scalars(select(Character).where(Character.creator_id == user.id))).all()
    conversations = (await db.scalars(select(Conversation).where(Conversation.user_id == user.id))).all()
    ids = [c.id for c in conversations]
    messages = (await db.scalars(select(Message).where(Message.conversation_id.in_(ids)))).all() if ids else []
    pinned = (await db.scalars(select(ConversationMemory).where(ConversationMemory.conversation_id.in_(ids)))).all() if ids else []
    learned = (await db.scalars(select(LearnedMemory).where(LearnedMemory.conversation_id.in_(ids)))).all() if ids else []
    summaries = (await db.scalars(select(ConversationSummary).where(ConversationSummary.conversation_id.in_(ids)))).all() if ids else []
    personas = (await db.scalars(select(Persona).where(Persona.user_id == user.id))).all()
    owned_media = (await db.scalars(select(MediaAsset).where(MediaAsset.owner_id == user.id))).all()
    owned_voice = (await db.scalars(select(VoiceClip).where(VoiceClip.owner_id == user.id))).all()
    from app.models.entities import StoryState, StoryScene, StoryRelationship, StoryEmotion, StoryEvent, StoryScenario
    states = (await db.scalars(select(StoryState).where(StoryState.conversation_id.in_(ids)))).all() if ids else []
    scenes = (await db.scalars(select(StoryScene).where(StoryScene.conversation_id.in_(ids)))).all() if ids else []
    relations = (await db.scalars(select(StoryRelationship).where(StoryRelationship.conversation_id.in_(ids)))).all() if ids else []
    emotions = (await db.scalars(select(StoryEmotion).where(StoryEmotion.conversation_id.in_(ids)))).all() if ids else []
    events = (await db.scalars(select(StoryEvent).where(StoryEvent.conversation_id.in_(ids)))).all() if ids else []
    scenarios = (await db.scalars(select(StoryScenario).where(StoryScenario.owner_id == user.id))).all()
    return {"format": "character-chat-v1.5", "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {"id": user.id, "email": user.email, "display_name": user.display_name},
        "characters": [{"id": c.id, "name": c.name, "personality": c.personality, "scenario": c.scenario,
                        "advanced_definition": c.advanced_definition, "greetings": c.greetings, "tags": c.tags, "voice_id": c.voice_id} for c in owned_chars],
        "personas": [{"id": p.id, "name": p.name, "biography": p.biography, "avatar_url": p.avatar_url} for p in personas],
        "media_assets": [{"id": a.id, "purpose": a.purpose, "character_id": a.character_id, "conversation_id": a.conversation_id, "persona_id": a.persona_id} for a in owned_media],
        "voice_clips": [{"id": c.id, "conversation_id": c.conversation_id, "message_id": c.message_id, "voice_id": c.voice_id} for c in owned_voice],
        "conversations": [{"id": c.id, "character_id": c.character_id, "title": c.title, "group_scenario": c.group_scenario} for c in conversations],
        "messages": [{"id": m.id, "conversation_id": m.conversation_id, "role": m.role,
                      "content": m.content, "parent_id": m.parent_id, "speaker_character_id": m.speaker_character_id} for m in messages],
        "pinned_memories": [{"conversation_id": x.conversation_id, "content": x.content} for x in pinned],
        "learned_memories": [{"conversation_id": x.conversation_id, "category": x.category, "content": x.content} for x in learned],
        "summaries": [{"conversation_id": x.conversation_id, "content": x.content} for x in summaries],
        "story_states": [{"conversation_id": x.conversation_id, "title": x.title, "premise": x.premise,
            "objective": x.objective, "chapter": x.chapter, "status": x.status, "current_scene_id": x.current_scene_id} for x in states],
        "story_scenes": [{"id": x.id, "conversation_id": x.conversation_id, "title": x.title,
            "setting": x.setting, "goal": x.goal} for x in scenes],
        "story_relationships": [{"conversation_id": x.conversation_id, "character_id": x.character_id,
            "affinity": x.affinity, "trust": x.trust, "notes": x.notes} for x in relations],
        "story_emotions": [{"conversation_id": x.conversation_id, "character_id": x.character_id,
            "emotion": x.emotion, "intensity": x.intensity, "notes": x.notes} for x in emotions],
        "story_timeline": [{"conversation_id": x.conversation_id, "scene_id": x.scene_id,
            "kind": x.kind, "title": x.title, "details": x.details} for x in events],
        "story_scenarios": [{"id": x.id, "title": x.title, "premise": x.premise,
            "opening_scene": x.opening_scene, "objective": x.objective} for x in scenarios]}

@router.delete("/privacy/account", status_code=204)
async def delete_my_account(user: User = Depends(authenticated_user), db: AsyncSession = Depends(get_db)):
    """Hard delete with explicit dependency ordering. Preserve minimal anonymized admin audit trail."""
    if user.role == "admin": raise HTTPException(403, "Administrators must transfer duties before deletion")
    authored = select(Character.id).where(Character.creator_id == user.id)
    # Capture owned files for deletion only after the DB transaction succeeds.
    from app.api.media import asset_path
    media_keys = (await db.scalars(select(MediaAsset.storage_key).where(MediaAsset.owner_id == user.id))).all()
    from app.api.voice import audio_path
    voice_keys = (await db.scalars(select(VoiceClip.storage_key).where((VoiceClip.owner_id == user.id) |
        VoiceClip.conversation_id.in_(select(Conversation.id).where(Conversation.user_id == user.id))))).all()
    await db.execute(delete(VoiceClip).where(VoiceClip.owner_id == user.id))
    await db.execute(delete(MediaAsset).where(MediaAsset.owner_id == user.id))
    # Remove chats owned by user AND chats referencing their characters, including group conversations.
    affected = select(Conversation.id).where(
        (Conversation.user_id == user.id) | Conversation.character_id.in_(authored) |
        Conversation.id.in_(select(GroupParticipant.conversation_id).where(GroupParticipant.character_id.in_(authored))))
    extra_voice_keys = (await db.scalars(select(VoiceClip.storage_key).where(VoiceClip.conversation_id.in_(affected)))).all()
    await db.execute(delete(VoiceClip).where(VoiceClip.conversation_id.in_(affected)))
    for model in [Message, ConversationMemory, LearnedMemory, ConversationSummary, GroupParticipant]:
        await db.execute(delete(model).where(model.conversation_id.in_(affected)))
    await db.execute(delete(Conversation).where(Conversation.id.in_(affected)))
    await db.execute(delete(LorebookEntry).where(LorebookEntry.character_id.in_(authored)))
    # collections made by user and collection memberships referencing authored characters
    collections = select(Collection.id).where(Collection.user_id == user.id)
    await db.execute(delete(CollectionItem).where((CollectionItem.collection_id.in_(collections)) |
        (CollectionItem.character_id.in_(authored))))
    await db.execute(delete(Collection).where(Collection.user_id == user.id))
    await db.execute(delete(Favorite).where((Favorite.user_id == user.id) | Favorite.character_id.in_(authored)))
    await db.execute(delete(CharacterRating).where((CharacterRating.user_id == user.id) | CharacterRating.character_id.in_(authored)))
    await db.execute(delete(CommunityReport).where((CommunityReport.reporter_id == user.id) | CommunityReport.character_id.in_(authored)))
    await db.execute(delete(CreatorFollow).where((CreatorFollow.follower_id == user.id) | (CreatorFollow.creator_id == user.id)))
    await db.execute(delete(UserProfile).where(UserProfile.user_id == user.id))
    await db.execute(delete(Persona).where(Persona.user_id == user.id))
    await db.execute(delete(ModerationAppeal).where(ModerationAppeal.user_id == user.id))
    await db.execute(delete(Character).where(Character.creator_id == user.id))
    # No email or message content in durable audit trail.
    audit(db, user, "account.deleted", "user", user.id)
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    for key in media_keys:
        asset_path(key).unlink(missing_ok=True)
    for key in set(voice_keys + extra_voice_keys):
        audio_path(key).unlink(missing_ok=True)
