"""Run only when TEST_DATABASE_URL is set, after applying migrations 001-009."""
import os
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.entities import Base

@pytest.mark.asyncio
async def test_upgraded_database_matches_declared_schema():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL after applying 001-009 in CI')
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            tables, columns = await conn.run_sync(lambda sync: (
                set(inspect(sync).get_table_names()),
                {table: set(col['name'] for col in inspect(sync).get_columns(table)) for table in Base.metadata.tables}
            ))
        assert set(Base.metadata.tables).issubset(tables)
        for table in Base.metadata.tables.values():
            assert set(table.columns.keys()).issubset(columns[table.name]), table.name
    finally:
        await engine.dispose()
