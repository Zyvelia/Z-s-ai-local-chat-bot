"""Optional live DB + ASGI smoke test. Run separately with TEST_DATABASE_URL set.

No Ollama required: verifies auth, character creation and conversation persistence.
"""
import os
from uuid import uuid4
import pytest

pytestmark = pytest.mark.asyncio


async def test_auth_character_conversation_roundtrip():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL for integration checks')
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core import db as db_module
    # The FastAPI DB engine is created at import; CI sets DATABASE_URL to the same test DB.
    assert db_module.settings.database_url == url, 'DATABASE_URL must match TEST_DATABASE_URL'
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        email = f'ci-{uuid4().hex}@example.org'
        response = await client.post('/api/v1/auth/register', json={
            'email': email, 'password': 'Test-Password-123456!', 'display_name': 'Integration Tester',
        })
        assert response.status_code == 201, response.text
        token = response.json()['access_token']
        auth = {'Authorization': f'Bearer {token}'}
        response = await client.get('/api/v1/users/me', headers=auth)
        assert response.status_code == 200, response.text
        assert response.json()['email'] == email
        # Use the actual public model schema validated by CharacterIn.
        response = await client.post('/api/v1/characters', headers=auth, json={
            'name': 'Test Character', 'personality': 'Friendly and concise',
            'scenario': 'A test room', 'greeting': 'Hello', 'is_public': False,
        })
        assert response.status_code == 201, response.text
        character_id = response.json()['id']
        response = await client.get(f'/api/v1/characters/{character_id}', headers=auth)
        assert response.status_code == 200, response.text
        assert response.json()['name'] == 'Test Character'
        response = await client.get('/api/v1/characters/mine', headers=auth)
        assert response.status_code == 200, response.text
        assert any(item['id'] == character_id for item in response.json())
        response = await client.post('/api/v1/auth/login', json={
            'email': email, 'password': 'Test-Password-123456!',
        })
        assert response.status_code == 200, response.text

async def test_private_chat_and_memory_are_not_visible_to_other_users():
    """Database-backed auth isolation smoke test; CI supplies disposable PostgreSQL."""
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL for integration checks')
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core import db as db_module
    assert db_module.settings.database_url == url
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        async def create_user():
            response = await client.post('/api/v1/auth/register', json={
                'email': f'isolation-{uuid4().hex}@example.org',
                'password': 'Another-Test-Password-123!', 'display_name': 'Tester',
            })
            assert response.status_code == 201, response.text
            return {'Authorization': 'Bearer ' + response.json()['access_token']}
        owner, stranger = await create_user(), await create_user()
        response = await client.post('/api/v1/characters', headers=owner, json={
            'name': 'Private Character', 'personality': 'Reserved',
            'scenario': 'Private testing room', 'greeting': 'Hello', 'is_public': False,
        })
        assert response.status_code == 201, response.text
        character_id = response.json()['id']
        assert (await client.get(f'/api/v1/characters/{character_id}', headers=stranger)).status_code == 404
        response = await client.post('/api/v1/conversations', headers=owner, json={'character_id': character_id})
        assert response.status_code == 201, response.text
        conversation_id = response.json()['id']
        response = await client.post(f'/api/v1/conversations/{conversation_id}/memories', headers=owner, json={'content': 'The hero carries a key'})
        assert response.status_code == 201, response.text
        response = await client.get(f'/api/v1/conversations/{conversation_id}/memories', headers=owner)
        assert response.status_code == 200 and len(response.json()) == 1
        response = await client.get(f'/api/v1/conversations/{conversation_id}/memories', headers=stranger)
        assert response.status_code == 404
        response = await client.get(f'/api/v1/conversations/{conversation_id}/messages', headers=stranger)
        assert response.status_code == 404
