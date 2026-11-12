"""Internal-only self-hosted Piper + faster-whisper audio worker.

Only internal API requests with X-Internal-Token are accepted. No public port.
"""
import asyncio
import hmac
import re
import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

TOKEN = os.environ.get('VOICE_INTERNAL_TOKEN', '')
PIPER_MODEL = Path(os.environ.get('PIPER_MODEL_PATH', '/models/voice.onnx'))
WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'tiny')
WHISPER_CACHE = os.environ.get('WHISPER_DOWNLOAD_ROOT', '/model-cache')
app = FastAPI(title='Private voice worker')
_lock = asyncio.Semaphore(1)
_whisper = None


def verify(token: str | None):
    if not TOKEN or not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(401, 'Unauthorized')


def model_file(voice_id: str) -> Path:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', voice_id):
        raise ValueError('Invalid voice identifier')
    return PIPER_MODEL if voice_id == 'default' else PIPER_MODEL.parent / (voice_id + '.onnx')


def synth(text: str, voice_id: str = 'default') -> bytes:
    voice_model = model_file(voice_id)
    if not voice_model.is_file():
        raise RuntimeError('Piper voice model is not installed')
    # stdin, argument list, explicit timeout and temporary output avoid shell injection.
    with tempfile.TemporaryDirectory() as root:
        dest = Path(root) / 'speech.wav'
        result = subprocess.run(['piper', '--model', str(voice_model), '--output_file', str(dest)],
                                input=text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=70)
        if result.returncode != 0 or not dest.is_file():
            raise RuntimeError('Piper inference failed')
        data = dest.read_bytes()
        if len(data) > 16 * 1024 * 1024:
            raise RuntimeError('Audio too large')
        return data


def recognize(raw: bytes) -> str:
    global _whisper
    from faster_whisper import WhisperModel
    if _whisper is None:
        _whisper = WhisperModel(WHISPER_MODEL, device='cpu', compute_type='int8', download_root=WHISPER_CACHE)
    with tempfile.TemporaryDirectory() as root:
        source = Path(root) / 'input.audio'
        source.write_bytes(raw)
        duration = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(source)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        try:
            seconds = float(duration.stdout.strip())
        except ValueError as exc:
            raise ValueError('Could not determine recording duration') from exc
        if duration.returncode != 0 or seconds <= 0 or seconds > 60:
            raise ValueError('Recording must be 60 seconds or shorter')
        segments, _ = _whisper.transcribe(str(source), beam_size=1, vad_filter=True)
        return ' '.join(s.text.strip() for s in segments).strip()[:5000]


class SynthesisInput(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    voice_id: str = 'default'


@app.get('/health')
def health(x_internal_token: str | None = Header(default=None)):
    verify(x_internal_token)
    return {'tts_ready': PIPER_MODEL.is_file(), 'stt_ready': True, 'engine': 'Piper + faster-whisper'}


@app.post('/synthesize')
async def tts(body: SynthesisInput, x_internal_token: str | None = Header(default=None)):
    verify(x_internal_token)
    if body.voice_id != 'default' and not model_file(body.voice_id).is_file():
        raise HTTPException(422, 'Voice model not installed')
    async with _lock:
        try:
            data = await asyncio.to_thread(synth, body.text, body.voice_id)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(503, 'Local TTS engine is unavailable') from exc
    return Response(data, media_type='audio/wav')


@app.post('/transcribe')
async def stt(file: UploadFile = File(...), x_internal_token: str | None = Header(default=None)):
    verify(x_internal_token)
    data = await file.read(12 * 1024 * 1024 + 1)
    await file.close()
    if not data or len(data) > 12 * 1024 * 1024:
        raise HTTPException(413, 'Recording is too large')
    async with _lock:
        try:
            text = await asyncio.to_thread(recognize, data)
        except Exception as exc:
            raise HTTPException(503, 'Local transcription failed') from exc
    return {'text': text}
