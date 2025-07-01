import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import insert, select
from app.core.config import settings
from app.db.base import Base
from app.models.user_models import UserGroup

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+pg8000://"
    f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_DB_PORT}"
    f"/{settings.POSTGRES_DB}"
)

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for id_, name in [(1, "USER"), (2, "MODERATOR"), (3, "ADMIN")]:
            exists = await conn.execute(select(UserGroup).where(UserGroup.id == id_))
            if not exists.scalar_one_or_none():
                await conn.execute(insert(UserGroup).values(id=id_, name=name))