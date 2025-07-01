import pytest
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import stripe

from app.db.base import Base
from app.routes.cart.carts import router as cart_router
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.movie_models import MovieModel, CertificationModel


class DummyUser:
    id = 1

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
    app.include_router(cart_router)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: DummyUser()

    return app

@pytest.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client

@pytest.mark.anyio
async def test_add_to_and_remove_from_cart(client, session):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()
    movie = MovieModel(
        name="TestMovie", year=2022, time=100,
        imdb=7.0, votes=100, meta_score=70, gross=500000,
        description="desc", price=4.50, certification_id=cert.id
    )
    session.add(movie)
    await session.commit()

    payload = jsonable_encoder({"movie_id": movie.id})
    r = await client.post("/cart/items", json=payload)
    assert r.status_code == status.HTTP_201_CREATED
    cart = r.json()
    assert cart["user_id"] == DummyUser.id
    assert len(cart["items"]) == 1
    assert cart["items"][0]["movie_id"] == movie.id

    r2 = await client.post("/cart/items", json=payload)
    assert r2.status_code == status.HTTP_400_BAD_REQUEST

    r3 = await client.delete(f"/cart/items/{movie.id}")
    assert r3.status_code == status.HTTP_200_OK
    cart2 = r3.json()
    assert cart2["items"] == []

@pytest.mark.anyio
async def test_view_and_clear_cart(client):
    r = await client.get("/cart/")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["items"] == []

    r2 = await client.delete("/cart/clear")
    assert r2.status_code == status.HTTP_200_OK
    assert r2.json()["items"] == []

@pytest.mark.anyio
async def test_checkout_and_order_webhook_and_success(client, session, monkeypatch):
    cert = CertificationModel(name="R")
    session.add(cert)
    await session.commit()
    movie = MovieModel(
        name="CheckoutMovie", year=2021, time=90,
        imdb=8.0, votes=150, meta_score=80, gross=300000,
        description="d", price=5.00, certification_id=cert.id
    )
    session.add(movie)
    await session.commit()

    await client.post("/cart/items", json={"movie_id": movie.id})

    class DummySession:
        url = "https://checkout"
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kw: DummySession())

    r = await client.post("/cart/checkout")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["checkout_url"] == "https://checkout"

    dummy_event = type("E", (), {"type": "checkout.session.completed", "data": type("D", (), {"object": type("O", (), {"metadata": {"order_id": "1"}})})})
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, sig, secret: dummy_event)

    r2 = await client.post("/cart/stripe/webhook", headers={"stripe-signature": "sig"}, content=b"payload")
    assert r2.status_code == status.HTTP_200_OK

    class DummyRetrieve:
        metadata = {"order_id": "1"}
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda session_id: DummyRetrieve())

    r3 = await client.get("/cart/orders/success", params={"session_id": "sess_123"})
    assert r3.status_code == status.HTTP_200_OK
    text = r3.text
    assert "Payment was successful" in text
    assert f"order #1" in text.lower()
