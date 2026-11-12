"""v1.0 API route and migration contracts; does not need running Postgres."""
from pathlib import Path
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from app.models.entities import Base

MIGRATIONS = Path(__file__).parents[1] / 'migrations'


def test_migrations_contiguous_and_transactional():
    files = sorted(MIGRATIONS.glob('[0-9][0-9][0-9]_*.sql'))
    assert [int(p.name[:3]) for p in files] == list(range(1, len(files) + 1))
    assert all('BEGIN;' in p.read_text() and 'COMMIT;' in p.read_text() for p in files)


def test_baseline_contains_only_original_v01_tables():
    source = (MIGRATIONS / '001_initial_v01.sql').read_text()
    for table in ('users', 'characters', 'conversations', 'messages'):
        assert f'CREATE TABLE {table}' in source
    assert 'CREATE TABLE learned_memories' not in source


def test_every_current_table_compiles_for_postgres():
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert 'CREATE TABLE' in ddl


def test_frozen_upgrade_chain_includes_latest_schema():
    migrations = '\n'.join(p.read_text() for p in sorted(MIGRATIONS.glob('[0-9][0-9][0-9]_*.sql')))
    for name in ('conversation_summaries', 'learned_memories', 'personas',
                 'group_participants', 'character_favorites', 'audit_logs', 'moderation_appeals'):
        assert name in migrations
