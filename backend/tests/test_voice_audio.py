"""Voice API security, format validation, and migration schema tests; no models required."""
from io import BytesIO
import wave
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.api.voice import (validate_audio, validate_wav, owned_chat, voice_choices,
                           set_character_voice, VoicePreference, get_clip, MAX_RECORDING)
from app.models.entities import Character, Conversation, VoiceClip


def wav(seconds=0.05, rate=16000):
    dest = BytesIO()
    with wave.open(dest, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b'\x00\x00' * int(seconds * rate))
    return dest.getvalue()


def test_pcm_wav_accepted_for_transcription_and_synthesis():
    data = wav()
    validate_audio(data, 'audio/wav')
    validate_wav(data)


@pytest.mark.parametrize('data,mime', [
    (b'', 'audio/wav'), (b'<svg>no</svg>', 'audio/wav'),
    (b'RIFF', 'audio/wav'), (b'x' * (MAX_RECORDING + 1), 'audio/wav'),
    (wav(), 'image/png'), (b'ID3' + b'x' * 8, 'application/octet-stream'),
])
def test_reject_invalid_audio(data, mime):
    with pytest.raises(ValueError):
        validate_audio(data, mime)


def test_invalid_worker_wav_and_too_long():
    for bad in [b'bad wav', b'', wav(seconds=91)]:
        with pytest.raises(ValueError):
            validate_wav(bad)


def test_postgres_voice_migration_and_model():
    sql = (Path(__file__).parents[1] / 'migrations' / '011_voice_audio.sql').read_text()
    assert 'ALTER TABLE characters' in sql
    assert 'CREATE TABLE IF NOT EXISTS voice_clips' in sql
    ddl = str(CreateTable(VoiceClip.__table__).compile(dialect=postgresql.dialect()))
    assert 'owner_id' in ddl and 'message_id' in ddl and 'conversation_id' in ddl


class FakeDb:
    def __init__(self, values):
        self.values = values
        self.commits = 0
    async def get(self, model, id):
        return self.values.get((model, id))
    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_chat_owner_required():
    db = FakeDb({(Conversation, 'chat'): SimpleNamespace(id='chat', user_id='other')})
    with pytest.raises(HTTPException) as exc:
        await owned_chat('chat', SimpleNamespace(id='me'), db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_voice_preference_creator_only():
    char = SimpleNamespace(id='character', creator_id='other', voice_id='default')
    db = FakeDb({(Character, 'character'): char})
    with pytest.raises(HTTPException) as exc:
        await set_character_voice('character', VoicePreference(voice_id='default'),
                                  SimpleNamespace(id='me'), db)
    assert exc.value.status_code == 404
    assert db.commits == 0


@pytest.mark.asyncio
async def test_voice_preference_rejects_noninstalled_voice(monkeypatch):
    monkeypatch.setattr('app.api.voice.voice_choices', lambda: ['default'])
    char = SimpleNamespace(id='character', creator_id='me', voice_id='default')
    db = FakeDb({(Character, 'character'): char})
    with pytest.raises(HTTPException) as exc:
        await set_character_voice('character', VoicePreference(voice_id='untrusted'),
                                  SimpleNamespace(id='me'), db)
    assert exc.value.status_code == 422
    assert char.voice_id == 'default'


@pytest.mark.asyncio
async def test_clip_private_even_when_user_guesses_id():
    clip = SimpleNamespace(owner_id='someone-else', conversation_id='chat')
    db = FakeDb({(VoiceClip, 'clip'): clip})
    with pytest.raises(HTTPException) as exc:
        await get_clip('clip', SimpleNamespace(id='me'), db)
    assert exc.value.status_code == 404


def test_voice_worker_not_published_in_compose():
    compose = (Path(__file__).resolve().parents[2] / 'compose.yaml').read_text()
    assert 'voice:\n    build: ./voice-service' in compose
    voice_config = compose.split('  voice:\n')[1].split('  api:\n')[0]
    assert '\n    ports:' not in voice_config
