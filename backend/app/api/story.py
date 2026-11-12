"""Private story state, scenes, relationships, emotions, timeline, and reusable scenarios."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import (User, Conversation, StoryState, StoryScene, StoryRelationship,
    StoryEmotion, StoryEvent, StoryScenario)
from app.api.story_schemas import (StorySettings, StoryOut, SceneIn, SceneOut, RelationshipIn,
    RelationshipOut, EmotionIn, EmotionOut, EventIn, EventOut, ScenarioIn, ScenarioOut)
from app.services.story import authorized_story_character

router = APIRouter(prefix='/api/v1', tags=['story'])

async def own_chat(chat_id: str, user: User, db: AsyncSession):
    chat = await db.get(Conversation, chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(404, 'Conversation not found')
    return chat

async def own_story(chat_id: str, user: User, db: AsyncSession):
    await own_chat(chat_id, user, db)
    state = await db.get(StoryState, chat_id)
    if not state:
        raise HTTPException(404, 'Story not initialized')
    return state

@router.get('/conversations/{chat_id}/story', response_model=StoryOut)
async def get_story(chat_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await own_story(chat_id, user, db)

@router.put('/conversations/{chat_id}/story', response_model=StoryOut)
async def put_story(chat_id: str, payload: StorySettings, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_chat(chat_id, user, db)
    state = await db.get(StoryState, chat_id)
    if state is None:
        state = StoryState(conversation_id=chat_id)
        db.add(state)
    for key, value in payload.model_dump().items():
        setattr(state, key, value)
    await db.commit()
    await db.refresh(state)
    return state

@router.get('/conversations/{chat_id}/story/scenes', response_model=list[SceneOut])
async def list_scenes(chat_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_chat(chat_id, user, db)
    return (await db.scalars(select(StoryScene).where(StoryScene.conversation_id == chat_id).order_by(StoryScene.position))).all()

@router.post('/conversations/{chat_id}/story/scenes', response_model=SceneOut, status_code=201)
async def add_scene(chat_id: str, payload: SceneIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    count = await db.scalar(select(func.count()).select_from(StoryScene).where(StoryScene.conversation_id == chat_id))
    if count >= 100:
        raise HTTPException(422, 'Scene limit reached')
    scene = StoryScene(conversation_id=chat_id, position=count, **payload.model_dump())
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene

@router.patch('/conversations/{chat_id}/story/scenes/{scene_id}', response_model=SceneOut)
async def edit_scene(chat_id: str, scene_id: str, payload: SceneIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    scene = await db.get(StoryScene, scene_id)
    if not scene or scene.conversation_id != chat_id:
        raise HTTPException(404, 'Scene not found')
    for key, value in payload.model_dump().items():
        setattr(scene, key, value)
    await db.commit()
    await db.refresh(scene)
    return scene

@router.put('/conversations/{chat_id}/story/scenes/{scene_id}/activate', response_model=StoryOut)
async def activate_scene(chat_id: str, scene_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    state = await own_story(chat_id, user, db)
    scene = await db.get(StoryScene, scene_id)
    if not scene or scene.conversation_id != chat_id:
        raise HTTPException(404, 'Scene not found')
    state.current_scene_id = scene_id
    db.add(StoryEvent(conversation_id=chat_id, scene_id=scene_id, kind='scene', title=('Entered: ' + scene.title)[:120], details=scene.setting[:1000]))
    await db.commit()
    await db.refresh(state)
    return state

@router.delete('/conversations/{chat_id}/story/scenes/{scene_id}', status_code=204)
async def remove_scene(chat_id: str, scene_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    state = await own_story(chat_id, user, db)
    scene = await db.get(StoryScene, scene_id)
    if not scene or scene.conversation_id != chat_id:
        raise HTTPException(404, 'Scene not found')
    if state.current_scene_id == scene_id:
        state.current_scene_id = None
    await db.delete(scene)
    await db.commit()

@router.get('/conversations/{chat_id}/story/relationships', response_model=list[RelationshipOut])
async def relationships(chat_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    return (await db.scalars(select(StoryRelationship).where(StoryRelationship.conversation_id == chat_id))).all()

@router.put('/conversations/{chat_id}/story/relationships/{character_id}', response_model=RelationshipOut)
async def set_relationship(chat_id: str, character_id: str, payload: RelationshipIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    chat = await own_chat(chat_id, user, db)
    await own_story(chat_id, user, db)
    if not await authorized_story_character(db, chat, character_id):
        raise HTTPException(404, 'Character is not in this conversation')
    current = await db.scalar(select(StoryRelationship).where(StoryRelationship.conversation_id == chat_id, StoryRelationship.character_id == character_id))
    if current is None:
        current = StoryRelationship(conversation_id=chat_id, character_id=character_id)
        db.add(current)
    for key, value in payload.model_dump().items():
        setattr(current, key, value)
    await db.commit()
    await db.refresh(current)
    return current

@router.get('/conversations/{chat_id}/story/emotions', response_model=list[EmotionOut])
async def emotions(chat_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    return (await db.scalars(select(StoryEmotion).where(StoryEmotion.conversation_id == chat_id))).all()

@router.put('/conversations/{chat_id}/story/emotions/{character_id}', response_model=EmotionOut)
async def set_emotion(chat_id: str, character_id: str, payload: EmotionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    chat = await own_chat(chat_id, user, db)
    await own_story(chat_id, user, db)
    if not await authorized_story_character(db, chat, character_id):
        raise HTTPException(404, 'Character is not in this conversation')
    mood = await db.get(StoryEmotion, (chat_id, character_id))
    if mood is None:
        mood = StoryEmotion(conversation_id=chat_id, character_id=character_id)
        db.add(mood)
    for key, value in payload.model_dump().items():
        setattr(mood, key, value)
    await db.commit()
    await db.refresh(mood)
    return mood

@router.get('/conversations/{chat_id}/story/timeline', response_model=list[EventOut])
async def timeline(chat_id: str, limit: int = 100, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    if not 1 <= limit <= 200:
        raise HTTPException(422, 'Invalid timeline limit')
    rows = (await db.scalars(select(StoryEvent).where(StoryEvent.conversation_id == chat_id)
        .order_by(StoryEvent.created_at.desc(), StoryEvent.id.desc()).limit(limit))).all()
    return list(reversed(rows))

@router.post('/conversations/{chat_id}/story/timeline', response_model=EventOut, status_code=201)
async def add_event(chat_id: str, payload: EventIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    state = await own_story(chat_id, user, db)
    count = await db.scalar(select(func.count()).select_from(StoryEvent).where(StoryEvent.conversation_id == chat_id))
    if count >= 1000:
        raise HTTPException(422, 'Timeline limit reached')
    entry = StoryEvent(conversation_id=chat_id, scene_id=state.current_scene_id, **payload.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry

@router.delete('/conversations/{chat_id}/story/timeline/{event_id}', status_code=204)
async def delete_event(chat_id: str, event_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_story(chat_id, user, db)
    event = await db.get(StoryEvent, event_id)
    if not event or event.conversation_id != chat_id:
        raise HTTPException(404, 'Timeline entry not found')
    await db.delete(event)
    await db.commit()

@router.get('/story/scenarios', response_model=list[ScenarioOut])
async def list_scenarios(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(StoryScenario).where(StoryScenario.owner_id == user.id)
        .order_by(StoryScenario.created_at.desc()).limit(100))).all()

@router.post('/story/scenarios', response_model=ScenarioOut, status_code=201)
async def create_scenario(payload: ScenarioIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(StoryScenario).where(StoryScenario.owner_id == user.id))
    if count >= 100:
        raise HTTPException(422, 'Scenario limit reached')
    scenario = StoryScenario(owner_id=user.id, **payload.model_dump())
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario

@router.delete('/story/scenarios/{scenario_id}', status_code=204)
async def delete_scenario(scenario_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(StoryScenario, scenario_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, 'Scenario not found')
    await db.delete(item)
    await db.commit()

@router.post('/conversations/{chat_id}/story/scenarios/{scenario_id}', response_model=StoryOut)
async def apply_scenario(chat_id: str, scenario_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_chat(chat_id, user, db)
    template = await db.get(StoryScenario, scenario_id)
    if not template or template.owner_id != user.id:
        raise HTTPException(404, 'Scenario not found')
    state = await db.get(StoryState, chat_id)
    if state is None:
        state = StoryState(conversation_id=chat_id)
        db.add(state)
    state.title = template.title
    state.premise = template.premise
    state.objective = template.objective
    if template.opening_scene:
        scene = StoryScene(conversation_id=chat_id, title=(template.title + ' — Opening')[:120], setting=template.opening_scene)
        db.add(scene)
        await db.flush()
        state.current_scene_id = scene.id
    await db.commit()
    await db.refresh(state)
    return state
