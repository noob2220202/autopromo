from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL
from db.models import Base

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


def _existing_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _add_missing_columns(conn) -> None:
    if conn.dialect.name != "sqlite":
        return
    for table in Base.metadata.sorted_tables:
        existing = _existing_columns(conn, table.name)
        if not existing:
            continue
        for column in table.columns:
            if column.name in existing:
                continue
            ddl_type = column.type.compile(dialect=conn.dialect)
            conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session
