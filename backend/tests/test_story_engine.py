"""v1.5 deterministic story state, ownership and migration contracts."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from app.api.story_schemas import (StorySettings, SceneIn, EmotionIn, RelationshipIn, EventIn, ScenarioIn)
from app.api.story import own_chat, own_story, set_emotion, apply_scenario
from app.models.entities import (Conversation, StoryState, StoryScene, StoryEmotion, StoryEvent,
    StoryRelationship, StoryScenario)
from app.services.story import render_story_context


def test_story_payload_limits_and_status():
    assert StorySettings(title='My tale', chapter=4, status='paused').chapter == 4
    for invalid in [{'title':''}, {'title':'A','chapter':0}, {'title':'A','status':'unknown'},
                    {'title':'A','premise':'x'*2001}]:
        with pytest.raises(ValidationError):
            StorySettings(**invalid)
    with pytest.raises(ValidationError): SceneIn(title='')
    with pytest.raises(ValidationError): RelationshipIn(affinity=101)
    with pytest.raises(ValidationError): RelationshipIn(trust=-101)
    with pytest.raises(ValidationError): EmotionIn(emotion='unbounded')
    with pytest.raises(ValidationError): EmotionIn(intensity=101)
    with pytest.raises(ValidationError): EventIn(kind='admin')
    with pytest.raises(ValidationError): ScenarioIn(title='x'*121)


def test_context_is_bounded_and_excludes_uninitialized_story():
    assert render_story_context(None, None, [], [], []) == ''
    state = SimpleNamespace(title='Demo', chapter=1, status='active', premise='x'*8000, objective='find artifact')
    scene = SimpleNamespace(title='Castle', setting='stone corridor', goal='escape')
    mood = SimpleNamespace(character_id='c1', emotion='fear', intensity=88, notes='worried')
    relation = SimpleNamespace(character_id='c1', affinity=30, trust=70, notes='ally')
    event = SimpleNamespace(kind='discovery', title='Found key', details='bronze key')
    result = render_story_context(state, scene, [mood], [relation], [event])
    assert len(result) <= 5500
    assert 'Castle' in result and 'fear' in result and 'Found key' in result
    assert 'system-level' not in result and 'untrusted' in result


class FakeDb:
    def __init__(self, entries): self.entries = entries
    async def get(self, model, key): return self.entries.get((model, key))

@pytest.mark.asyncio
async def test_story_is_private_to_conversation_owner():
    db = FakeDb({(Conversation, 'chat'): SimpleNamespace(id='chat', user_id='owner'),
                 (StoryState, 'chat'): SimpleNamespace(conversation_id='chat')})
    with pytest.raises(HTTPException) as exc:
        await own_story('chat', SimpleNamespace(id='stranger'), db)
    assert exc.value.status_code == 404
    assert (await own_story('chat', SimpleNamespace(id='owner'), db)).conversation_id == 'chat'

@pytest.mark.asyncio
async def test_missing_story_refuses_mutation():
    db = FakeDb({(Conversation, 'chat'): SimpleNamespace(id='chat', user_id='owner')})
    with pytest.raises(HTTPException) as exc:
        await own_story('chat', SimpleNamespace(id='owner'), db)
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_other_users_scenario_not_applied():
    db = FakeDb({(Conversation, 'chat'): SimpleNamespace(id='chat', user_id='me'),
                 (StoryScenario, 'secret'): SimpleNamespace(id='secret', owner_id='other')})
    with pytest.raises(HTTPException) as exc:
        await apply_scenario('chat', 'secret', SimpleNamespace(id='me'), db)
    assert exc.value.status_code == 404


def test_migration_matches_entities_and_has_foreign_key_cascades():
    sql = (Path(__file__).resolve().parents[1] / 'migrations' / '012_story_engine.sql').read_text()
    for model in (StoryState, StoryScene, StoryRelationship, StoryEmotion, StoryEvent, StoryScenario):
        assert f'CREATE TABLE IF NOT EXISTS {model.__tablename__}' in sql
        ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        assert 'CREATE TABLE' in ddl
    assert sql.count('ON DELETE CASCADE') >= 6
    assert 'BEGIN;' in sql and 'COMMIT;' in sql


def test_story_is_connected_to_chat_stream_and_fork():
    source = (Path(__file__).resolve().parents[1] / 'app/api/routes.py').read_text()
    assert 'await story_context(db, conversation.id)' in source
    assert 'await clone_story(db, source.id, fork.id)' in source

@pytest.mark.asyncio
async def test_emotion_updates_reject_nonparticipant():
    db = FakeDb({(Conversation, 'chat'): SimpleNamespace(id='chat', user_id='owner', character_id='c1', chat_mode='single'),
                 (StoryState, 'chat'): SimpleNamespace(conversation_id='chat')})
    with pytest.raises(HTTPException) as exc:
        await set_emotion('chat', 'c2', EmotionIn(emotion='joy'), SimpleNamespace(id='owner'), db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_fork_copies_story_without_shared_mutable_objects():
    from app.services.story import clone_story
    from uuid import uuid4
    state = SimpleNamespace(title='Mystery', premise='Castle', objective='Find key', chapter=2,
                            status='active', current_scene_id='scene1')
    scene = SimpleNamespace(id='scene1', title='Hall', setting='Cold', goal='Search', position=0)
    rel = SimpleNamespace(character_id='c1', affinity=15, trust=33, notes='ally')
    mood = SimpleNamespace(character_id='c1', emotion='fear', intensity=70, notes='threat')
    event = SimpleNamespace(scene_id='scene1', kind='discovery', title='Found map', details='north', created_at=None)
    class ScalarResult:
        def __init__(self, values): self.values=values
        def all(self): return self.values
    class Db(FakeDb):
        def __init__(self):
            super().__init__({(StoryState, 'source'): state})
            self.added=[]
        async def scalars(self, query):
            table=query.column_descriptions[0]['entity']
            return ScalarResult({StoryScene:[scene],StoryRelationship:[rel],StoryEmotion:[mood],StoryEvent:[event]}.get(table,[]))
        def add(self, obj): self.added.append(obj)
        async def flush(self):
            for obj in self.added:
                if hasattr(obj,'id') and obj.id is None: obj.id=str(uuid4())
    db=Db()
    await clone_story(db,'source','fork')
    copied_state = next(x for x in db.added if isinstance(x, StoryState))
    copied_scene = next(x for x in db.added if isinstance(x, StoryScene))
    copied_event = next(x for x in db.added if isinstance(x, StoryEvent))
    assert copied_state.conversation_id == 'fork'
    assert copied_scene.id != 'scene1'
    assert copied_state.current_scene_id == copied_scene.id
    assert copied_event.scene_id == copied_scene.id
    copied_scene.setting='Updated in fork'
    assert scene.setting == 'Cold'
