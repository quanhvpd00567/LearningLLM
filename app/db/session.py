from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def create_database(database_url: str):
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise ValueError("DATABASE_URL must use PostgreSQL")
    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg"), pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
