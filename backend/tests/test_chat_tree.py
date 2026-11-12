from dataclasses import dataclass
from datetime import datetime, timezone
from app.services.chat_tree import path_to, active_path, siblings_for, validate_alternation, roleplay_prompt
from app.api.schemas import ConversationEdit, MessageEdit, RegenerateIn
from pydantic import ValidationError
import pytest

@dataclass
class Msg:
    id: str
    parent_id: str | None
    role: str
    content: str = "sample"
    created_at: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)


def sample():
    nodes = [Msg('u1', None, 'user'), Msg('a1', 'u1', 'assistant'),
             Msg('a2', 'u1', 'assistant'), Msg('u2', 'a2', 'user'),
             Msg('a3', 'u2', 'assistant')]
    return {m.id: m for m in nodes}


def test_active_path_only_selected_alternative():
    tree = sample()
    assert [x.id for x in active_path(tree, 'a3')] == ['u1', 'a2', 'u2', 'a3']
    assert validate_alternation(active_path(tree, 'a3'))
    assert [x.id for x in active_path(tree, 'a1')] == ['u1', 'a1']


def test_alternative_siblings():
    tree = sample()
    assert {x.id for x in siblings_for(tree, tree['a1'])} == {'a1', 'a2'}


def test_broken_and_cyclic_trees_rejected():
    with pytest.raises(ValueError):
        path_to({'a': Msg('a', 'unknown', 'user')}, 'a')
    with pytest.raises(ValueError):
        path_to({'a': Msg('a', 'b', 'user'), 'b': Msg('b', 'a', 'assistant')}, 'a')


def test_response_length_constraints():
    assert ConversationEdit(response_length=512).response_length == 512
    with pytest.raises(ValidationError):
        ConversationEdit(response_length=5000)
    with pytest.raises(ValidationError):
        ConversationEdit(response_length=20)


def test_edit_and_regeneration_require_values():
    assert MessageEdit(content='revised').content == 'revised'
    assert RegenerateIn(assistant_id='abc').assistant_id == 'abc'
    with pytest.raises(ValidationError):
        MessageEdit(content='')


def test_roleplay_formatting_toggle():
    assert 'asterisks' in roleplay_prompt(True)
    assert 'ordinary conversational' in roleplay_prompt(False)
