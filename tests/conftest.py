import asyncio
import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import event, insert

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.main import app as fastapi_app
from app.db.base import Base
from app.models.user_models import UserGroup
from app.db.session import get_db

@pytest.fixture(scope="session")
def app() -> FastAPI:
    return fastapi_app


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    def _enable_sqlite_fk(dbapi_conn, conn_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
    event.listen(engine.sync_engine, "connect", _enable_sqlite_fk)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                insert(UserGroup).values(id=1, name="default")
            )
        )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(async_engine):

    conn = await async_engine.connect()
    await conn.begin() 
    await conn.begin_nested()

    @event.listens_for(Session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if not trans.nested:
            return
        if trans._parent and not trans._parent.nested:
            sess.begin_nested()

    async with AsyncSession(bind=conn, expire_on_commit=False) as sess:
        yield sess

    await sess.close()
    await conn.rollback()
    await conn.close()


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI, session: AsyncSession):
    async def _override_get_db():
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
