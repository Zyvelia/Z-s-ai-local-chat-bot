"""Authenticated voice endpoints; only an internal self-hosted voice worker is contacted."""
from pathlib import Path
from uuid import uuid4
import wave
from io import BytesIO

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.entities import Character, Conversation, Message, User, VoiceClip

router = APIRouter(prefix='/api/v1/voice', tags=['voice'])
MAX_RECORDING = 12 * 1024 * 1024
MAX_WAV = 16 * 1024 * 1024
ALLOWED_AUDIO = {'audio/wav', 'audio/x-wav', 'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/mpeg'}


def validate_audio(data: bytes, content_type: str) -> None:
    if not data or len(data) > MAX_RECORDING or content_type not in ALLOWED_AUDIO:
        raise ValueError('Unsupported recording or recording exceeds 12 MiB')
    signatures = (data[:4] == b'RIFF' and data[8:12] == b'WAVE',
                  data.startswith(b'\x1a\x45\xdf\xa3'), data.startswith(b'OggS'),
                  b'ftyp' in data[4:12], data.startswith(b'ID3'), data.startswith(b'\xff\xfb'))
    if not any(signatures):
        raise ValueError('Recording header does not match a supported audio container')
    if signatures[0]:
        try:
            with wave.open(BytesIO(data), 'rb') as wav:
                if wav.getframerate() <= 0 or wav.getnframes() / wav.getframerate() > 60:
                    raise ValueError('Recording exceeds 60 seconds')
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise ValueError('Malformed WAV recording') from exc


def validate_wav(data: bytes) -> None:
    if not data or len(data) > MAX_WAV:
        raise ValueError('Generated audio exceeds limit')
    try:
        with wave.open(BytesIO(data), 'rb') as wav:
            if wav.getnchannels() not in (1, 2) or wav.getframerate() > 48000 or wav.getsampwidth() not in (1, 2, 3, 4):
                raise ValueError('Unsupported generated audio format')
            if wav.getnframes() / wav.getframerate() > 90:
                raise ValueError('Generated audio is too long')
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise ValueError('Invalid generated WAV') from exc


def audio_path(key: str) -> Path:
    return Path(settings.audio_storage_dir) / key


def voice_choices() -> list[str]:
    return [x.strip() for x in settings.voice_ids.split(',') if x.strip()]


def worker_headers():
    return {'X-Internal-Token': settings.voice_internal_token}


async def call_worker(path: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5)) as client:
            response = await client.post(settings.voice_service_url.rstrip('/') + path, headers=worker_headers(), **kwargs)
            response.raise_for_status()
            return response
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        raise HTTPException(503 if code >= 500 else 422, 'Local voice engine could not process audio') from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, 'Local voice engine is unavailable') from exc


async def owned_chat(chat_id: str, user: User, db: AsyncSession) -> Conversation:
    chat = await db.get(Conversation, chat_id)
    if chat is None or chat.user_id != user.id:
        raise HTTPException(404, 'Conversation not found')
    return chat


class VoicePreference(BaseModel):
    voice_id: str


@router.get('/status')
async def voice_status(user: User = Depends(current_user)):
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(settings.voice_service_url.rstrip('/') + '/health', headers=worker_headers())
            r.raise_for_status()
            data = r.json()
        return {'online': True, 'tts_ready': bool(data.get('tts_ready')), 'stt_ready': bool(data.get('stt_ready')), 'voices': voice_choices()}
    except (httpx.HTTPError, ValueError):
        return {'online': False, 'tts_ready': False, 'stt_ready': False, 'voices': voice_choices()}


@router.put('/characters/{character_id}/voice')
async def set_character_voice(character_id: str, body: VoicePreference, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, character_id)
    if char is None or char.creator_id != user.id:
        raise HTTPException(404, 'Character not found')
    if body.voice_id not in voice_choices():
        raise HTTPException(422, 'Voice is not installed or permitted')
    char.voice_id = body.voice_id
    await db.commit()
    return {'character_id': char.id, 'voice_id': char.voice_id}


@router.post('/transcribe')
async def transcribe(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Transcription is ephemeral; not retained unless user sends the text."""
    try:
        data = await file.read(MAX_RECORDING + 1)
        validate_audio(data, file.content_type or '')
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
    response = await call_worker('/transcribe', files={'file': ('recording', data, file.content_type)})
    try:
        result = response.json()
        text = result['text']
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, 'Invalid speech recognition response') from exc
    if not isinstance(text, str) or len(text) > 5000:
        raise HTTPException(502, 'Invalid transcript')
    return {'text': text.strip()}


@router.post('/conversations/{chat_id}/messages/{message_id}/synthesize', status_code=201)
async def synthesize(chat_id: str, message_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    chat = await owned_chat(chat_id, user, db)
    message = await db.get(Message, message_id)
    if message is None or message.conversation_id != chat_id or message.role != 'assistant':
        raise HTTPException(404, 'Assistant message not found')
    character_id = message.speaker_character_id or chat.character_id
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(404, 'Character not found')
    voice = character.voice_id or 'default'
    if voice not in voice_choices():
        raise HTTPException(422, 'Selected voice is not available')
    if not message.content.strip() or len(message.content) > 3000:
        raise HTTPException(422, 'Message must contain 1 to 3000 characters for speech')
    count = await db.scalar(select(func.count(VoiceClip.id)).where(VoiceClip.owner_id == user.id))
    if (count or 0) >= settings.max_voice_clips:
        raise HTTPException(429, 'Saved voice clip limit reached; delete old clips first')
    response = await call_worker('/synthesize', json={'text': message.content, 'voice_id': voice})
    try:
        validate_wav(response.content)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    key = uuid4().hex + '.wav'
    target = audio_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as f:
        f.write(response.content)
    clip = VoiceClip(owner_id=user.id, conversation_id=chat_id, message_id=message_id,
                     voice_id=voice, storage_key=key, size_bytes=len(response.content))
    db.add(clip)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        target.unlink(missing_ok=True)
        raise
    return {'id': clip.id, 'message_id': message_id, 'voice_id': voice, 'url': f'/api/v1/voice/clips/{clip.id}'}


@router.get('/conversations/{chat_id}/clips')
async def list_clips(chat_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_chat(chat_id, user, db)
    clips = (await db.scalars(select(VoiceClip).where(VoiceClip.conversation_id == chat_id,
                      VoiceClip.owner_id == user.id).order_by(VoiceClip.created_at.desc()).limit(100))).all()
    return [{'id': c.id, 'message_id': c.message_id, 'voice_id': c.voice_id, 'size_bytes': c.size_bytes} for c in clips]


@router.get('/clips/{clip_id}')
async def get_clip(clip_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    clip = await db.get(VoiceClip, clip_id)
    if not clip or clip.owner_id != user.id:
        raise HTTPException(404, 'Audio not found')
    await owned_chat(clip.conversation_id, user, db)
    path = audio_path(clip.storage_key)
    if not path.is_file():
        raise HTTPException(404, 'Audio file missing')
    return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/clips/{clip_id}', status_code=204)
async def delete_clip(clip_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    clip = await db.get(VoiceClip, clip_id)
    if not clip or clip.owner_id != user.id:
        raise HTTPException(404, 'Audio not found')
    key = clip.storage_key
    await db.delete(clip)
    await db.commit()
    audio_path(key).unlink(missing_ok=True)
