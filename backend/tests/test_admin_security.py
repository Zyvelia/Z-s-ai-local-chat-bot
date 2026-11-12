"""v0.9 DB-free authorization/contract tests; integration testing deferred to v1.0."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
import sys
from types import ModuleType
mock_db = ModuleType('app.core.db')
async def get_db():
    yield None
mock_db.get_db = get_db
sys.modules.setdefault('app.core.db', mock_db)
mock_security = ModuleType('app.core.security')
async def current_user():
    return None
mock_security.current_user = current_user
mock_security.authenticated_user = current_user
sys.modules.setdefault('app.core.security', mock_security)
from app.api.admin import require_admin, router, audit, restrict_user, moderate_character, appeal
from app.api.admin_schemas import UserRestriction, CharacterModeration, ReportDecision, AppealSubmission, AppealDecision
from app.core.ratelimit import hit, rules, _hits
from app.models.entities import Base, AuditLog, User, Character, ModerationAppeal


def test_admin_role_is_server_enforced():
    with pytest.raises(HTTPException) as exc:
        require_admin(SimpleNamespace(role='member'))
    assert exc.value.status_code == 403
    assert require_admin(SimpleNamespace(role='admin')).role == 'admin'


def test_permission_sensitive_routes():
    paths = {(r.path, m) for r in router.routes for m in getattr(r, 'methods', ())}
    for method, path in [
        ('GET','/api/v1/admin/dashboard'), ('GET','/api/v1/admin/users'),
        ('PUT','/api/v1/admin/users/{user_id}/restriction'),
        ('PUT','/api/v1/admin/characters/{character_id}/moderation'),
        ('GET','/api/v1/admin/reports'), ('PUT','/api/v1/admin/reports/{report_id}'),
        ('GET','/api/v1/admin/appeals'), ('PUT','/api/v1/admin/appeals/{appeal_id}'),
        ('GET','/api/v1/admin/audit'), ('POST','/api/v1/appeals'),
        ('GET','/api/v1/appeals/mine'), ('GET','/api/v1/privacy/export'),
        ('DELETE','/api/v1/privacy/account'),
    ]:
        assert (path, method) in paths


def test_validation():
    assert UserRestriction(suspend=True, days=7, reason='spam').days == 7
    with pytest.raises(ValidationError): UserRestriction(suspend=True, days=500)
    with pytest.raises(ValidationError): CharacterModeration(status='secret', reason='spam')
    with pytest.raises(ValidationError): CharacterModeration(status='hidden', reason='x')
    with pytest.raises(ValidationError): ReportDecision(status='unknown')
    with pytest.raises(ValidationError): AppealSubmission(reason='short')
    with pytest.raises(ValidationError): AppealDecision(status='accepted', response='x')


def test_schema_migration_and_fk():
    sql = (Path(__file__).parents[1]/'migrations'/'009_administration_security.sql').read_text()
    for table in ('audit_logs','moderation_appeals'):
        assert table in Base.metadata.tables
        assert 'CREATE TABLE IF NOT EXISTS '+table in sql
    for col in ('role','is_suspended','suspended_until','suspension_reason'):
        assert col in Base.metadata.tables['users'].columns
        assert col in sql
    assert 'moderation_status' in Base.metadata.tables['characters'].columns
    assert 'moderation_status' in sql
    for t in (AuditLog, ModerationAppeal):
        str(t.__table__.compile(dialect=postgresql.dialect()))


def test_rate_limiting_and_window_expiry():
    _hits.clear()
    key='security-unit-test-unique'
    assert hit(key, 2, 60, now=10) == (True, 0)
    assert hit(key, 2, 60, now=11) == (True, 0)
    allowed, retry = hit(key, 2, 60, now=12)
    assert not allowed and retry > 0
    assert hit(key, 2, 60, now=70)[0] is True
    assert rules('GET','/api/v1/characters') is None
    assert rules('POST','/api/v1/auth/login') == (10,60)
    assert rules('POST','/api/v1/appeals') == (5,3600)


class FakeDB:
    def __init__(self, target=None, count=0):
        self.target = target
        self.count = count
        self.added=[]
        self.commits=0
    async def get(self, model, pk): return self.target
    async def scalar(self, stmt): return self.count
    def add(self, item): self.added.append(item)
    async def commit(self): self.commits += 1


def test_audit_never_embeds_passwords():
    db=FakeDB()
    audit(db, SimpleNamespace(id='a'), 'test', 'user', 'target')
    assert db.added[0].actor_id == 'a'
    assert db.added[0].details == {}


@pytest.mark.asyncio
async def test_restriction_and_audit():
    admin = SimpleNamespace(id='admin', role='admin')
    target = SimpleNamespace(id='user', role='member', is_suspended=False, suspended_until=None, suspension_reason='')
    db=FakeDB(target)
    response = await restrict_user('user', UserRestriction(suspend=True, reason='abuse'), admin, db)
    assert response['status'] == 'suspended'
    assert target.is_suspended
    assert any(isinstance(x, AuditLog) for x in db.added)
    assert db.commits == 1
    with pytest.raises(HTTPException) as exc:
        await restrict_user('user', UserRestriction(suspend=True), admin, FakeDB(SimpleNamespace(role='admin')))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_character_moderation():
    admin=SimpleNamespace(id='admin')
    c=SimpleNamespace(moderation_status='active')
    db=FakeDB(c)
    response=await moderate_character('c', CharacterModeration(status='hidden', reason='violent content'), admin, db)
    assert response == {'status':'hidden'}
    assert c.moderation_status == 'hidden'
    assert db.commits == 1


@pytest.mark.asyncio
async def test_appeals_ownership():
    db=FakeDB(SimpleNamespace(creator_id='other', moderation_status='hidden'))
    with pytest.raises(HTTPException) as exc:
        await appeal(AppealSubmission(character_id='c',reason='I would like a review of this decision'), SimpleNamespace(id='owner'), db)
    assert exc.value.status_code == 404
