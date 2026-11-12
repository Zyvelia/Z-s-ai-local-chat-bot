"""v0.8 unit/contract tests: no Docker or live Ollama required."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.api.model_schemas import CharacterModelIn, ConversationModelIn
from app.services.inference import PRESETS, effective_options, LocalInferenceQueue
from app.providers.ollama import OllamaProvider
from app.models.entities import Base


def test_preset_resolution_and_inheritance():
    character = SimpleNamespace(preferred_model='my-local-model:latest')
    conversation = SimpleNamespace(inference_model=None, generation_preset='creative', temperature=None,
        top_p=None, context_window=8192, response_length=1024)
    options = effective_options(character, conversation)
    assert options.model == 'my-local-model:latest'
    assert options.temperature == PRESETS['creative']['temperature']
    assert options.top_p == PRESETS['creative']['top_p']
    assert (options.num_ctx, options.num_predict) == (8192, 1024)
    conversation.inference_model = 'override:3b'
    conversation.temperature = 0.0
    conversation.top_p = 0.05
    assert effective_options(character, conversation).model == 'override:3b'
    assert effective_options(character, conversation).temperature == 0
    assert effective_options(character, conversation).top_p == 0.05


def test_custom_input_constraints():
    assert ConversationModelIn(temperature=0, top_p=1, context_window=131072, response_length=2048)
    assert CharacterModelIn(model=None).model is None
    for value in (-1, 2.1):
        with pytest.raises(ValidationError): ConversationModelIn(temperature=value)
    for value in (0.01, 1.1):
        with pytest.raises(ValidationError): ConversationModelIn(top_p=value)
    for value in (511, 131073):
        with pytest.raises(ValidationError): ConversationModelIn(context_window=value)
    with pytest.raises(ValidationError): ConversationModelIn(generation_preset='unknown')
    with pytest.raises(ValidationError): ConversationModelIn(inference_model='x' * 161)


def test_migration_matches_models():
    sql = (Path(__file__).parents[1] / 'migrations' / '008_ai_model_control.sql').read_text()
    for field in ('preferred_model', 'inference_model', 'temperature', 'top_p', 'context_window', 'generation_preset'):
        assert field in sql
    assert all(field in Base.metadata.tables['conversations'].columns for field in
        ('inference_model', 'temperature', 'top_p', 'context_window', 'generation_preset'))
    assert 'preferred_model' in Base.metadata.tables['characters'].columns


def test_queue_capacity_timeout_and_release():
    async def run():
        queue = LocalInferenceQueue(capacity=1, wait_seconds=0.015)
        await queue.acquire()
        assert queue.snapshot()['running'] == 1
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await queue.acquire()
        assert exc.value.status_code == 503
        assert queue.snapshot()['waiting'] == 0
        queue.release()
        await queue.acquire()
        queue.release()
        assert queue.snapshot()['running'] == 0
    asyncio.run(run())


def test_ollama_model_list_and_status(monkeypatch):
    import httpx
    async def run():
        requests = []
        def handler(request):
            requests.append(request.url.path)
            if request.url.path == '/api/tags':
                return httpx.Response(200, json={'models': [{'name': 'local:1', 'size': 100, 'details': {'family': 'llama'}}]})
            if request.url.path == '/api/version':
                return httpx.Response(200, json={'version': '0.test'})
            if request.url.path == '/api/ps':
                return httpx.Response(200, json={'models': [{'name': 'local:1', 'size_vram': 35}]})
            return httpx.Response(404)
        original_client = httpx.AsyncClient
        monkeypatch.setattr(httpx, 'AsyncClient', lambda *args, **kwargs: original_client(*args, transport=httpx.MockTransport(handler), **kwargs))
        provider = OllamaProvider()
        assert (await provider.models())[0]['name'] == 'local:1'
        await provider.ensure_installed('local:1')
        with pytest.raises(ValueError): await provider.ensure_installed('missing')
        status = await provider.status()
        assert status['loaded_models'][0]['size_vram'] == 35
        assert '/api/ps' in requests
    asyncio.run(run())


def test_ollama_request_includes_options(monkeypatch):
    import httpx
    payloads = []
    def handler(request):
        if request.url.path == '/api/chat':
            import json
            payloads.append(json.loads(request.content))
            return httpx.Response(200, text='{"message":{"content":"Hi"},"done":false}\n{"done":true}\n')
        return httpx.Response(404)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *args, **kwargs: original_client(*args, transport=httpx.MockTransport(handler), **kwargs))
    async def run():
        chunks = [x async for x in OllamaProvider().stream_chat([{'role': 'user', 'content': 'hi'}],
          max_tokens=666, model='local:1', temperature=0.2, top_p=0.5, num_ctx=8192)]
        assert chunks == ['Hi']
        assert payloads[0]['model'] == 'local:1'
        assert payloads[0]['options'] == {'num_predict': 666, 'temperature': 0.2, 'top_p': 0.5, 'num_ctx': 8192}
    asyncio.run(run())
