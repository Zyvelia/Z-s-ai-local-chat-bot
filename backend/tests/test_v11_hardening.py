"""No live Ollama or PostgreSQL required: transport and migration invariants."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from app.providers.ollama import OllamaProvider
from app.services.inference import LocalInferenceQueue


@pytest.fixture
def mock_ollama(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'llama3.2:3b'}]})
        if request.url.path == '/api/version':
            return httpx.Response(200, json={'version': '0.9-test'})
        if request.url.path == '/api/ps':
            return httpx.Response(404)
        if request.url.path == '/api/chat':
            payload = json.loads(request.content)
            assert payload['stream'] is True
            return httpx.Response(200, text='\n'.join([
                json.dumps({'message': {'content': 'Hello '}, 'done': False}),
                json.dumps({'message': {'content': 'world'}, 'done': False}),
                json.dumps({'done': True}),
            ]) + '\n')
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    real_client = httpx.AsyncClient

    def client(*args, **kwargs):
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr('app.providers.ollama.httpx.AsyncClient', client)
    return calls


@pytest.mark.asyncio
async def test_ollama_streamed_tokens_and_options(mock_ollama):
    provider = OllamaProvider()
    assert await provider.models() == [{'name': 'llama3.2:3b', 'size': None, 'modified_at': None, 'details': {}}]
    tokens = [token async for token in provider.stream_chat(
        [{'role': 'user', 'content': 'hello'}], model='llama3.2:3b',
        temperature=0.45, top_p=0.8, num_ctx=2048, max_tokens=128)]
    assert tokens == ['Hello ', 'world']
    payload = json.loads(mock_ollama[-1].content)
    assert payload['options'] == {'num_predict': 128, 'temperature': 0.45, 'top_p': 0.8, 'num_ctx': 2048}


@pytest.mark.asyncio
async def test_ollama_status_degrades_when_ps_not_supported(mock_ollama):
    info = await OllamaProvider().status()
    assert info['online'] is True
    assert info['loaded_models'] is None


@pytest.mark.asyncio
async def test_ollama_http_failure_does_not_return_partial_success(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    real_client = httpx.AsyncClient
    monkeypatch.setattr('app.providers.ollama.httpx.AsyncClient', lambda *a, **k: real_client(*a, transport=transport, **k))
    with pytest.raises(httpx.HTTPStatusError):
        _ = [token async for token in OllamaProvider().stream_chat([{'role': 'user', 'content': 'hello'}])]


@pytest.mark.asyncio
async def test_queue_recovers_after_rejected_waiter():
    import fastapi
    queue = LocalInferenceQueue(capacity=1, wait_seconds=0.01)
    await queue.acquire()
    with pytest.raises(fastapi.HTTPException) as exc:
        await queue.acquire()
    assert exc.value.status_code == 503
    assert queue.snapshot()['waiting'] == 0
    queue.release()
    await queue.acquire()
    queue.release()
    assert queue.snapshot()['running'] == 0


def migration_module():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'migrate.py'
    spec = importlib.util.spec_from_file_location('safe_migrations', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_sequence_and_outer_transactions_removed():
    module = migration_module()
    names = [path.name for path in module.migration_files()]
    assert len(names) >= 9
    assert names[0].startswith('001_') and names[-1].startswith('014_')
    assert module.statements('BEGIN;\nCREATE TABLE x (id INTEGER);\nCOMMIT;') == 'CREATE TABLE x (id INTEGER);'


def test_migration_runner_requires_explicit_database(monkeypatch):
    module = migration_module()
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('TEST_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='Set DATABASE_URL'):
        module.database_dsn()
