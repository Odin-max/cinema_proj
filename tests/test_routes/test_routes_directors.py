import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.routes.directors.directors import router as directors_router
from app.db.session import get_db
from app.core.security import get_current_user, get_current_moderator
from app.models.movie_models import DirectorModel


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
    app.include_router(directors_router)

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
async def test_create_director_success(client: AsyncClient):
    r = await client.post("/directors/", json={"name": "Spielberg"})
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert isinstance(data["id"], int)
    assert data["name"] == "Spielberg"


@pytest.mark.anyio
async def test_create_director_duplicate(client: AsyncClient, session: AsyncSession):
    session.add(DirectorModel(name="Tarantino"))
    await session.commit()

    r = await client.post("/directors/", json={"name": "Tarantino"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in r.json()["detail"].lower()


@pytest.mark.anyio
async def test_list_and_get_directors(client: AsyncClient, session: AsyncSession):
    d1 = DirectorModel(name="Kubrick")
    d2 = DirectorModel(name="Scorsese")
    session.add_all([d1, d2])
    await session.commit()

    r = await client.get("/directors/")
    assert r.status_code == status.HTTP_200_OK
    names = {d["name"] for d in r.json()}
    assert names == {"Kubrick", "Scorsese"}

    r = await client.get(f"/directors/{d1.id}")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == d1.id
    assert data["name"] == "Kubrick"

    r = await client.get("/directors/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.anyio
async def test_update_director(client: AsyncClient, session: AsyncSession):
    d = DirectorModel(name="OldName")
    session.add(d)
    await session.commit()

    r = await client.put(f"/directors/{d.id}", json={"name": "NewName"})
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["name"] == "NewName"

    other = DirectorModel(name="Existing")
    session.add(other)
    await session.commit()
    r = await client.put(f"/directors/{d.id}", json={"name": "Existing"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "in use" in r.json()["detail"].lower()

    r = await client.put("/directors/999", json={"name": "X"})
    assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_delete_director(client: AsyncClient, session: AsyncSession):
    d = DirectorModel(name="ToDelete")
    session.add(d)
    await session.commit()

    r = await client.delete(f"/directors/{d.id}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    r = await client.get(f"/directors/{d.id}")
    assert r.status_code == status.HTTP_404_NOT_FOUND

    r = await client.delete("/directors/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
