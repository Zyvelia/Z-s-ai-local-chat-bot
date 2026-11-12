"""Offline synchronization contracts; do not require a running PostgreSQL server."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from hashlib import sha256
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable
from app.api.offline_sync import SafeMetadataEdit, apply_metadata_edit, get_sync_state
from app.models.entities import Base, SyncMutation, Conversation


def test_offline_edits_are_narrow_and_validated():
    base = {'operation_id': str(uuid4()), 'base_revision': 0}
    for overrides in ({}, {'title': ' ' * 121}, {'auto_memory': True}, {'base_revision': -1}, {'is_archived': 'not a boolean'}):
        with pytest.raises(ValidationError):
            SafeMetadataEdit(**(base | overrides))
    assert SafeMetadataEdit(**(base | {'title': 'Morning chat'})).title == 'Morning chat'
    assert SafeMetadataEdit(**(base | {'is_archived': False})).is_archived is False


def test_migration_and_orm_match():
    ddl = (Path(__file__).resolve().parents[1] / 'migrations' / '014_offline_sync.sql').read_text()
    assert 'metadata_revision' in ddl and 'sync_mutations' in ddl
    assert 'REFERENCES users(id) ON DELETE CASCADE' in ddl
    assert 'REFERENCES conversations(id) ON DELETE CASCADE' in ddl
    assert 'CREATE TABLE sync_mutations' in str(CreateTable(SyncMutation.__table__).compile(dialect=dialect()))
    assert 'metadata_revision' in Conversation.__table__.columns
    assert set(Base.metadata.tables).issuperset({'conversations', 'sync_mutations'})


class ScalarResult:
    def __init__(self, value): self.value = value
    def scalar_one_or_none(self): return self.value


@pytest.mark.asyncio
async def test_account_isolation_before_sync_write():
    fake = AsyncMock()
    fake.scalar.return_value = None
    user = SimpleNamespace(id='other-user')
    with pytest.raises(HTTPException) as exc:
        await apply_metadata_edit('not-my-chat', SafeMetadataEdit(operation_id=uuid4(), base_revision=0, title='Nope'), user, fake)
    assert exc.value.status_code == 404
    fake.execute.assert_not_awaited()
    with pytest.raises(HTTPException) as exc:
        await get_sync_state('not-my-chat', user, fake)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rejected_stale_edit_returns_remote_state():
    chat = SimpleNamespace(id='chat1', title='Other device title', is_archived=True, metadata_revision=4)
    fake = AsyncMock()
    fake.scalar.return_value = chat
    fake.get.return_value = None
    fake.execute.return_value = ScalarResult(None)
    with pytest.raises(HTTPException) as exc:
        await apply_metadata_edit('chat1', SafeMetadataEdit(operation_id=uuid4(), base_revision=3, title='Local title'),
                                  SimpleNamespace(id='user1'), fake)
    assert exc.value.status_code == 409
    assert exc.value.detail['code'] == 'revision_conflict'
    assert exc.value.detail['server']['metadata_revision'] == 4
    fake.rollback.assert_awaited_once()
    fake.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_idempotent_replay_does_not_repeat_mutation():
    uid = uuid4()
    chat = SimpleNamespace(id='chat1', title='Already saved', is_archived=False, metadata_revision=9)
    fake = AsyncMock()
    fake.scalar.return_value = chat
    payload = SafeMetadataEdit(operation_id=uid, base_revision=8, title='Already saved')
    digest = sha256(json.dumps(payload.model_dump(mode='json', exclude={'operation_id'}), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    fake.get.return_value = SimpleNamespace(id=str(uid), user_id='user1', conversation_id='chat1', base_revision=8, payload_digest=digest, resulting_revision=9)
    result = await apply_metadata_edit('chat1', SafeMetadataEdit(operation_id=uid, base_revision=8, title='Already saved'),
                                       SimpleNamespace(id='user1'), fake)
    assert result['status'] == 'already_applied'
    assert result['applied_revision'] == 9
    fake.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_sync_creates_receipt():
    uid = uuid4()
    chat = SimpleNamespace(id='chat1', title='My title', is_archived=True, metadata_revision=3)
    fake = AsyncMock()
    fake.scalar.return_value = chat
    fake.get.return_value = None
    fake.execute.return_value = ScalarResult('chat1')
    result = await apply_metadata_edit('chat1', SafeMetadataEdit(operation_id=uid, base_revision=2, title='My title'),
                                       SimpleNamespace(id='user1'), fake)
    assert result['status'] == 'applied'
    assert result['applied_revision'] == 3
    fake.add.assert_called_once()
    receipt = fake.add.call_args.args[0]
    assert receipt.id == str(uid)
    fake.commit.assert_awaited_once()
