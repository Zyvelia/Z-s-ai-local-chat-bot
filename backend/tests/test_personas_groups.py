"""v0.6 tests for persona validation, group routing and roleplay context."""
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.api.schemas import GroupConversationIn, PersonaIn, PersonaEdit, ConversationOut, MessageOut
from app.services.group_chat import next_speaker, group_prompt, persona_prompt
from app.models.entities import Persona, GroupParticipant, Conversation, Message


def test_unique_group_members_and_capacity():
    good = GroupConversationIn(character_ids=['a','b','c'], title='Scene')
    assert good.character_ids == ['a','b','c']
    for ids in (['a'], ['a','a'], list('abcdefg')):
        with pytest.raises(ValidationError):
            GroupConversationIn(character_ids=ids)


def test_persona_fields_validation():
    result = PersonaIn(name='Traveler', biography='From the north', avatar_url='https://example.org/avatar.png')
    assert result.name == 'Traveler'
    with pytest.raises(ValidationError):
        PersonaIn(name='x', avatar_url='http://example.org/a.png')
    with pytest.raises(ValidationError):
        PersonaEdit(avatar_url='javascript:alert(1)')
    with pytest.raises(ValidationError):
        PersonaIn(name='x', biography='X' * 3001)


def test_auto_speaker_rotation():
    members = ['nova', 'kai', 'iris']
    assert next_speaker(members, None) == 'nova'
    assert next_speaker(members, 'nova') == 'kai'
    assert next_speaker(members, 'iris') == 'nova'
    assert next_speaker(members, 'kai', 'iris') == 'iris'
    with pytest.raises(ValueError):
        next_speaker(members, None, 'outsider')
    with pytest.raises(ValueError):
        next_speaker([], None)


def test_prompt_contains_identity_and_group_scenario():
    a = SimpleNamespace(name='Nova', tagline='Detective', personality='Curious', scenario='', advanced_definition='', example_dialogue=[])
    b = SimpleNamespace(name='Kai', tagline='Engineer', personality='Calm', scenario='', advanced_definition='', example_dialogue=[])
    user = SimpleNamespace(name='Traveler', biography='Has a map')
    p = group_prompt(a, [a, b], 'A mysterious train station', user)
    assert 'ONLY Nova' in p
    assert 'Kai' in p
    assert 'A mysterious train station' in p
    assert 'Traveler' in p
    assert 'Do not write their actions or dialogue' in persona_prompt(user)
    assert persona_prompt(None) == ''


def test_schema_group_and_speaker_compatible_with_old_data():
    old = dict(id='cid', character_id='a', title='Chat', is_archived=False,
               auto_memory=False, response_length=384, roleplay_mode=True)
    parsed = ConversationOut.model_validate(old)
    assert parsed.chat_mode == 'single'
    assert parsed.persona_id is None
    msg = MessageOut(id='id', role='assistant', content='Hello')
    assert msg.speaker_character_id is None


def test_models_have_expected_relationship_columns():
    assert 'persona_id' in Conversation.__table__.columns
    assert 'speaker_character_id' in Message.__table__.columns
    assert 'user_id' in Persona.__table__.columns
    assert {'conversation_id', 'character_id', 'position'} <= set(GroupParticipant.__table__.columns.keys())


def test_group_routes_exist():
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1] / 'app' / 'api' / 'routes.py'
    tree = ast.parse(source.read_text())
    patterns = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {'get', 'post', 'patch', 'delete', 'put'}:
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        patterns.add(('/api/v1' + dec.args[0].value, dec.func.attr.upper()))
    for method, path in [
        ('GET', '/api/v1/personas'), ('POST', '/api/v1/personas'),
        ('PATCH', '/api/v1/personas/{persona_id}'), ('DELETE', '/api/v1/personas/{persona_id}'),
        ('POST', '/api/v1/conversations/groups'),
        ('GET', '/api/v1/conversations/{conversation_id}/participants'),
        ('PUT', '/api/v1/conversations/{conversation_id}/persona'),
        ('POST', '/api/v1/conversations/{conversation_id}/group/turn'),
    ]:
        assert (path, method) in patterns
