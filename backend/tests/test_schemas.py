import pytest
from pydantic import ValidationError
from app.api.schemas import CharacterIn, MessageIn, RegisterIn

def test_valid_character():
    c = CharacterIn(name="Nova", personality="Thoughtful explorer")
    assert c.is_public is False

def test_reject_empty_message():
    with pytest.raises(ValidationError):
        MessageIn(content="")

def test_short_password():
    with pytest.raises(ValidationError):
        RegisterIn(email="a@example.com", display_name="A", password="123")

from app.api.schemas import ConversationEdit, CharacterEdit, MemoryIn

def test_memory_is_bounded():
    with pytest.raises(ValidationError):
        MemoryIn(content='x' * 1201)
    assert MemoryIn(content='The character knows my nickname.').content

def test_conversation_title_length():
    with pytest.raises(ValidationError):
        ConversationEdit(title='')
    with pytest.raises(ValidationError):
        ConversationEdit(title='a' * 121)

def test_character_patch_validation():
    with pytest.raises(ValidationError):
        CharacterEdit(name='')
    assert CharacterEdit(tagline='Updated').tagline == 'Updated'
