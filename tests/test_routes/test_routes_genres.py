import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.routes.genres.genres import router as genres_router
from app.db.session import get_db
from app.core.security import get_current_user, get_current_moderator
from app.models.movie_models import GenreModel

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
def app(session, monkeypatch):
    app = FastAPI()
    app.include_router(genres_router)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: None
    app.dependency_overrides[get_current_moderator] = lambda: None

    return app

@pytest.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_create_genre_success(client: AsyncClient):
    r = await client.post("/genres/", json={"name": "Action"})
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert isinstance(data["id"], int)
    assert data["name"] == "Action"

@pytest.mark.anyio
async def test_create_genre_duplicate(client: AsyncClient, session: AsyncSession):
    session.add(GenreModel(name="Horror"))
    await session.commit()

    r = await client.post("/genres/", json={"name": "Horror"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_list_and_get_genre(client: AsyncClient, session: AsyncSession):
    g1 = GenreModel(name="Drama")
    g2 = GenreModel(name="Comedy")
    session.add_all([g1, g2])
    await session.commit()

    r = await client.get("/genres/")
    assert r.status_code == status.HTTP_200_OK
    names = {g["name"] for g in r.json()}
    assert names == {"Drama", "Comedy"}

    r = await client.get(f"/genres/{g1.id}")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == g1.id
    assert data["name"] == "Drama"

    r = await client.get("/genres/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_update_genre(client: AsyncClient, session: AsyncSession):
    g = GenreModel(name="Thriller")
    session.add(g)
    await session.commit()

    r = await client.put(f"/genres/{g.id}", json={"name": "Sci-Fi"})
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["name"] == "Sci-Fi"

    other = GenreModel(name="Romance")
    session.add(other)
    await session.commit()
    r = await client.put(f"/genres/{g.id}", json={"name": "Romance"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "in use" in r.json()["detail"].lower()

    r = await client.put("/genres/999", json={"name": "X"})
    assert r.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_delete_genre(client: AsyncClient, session: AsyncSession):
    g = GenreModel(name="Documentary")
    session.add(g)
    await session.commit()

    r = await client.delete(f"/genres/{g.id}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    r = await client.get(f"/genres/{g.id}")
    assert r.status_code == status.HTTP_404_NOT_FOUND

    r = await client.delete("/genres/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
