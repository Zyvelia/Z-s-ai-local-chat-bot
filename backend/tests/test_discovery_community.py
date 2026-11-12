"""v0.7 focused validation, query construction, authorization and migration checks.

These tests are intentionally DB-independent; full Postgres/Ollama integration is
still needed before shipping a public platform.
"""
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
# Offline test environment omits asyncpg and pwdlib; stub dependency injection
# functions for DB-free route/schema tests. Runtime installs full requirements.
mock_db = ModuleType('app.core.db')
async def get_db():
    yield None
mock_db.get_db = get_db
sys.modules.setdefault('app.core.db', mock_db)
mock_security = ModuleType('app.core.security')
async def current_user():
    return None
mock_security.current_user = current_user
sys.modules.setdefault('app.core.security', mock_security)
from app.api.community import router, escape_like, available_character, mine_collection, build_discovery
from app.api.community_schemas import ProfileEdit, CollectionIn, RatingIn, ReportIn, SearchPage
from app.models.entities import (Base, UserProfile, Favorite, Collection, CollectionItem,
    CreatorFollow, CharacterRating, CommunityReport)


def test_profile_handle_validation_and_avatar():
    assert ProfileEdit(handle='  Alice_123  ').handle == 'alice_123'
    for name in ('2alice', 'a', 'bad space', '__private', 'A@B'):
        with pytest.raises(ValidationError):
            ProfileEdit(handle=name)
    with pytest.raises(ValidationError):
        ProfileEdit(handle='validname', avatar_url='http://insecure.example/a.png')


def test_collections_ratings_and_reports_validate():
    assert CollectionIn(title='Favorites').description == ''
    for bad in (0, 6):
        with pytest.raises(ValidationError):
            RatingIn(stars=bad)
    for bad in ('bogus', 'other!'):
        with pytest.raises(ValidationError):
            ReportIn(reason=bad)
    assert ReportIn(reason='spam', details='test').reason == 'spam'


def test_discovery_pagination_payload():
    page = SearchPage(items=[dict(id='x', creator_id='u', name='A', tagline='', tags=[],
        favorites=2, chats=1, average_rating=None, rating_count=0)], total=1, limit=20, offset=0)
    assert page.items[0].average_rating is None
    assert page.total == 1


def test_like_query_escaping():
    assert escape_like('100%_safe!') == '100!%!_safe!!'


def test_models_constraints_and_tables():
    tables = Base.metadata.tables
    for name in ('user_profiles', 'character_favorites', 'character_collections',
                 'collection_items', 'creator_follows', 'character_ratings', 'community_reports'):
        assert name in tables
    for t in (Favorite, CollectionItem, CreatorFollow, CharacterRating):
        assert len(t.__table__.primary_key.columns) == 2
    assert 'status' in CommunityReport.__table__.columns
    assert 'handle' in UserProfile.__table__.columns


def test_api_routes_exposed():
    routes = {(getattr(r, 'path', ''), method) for r in router.routes for method in getattr(r, 'methods', set())}
    for method, path in [
        ('GET','/api/v1/characters/discover'), ('GET','/api/v1/creators/{creator_id}'),
        ('PUT','/api/v1/creators/me'), ('POST','/api/v1/creators/{creator_id}/follow'),
        ('DELETE','/api/v1/creators/{creator_id}/follow'),
        ('GET','/api/v1/favorites'), ('POST','/api/v1/favorites/{character_id}'),
        ('GET','/api/v1/collections'), ('POST','/api/v1/collections'),
        ('POST','/api/v1/collections/{collection_id}/characters/{character_id}'),
        ('PUT','/api/v1/characters/{character_id}/rating'),
        ('POST','/api/v1/characters/{character_id}/reports'),
    ]:
        assert (path, method) in routes


class FakeDB:
    def __init__(self, item):
        self.item = item
    async def get(self, cls, id):
        return self.item


@pytest.mark.asyncio
async def test_private_character_is_not_exposed():
    db = FakeDB(SimpleNamespace(is_public=False, creator_id='owner'))
    with pytest.raises(HTTPException) as exc:
        await available_character(db, 'character', viewer_id='stranger')
    assert exc.value.status_code == 404
    assert (await available_character(db, 'character', viewer_id='owner')).creator_id == 'owner'


@pytest.mark.asyncio
async def test_private_collection_is_not_exposed():
    db = FakeDB(SimpleNamespace(user_id='owner'))
    with pytest.raises(HTTPException) as exc:
        await mine_collection(db, 'collection', 'stranger')
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_discovery_query_has_public_visibility_and_limits():
    class FakeResult:
        def all(self): return []
    class CaptureDB:
        def __init__(self): self.queries=[]
        async def scalar(self, sql): self.queries.append(sql); return 0
        async def execute(self, sql): self.queries.append(sql); return FakeResult()
    db = CaptureDB()
    out = await build_discovery(db, query='wizard', tag='fantasy', limit=10, offset=20, sort='popular')
    assert out == {'items': [], 'total': 0, 'limit': 10, 'offset': 20}
    sql = '\n'.join(str(q.compile(dialect=postgresql.dialect())) for q in db.queries)
    assert 'characters.is_public IS true' in sql
    assert 'OFFSET' in sql


def test_migration_has_existing_schema_guards():
    file = Path(__file__).parents[1] / 'migrations' / '007_discovery_community.sql'
    sql = file.read_text()
    for name in ('user_profiles', 'character_favorites', 'character_collections',
                 'collection_items', 'creator_follows', 'character_ratings', 'community_reports'):
        assert 'CREATE TABLE IF NOT EXISTS ' + name in sql
    assert 'BEGIN;' in sql and 'COMMIT;' in sql
