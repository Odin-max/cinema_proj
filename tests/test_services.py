import uuid
import pytest
from datetime import datetime, timedelta

from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select

from app.db.base import Base
from app.services import auth as auth_router
from app.core import security as auth_service
from app.core.config import settings
from app.models.user_models import (
    User,
    ActivationToken,
    RefreshToken,
    PasswordResetToken,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True, echo=False
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def session(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session
        await session.close()


@pytest.fixture(scope="function")
def app(session, monkeypatch):
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/auth")

    app.dependency_overrides[auth_router.get_db] = lambda: session

    monkeypatch.setattr(auth_router, "send_activation_email", lambda email, token: None)
    monkeypatch.setattr(
        auth_router, "send_password_reset_email", lambda email, token: None
    )

    return app


@pytest.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_register_activate_login_refresh_logout(
    client: AsyncClient, session: AsyncSession
):
    resp = await client.post(
        "/auth/register", json={"email": "foo@example.com", "password": "secret123"}
    )
    assert resp.status_code == status.HTTP_201_CREATED

    row = (
        await session.execute(
            select(ActivationToken).options(selectinload(ActivationToken.user))
        )
    ).scalar_one()
    assert row.user.email == "foo@example.com"
    token = row.token

    resp = await client.get(f"/auth/activate?token={token}")
    assert resp.status_code == 200
    assert "activated" in resp.json()["message"].lower()

    resp = await client.post(
        "/auth/login", data={"username": "foo@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body

    rt = body["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert resp.status_code == 200
    new = resp.json()
    assert "access_token" in new and "refresh_token" in new
    assert new["refresh_token"] == rt

    resp = await client.post("/auth/logout", json={"refresh_token": rt})
    assert resp.status_code == 200
    remaining = (
        (await session.execute(select(RefreshToken).where(RefreshToken.token == rt)))
        .scalars()
        .all()
    )
    assert remaining == []


@pytest.mark.anyio
async def test_resend_activation(client: AsyncClient, session: AsyncSession):
    user = User(
        email="bar@example.com",
        hashed_password="hash",
        is_active=False,
        group_id=auth_service.settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.commit()

    old = ActivationToken(
        user_id=user.id,
        token=str(uuid.uuid4()),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    session.add(old)
    await session.commit()

    resp = await client.post(
        "/auth/resend-activation", json={"email": "bar@example.com"}
    )
    assert resp.status_code == 200
    tokens = (
        (
            await session.execute(
                select(ActivationToken).where(ActivationToken.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(tokens) == 1
    assert tokens[0].token != old.token


@pytest.mark.anyio
async def test_forgot_and_reset_password(client: AsyncClient, session: AsyncSession):
    user = User(
        email="baz@example.com",
        hashed_password=auth_service.hash_password("oldpass"),
        is_active=True,
        group_id=auth_service.settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.commit()

    resp = await client.post("/auth/forgot-password", json={"email": "baz@example.com"})
    assert resp.status_code == status.HTTP_200_OK

    prt = (
        await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
    ).scalar_one()
    token = prt.token

    resp = await client.get(f"/auth/password/reset?token={token}")
    assert resp.status_code == 200
    assert "<form" in resp.text

    resp = await client.post(
        "/auth/password/reset", data={"token": token, "new_password": "newsecret"}
    )
    assert resp.status_code == status.HTTP_200_OK

    dbu = await session.get(User, user.id)
    assert auth_service.verify_password("newsecret", dbu.hashed_password)


@pytest.mark.anyio
async def test_activate_via_post(client: AsyncClient, session: AsyncSession):
    user = User(
        email="z@e.com",
        hashed_password=auth_service.hash_password("pass123"),
        is_active=False,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.flush()
    tok = str(uuid.uuid4())
    activation = ActivationToken(
        user_id=user.id,
        token=tok,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    session.add(activation)
    await session.commit()
    resp = await client.post("/auth/activate", json={"token": tok})
    assert resp.status_code == status.HTTP_200_OK
    assert "activated" in resp.json()["message"].lower()
    remaining = (await session.execute(select(ActivationToken))).scalars().all()
    assert remaining == []

    db_user = await session.get(User, user.id)
    assert db_user.is_active


@pytest.mark.anyio
async def test_read_me(client: AsyncClient, session: AsyncSession):
    user = User(
        email="me@e.com",
        hashed_password=auth_service.hash_password("pwd"),
        is_active=True,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.flush()
    access = auth_router.create_access_token(
        subject=str(user.id), expires_delta=timedelta(minutes=5)
    )
    r = await client.get("/auth/me")
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["email"] == "me@e.com"


@pytest.mark.anyio
async def test_login_errors(client: AsyncClient, session: AsyncSession):

    r = await client.post("/auth/login", data={"username": "x@x.com", "password": "x"})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    user = User(
        email="in@e.com",
        hashed_password=auth_service.hash_password("pw"),
        is_active=False,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.commit()
    r = await client.post(
        "/auth/login", data={"username": "in@e.com", "password": "pw"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.anyio
async def test_refresh_expired(client: AsyncClient, session: AsyncSession):
    rt = RefreshToken(
        user_id=1,
        token=str(uuid.uuid4()),
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    session.add(rt)
    await session.commit()
    r = await client.post("/auth/refresh", json={"refresh_token": rt.token})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_forgot_clears_old_tokens(client: AsyncClient, session: AsyncSession):
    user = User(
        email="fz@e.com",
        hashed_password=auth_service.hash_password("pw"),
        is_active=True,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.commit()
    old = PasswordResetToken(
        user_id=user.id,
        token=str(uuid.uuid4()),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    session.add(old)
    await session.commit()

    r = await client.post("/auth/forgot-password", json={"email": "fz@e.com"})
    assert r.status_code == status.HTTP_200_OK
    all_tokens = (await session.execute(select(PasswordResetToken))).scalars().all()
    assert len(all_tokens) == 1
    assert all_tokens[0].token != old.token


@pytest.mark.anyio
async def test_password_reset_submit_invalid(
    client: AsyncClient, session: AsyncSession
):
    r = await client.post(
        "/auth/password/reset", data={"token": "bad", "new_password": "x"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    user = User(
        email="pr@e.com",
        hashed_password=auth_service.hash_password("pw"),
        is_active=True,
        group_id=settings.DEFAULT_GROUP_ID,
    )
    session.add(user)
    await session.commit()
    exp = PasswordResetToken(
        user_id=user.id,
        token=str(uuid.uuid4()),
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    session.add(exp)
    await session.commit()
    r = await client.post(
        "/auth/password/reset", data={"token": exp.token, "new_password": "xyz"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.anyio
async def test_error_cases(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "dup@e.com", "password": "secret123"}
    )
    r = await client.post(
        "/auth/register", json={"email": "dup@e.com", "password": "secret123"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    r = await client.get("/auth/activate")
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    r = await client.post("/auth/login", data={"username": "x@x.com", "password": "x"})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    r = await client.post("/auth/refresh", json={"refresh_token": "bad"})
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    r = await client.post("/auth/logout", json={"refresh_token": "none"})
    assert r.status_code == status.HTTP_200_OK

    r = await client.post("/auth/forgot-password", json={"email": "nosuch@u.com"})
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    r = await client.get("/auth/password/reset?token=bad")
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    r = await client.post(
        "/auth/password/reset", data={"token": "bad", "new_password": "x"}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
