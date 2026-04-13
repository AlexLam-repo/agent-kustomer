from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
import os

def _build_url() -> str:
    # Intenta DATABASE_URL primero (Railway lo inyecta automáticamente)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+aiomysql://", 1)
        return url
    # Fallback: construir desde partes
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "password")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "agent_kustomer")
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}"


def get_engine() -> AsyncEngine:
    url = _build_url()
    return create_async_engine(url, echo=False, pool_pre_ping=True, pool_recycle=3600)


def get_session_factory(engine: AsyncEngine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    engine = get_engine()
    factory = get_session_factory(engine)
    async with factory() as session:
        yield session


# Para uso directo en background tasks
AsyncSessionLocal = None

def init_session_local():
    global AsyncSessionLocal
    engine = get_engine()
    AsyncSessionLocal = get_session_factory(engine)
    return AsyncSessionLocal


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
