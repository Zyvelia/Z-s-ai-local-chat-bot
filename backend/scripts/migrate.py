"""Transactional PostgreSQL upgrades, migration checksums, and repeatable CI.

Usage: DATABASE_URL=postgresql+asyncpg://... python backend/scripts/migrate.py
       DATABASE_URL=... python backend/scripts/migrate.py --verify-only

Only run on a fresh DB, or one previously managed by this runner.
For pre-v1.1 databases upgraded using manual SQL, see README.md (Database migrations and upgrade instructions).
"""
import argparse
import asyncio
import hashlib
import os
import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'
LOCK_ID = 11810229


def migration_files():
    files = sorted(MIGRATIONS.glob('[0-9][0-9][0-9]_*.sql'))
    numbers = [int(file.name.split('_', 1)[0]) for file in files]
    if numbers != list(range(1, len(numbers) + 1)):
        raise RuntimeError('Missing or duplicate migration number')
    return files


def statements(sql):
    # Historical scripts use BEGIN/COMMIT around otherwise ordinary SQL.
    # Remove only complete outer transaction lines and run all SQL under our
    # own transaction, including the tracking ledger write.
    return re.sub(r'(?im)^\s*(BEGIN|COMMIT);\s*$', '', sql).strip()


def database_dsn():
    raw = os.getenv('DATABASE_URL') or os.getenv('TEST_DATABASE_URL')
    if not raw:
        raise RuntimeError('Set DATABASE_URL to an explicit PostgreSQL database')
    return raw.replace('postgresql+asyncpg://', 'postgresql://', 1)


async def migrate(*, verify_only=False):
    import asyncpg
    conn = await asyncpg.connect(database_dsn())
    try:
        await conn.execute('SELECT pg_advisory_lock($1)', LOCK_ID)
        try:
            has_ledger = await conn.fetchval("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
            if verify_only and not has_ledger:
                raise RuntimeError('Migration ledger does not exist')
            if not verify_only and not has_ledger:
                # Fail closed for databases that were manually upgraded in
                # older releases, rather than replaying the initial schema.
                existing_tables = await conn.fetchval("""SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'""")
                if existing_tables:
                    raise RuntimeError('Existing database has no migration ledger; see README.md (Database migrations and upgrade instructions)')
            if not verify_only:
                await conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY, filename TEXT NOT NULL,
                    sha256 CHAR(64) NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            applied = {row['version']: row for row in await conn.fetch('SELECT * FROM schema_migrations')} if has_ledger or not verify_only else {}
            for file in migration_files():
                version = int(file.name[:3]); sql = file.read_text(encoding='utf-8')
                checksum = hashlib.sha256(sql.encode('utf-8')).hexdigest()
                if version in applied:
                    previous = applied[version]
                    if previous['sha256'] != checksum or previous['filename'] != file.name:
                        raise RuntimeError(f'Migration {file.name} changed since it was applied')
                    print('Verified', file.name)
                    continue
                if verify_only:
                    raise RuntimeError(f'Migration not applied: {file.name}')
                async with conn.transaction():
                    await conn.execute(statements(sql))
                    await conn.execute('INSERT INTO schema_migrations(version, filename, sha256) VALUES ($1, $2, $3)', version, file.name, checksum)
                print('Applied', file.name)
            unknown = set(applied) - {int(f.name[:3]) for f in migration_files()}
            if unknown:
                raise RuntimeError(f'Unknown migration versions: {sorted(unknown)}')
        finally:
            await conn.execute('SELECT pg_advisory_unlock($1)', LOCK_ID)
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    asyncio.run(migrate(verify_only=args.verify_only))
