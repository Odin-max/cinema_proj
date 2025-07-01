import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.db.base import Base
from app.db.session import get_db
from app.routes.stars.stars import router as stars_router
from app.core.security import get_current_user, get_current_moderator
from app.models.movie_models import StarModel


@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True, echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def session(engine):
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="function")
def app(session):
    app = FastAPI()
    app.include_router(stars_router)

    app.dependency_overrides[get_db] = lambda: session

    class User:
        def __init__(self, id): self.id = id
    app.dependency_overrides[get_current_user] = lambda: User(id=1)
    app.dependency_overrides[get_current_moderator] = lambda: None

    return app

@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_create_star_success(client, session):
    r = await client.post("/stars/", json={"name": "Alice"})
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert data["name"] == "Alice"
    all_stars = (await session.execute(select(StarModel))).scalars().all()
    assert any(s.name == "Alice" for s in all_stars)

@pytest.mark.anyio
async def test_create_star_duplicate(client, session):
    session.add(StarModel(name="Bob"))
    await session.commit()
    r = await client.post("/stars/", json={"name": "Bob"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in r.json()["detail"]

@pytest.mark.anyio
async def test_list_stars_empty(client):
    r = await client.get("/stars/")
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == []

@pytest.mark.anyio
async def test_list_stars_some(client, session):
    session.add_all([StarModel(name="X"), StarModel(name="Y")])
    await session.commit()
    r = await client.get("/stars/")
    assert r.status_code == status.HTTP_200_OK
    names = [item["name"] for item in r.json()]
    assert set(names) == {"X", "Y"}

@pytest.mark.anyio
async def test_get_star_not_found(client):
    r = await client.get("/stars/123")
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_get_star_success(client, session):
    s = StarModel(name="Zoe")
    session.add(s)
    await session.commit()
    r = await client.get(f"/stars/{s.id}")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == s.id
    assert data["name"] == "Zoe"

@pytest.mark.anyio
async def test_update_star_not_found(client):
    r = await client.put("/stars/999", json={"name": "NewName"})
    assert r.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_update_star_duplicate(client, session):
    a = StarModel(name="A")
    b = StarModel(name="B")
    session.add_all([a, b])
    await session.commit()
    r = await client.put(f"/stars/{b.id}", json={"name": "A"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "already in use" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_update_star_success(client, session):
    s = StarModel(name="Old")
    session.add(s)
    await session.commit()
    r = await client.put(f"/stars/{s.id}", json={"name": "NewName"})
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["name"] == "NewName"
    refreshed = await session.get(StarModel, s.id)
    assert refreshed.name == "NewName"

@pytest.mark.anyio
async def test_delete_star_not_found(client):
    r = await client.delete("/stars/888")
    assert r.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_delete_star_success(client, session):
    s = StarModel(name="ToRemove")
    session.add(s)
    await session.commit()
    r = await client.delete(f"/stars/{s.id}")
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert await session.get(StarModel, s.id) is None
