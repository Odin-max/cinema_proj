import pytest
from datetime import timedelta, datetime

from fastapi import FastAPI, Depends, status
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
from httpx import ASGITransport

from app.core.config import settings
from app.models.user_models import User, UserGroup
from app.db.base import Base
from app.core import security


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def session(async_engine) -> AsyncSession:
    SessionLocal = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with SessionLocal() as sess:
        yield sess
        await sess.rollback()


@pytest.fixture(scope="function")
def app(session: AsyncSession):
    app = FastAPI()
    app.dependency_overrides[security.get_db] = lambda: session

    @app.get("/me")
    async def me(u=Depends(security.get_current_user)):
        return {"id": u.id, "email": u.email}

    return app


@pytest.fixture(scope="function")
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_hash_and_verify():
    raw = "supersecret"
    h = security.hash_password(raw)
    assert h != raw
    assert security.verify_password(raw, h)
    assert not security.verify_password("wrong", h)


def test_create_and_decode_access_token():
    token = security.create_access_token("42", expires_delta=timedelta(minutes=5))
    data = jwt.decode(
        token,
        settings.SECRET_KEY_ACCESS,
        algorithms=[settings.JWT_SIGNING_ALGORITHM],
    )
    assert data["sub"] == "42"
    exp = datetime.utcfromtimestamp(data["exp"])
    delta = exp - datetime.utcnow()
    assert timedelta(minutes=4) < delta < timedelta(minutes=6)


@pytest.mark.anyio
async def test_get_current_user_happy_path(client: AsyncClient, session: AsyncSession):
    grp = UserGroup(name="users")
    usr = User(
        email="u@e",
        hashed_password=security.hash_password("x"),
        is_active=True,
        group=grp,
    )
    session.add_all([grp, usr])
    await session.commit()
    await session.refresh(usr)

    token = security.create_access_token(
        str(usr.id), expires_delta=timedelta(minutes=5)
    )
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": usr.id, "email": usr.email}


@pytest.mark.anyio
async def test_get_current_user_bad_token(client: AsyncClient):
    r = await client.get("/me", headers={"Authorization": "Bearer bad.token"})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_get_current_moderator_and_admin(
    client: AsyncClient,
    session: AsyncSession,
    app: FastAPI,
):
    modg = UserGroup(name="moderator")
    adg = UserGroup(name="admin")
    ug = UserGroup(name="user")
    session.add_all([modg, adg, ug])
    await session.commit()

    @app.get("/mod-only")
    async def mod_only(u=Depends(security.get_current_moderator)):
        return {"ok": True}

    @app.get("/admin-only")
    async def admin_only(u=Depends(security.get_current_admin)):
        return {"ok": True}

    async def make_user(group: UserGroup):
        u = User(
            email=f"{group.name}@e",
            hashed_password=security.hash_password("x"),
            is_active=True,
            group=group,
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u

    u_mod = await make_user(modg)
    u_admin = await make_user(adg)
    u_user = await make_user(ug)

    def bearer(u: User) -> str:
        return security.create_access_token(str(u.id))

    r1 = await client.get(
        "/mod-only", headers={"Authorization": f"Bearer {bearer(u_mod)}"}
    )
    r2 = await client.get(
        "/mod-only", headers={"Authorization": f"Bearer {bearer(u_admin)}"}
    )
    r3 = await client.get(
        "/mod-only", headers={"Authorization": f"Bearer {bearer(u_user)}"}
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == status.HTTP_403_FORBIDDEN

    a1 = await client.get(
        "/admin-only", headers={"Authorization": f"Bearer {bearer(u_admin)}"}
    )
    a2 = await client.get(
        "/admin-only", headers={"Authorization": f"Bearer {bearer(u_mod)}"}
    )
    a3 = await client.get(
        "/admin-only", headers={"Authorization": f"Bearer {bearer(u_user)}"}
    )
    assert a1.status_code == 200
    assert a2.status_code == status.HTTP_403_FORBIDDEN
    assert a3.status_code == status.HTTP_403_FORBIDDEN
