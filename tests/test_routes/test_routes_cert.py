import pytest
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.routes.certifications.certifications import router as cert_router
from app.db.session import get_db
from app.core.security import get_current_user, get_current_moderator
from app.models.movie_models import CertificationModel


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
    app.include_router(cert_router)

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
async def test_create_certification_success(client: AsyncClient):
    payload = {"name": "PG-13"}
    r = await client.post("/certifications/", json=payload)
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert isinstance(data["id"], int)
    assert data["name"] == "PG-13"

@pytest.mark.anyio
async def test_create_certification_duplicate(client: AsyncClient, session: AsyncSession):
    session.add(CertificationModel(name="R"))
    await session.commit()

    r = await client.post("/certifications/", json={"name": "R"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_list_and_get_certifications(client: AsyncClient, session: AsyncSession):
    c1 = CertificationModel(name="A")
    c2 = CertificationModel(name="B")
    session.add_all([c1, c2])
    await session.commit()

    r = await client.get("/certifications/")
    assert r.status_code == status.HTTP_200_OK
    names = {c["name"] for c in r.json()}
    assert names == {"A", "B"}

    r = await client.get(f"/certifications/{c1.id}")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == c1.id
    assert data["name"] == "A"

    r = await client.get("/certifications/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in r.json()["detail"].lower()

@pytest.mark.anyio
async def test_update_certification(client: AsyncClient, session: AsyncSession):
    c = CertificationModel(name="Old")
    session.add(c)
    await session.commit()

    r = await client.put(f"/certifications/{c.id}", json={"name": "New"})
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["name"] == "New"

    other = CertificationModel(name="Exists")
    session.add(other)
    await session.commit()
    r = await client.put(f"/certifications/{c.id}", json={"name": "Exists"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "in use" in r.json()["detail"].lower()

    r = await client.put("/certifications/999", json={"name": "X"})
    assert r.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_delete_certification(client: AsyncClient, session: AsyncSession):
    c = CertificationModel(name="ToDelete")
    session.add(c)
    await session.commit()

    r = await client.delete(f"/certifications/{c.id}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    r = await client.get(f"/certifications/{c.id}")
    assert r.status_code == status.HTTP_404_NOT_FOUND

    r = await client.delete("/certifications/999")
    assert r.status_code == status.HTTP_404_NOT_FOUND
