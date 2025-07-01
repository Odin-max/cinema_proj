import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.routes.orders.orders import router as orders_router
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.cart_models import CartModel, CartItemModel
from app.models.movie_models import MovieModel, CertificationModel
from app.models.order_models import OrderModel, OrderStatus



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
    app.include_router(orders_router)

    app.dependency_overrides[get_db] = lambda: session
    class DummyUser:
        id = 1
    app.dependency_overrides[get_current_user] = lambda: DummyUser()
    return app

@pytest.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client

@pytest.mark.anyio
async def test_place_order_empty_cart(client: AsyncClient, session: AsyncSession):
    r = await client.post("/orders/")
    assert r.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.anyio
async def test_place_order_success(client, session):
    cert = CertificationModel(name="PG-13")
    session.add(cert)
    await session.commit()

    movie = MovieModel(
        name="M",
        year=2021,
        time=90,
        imdb=8.0,
        votes=100,
        meta_score=80,
        gross=100000.0,
        description="",
        price=5.5,
        certification_id=cert.id,
    )
    session.add(movie)
    await session.flush()

    cart = CartModel(user_id=1)
    session.add(cart)
    await session.flush()

    ci = CartItemModel(cart_id=cart.id, movie_id=movie.id, quantity=1)
    session.add(ci)
    await session.commit()

    r = await client.post("/orders/")
    assert r.status_code == status.HTTP_201_CREATED

    data = r.json()
    assert "id" in data
    assert data["status"] == OrderStatus.pending.value
    assert float(data["total_amount"]) == 5.5

    assert isinstance(data["items"], list) and len(data["items"]) == 1
    item0 = data["items"][0]
    assert item0["movie_id"] == movie.id
    assert float(item0["price_at_order"]) == 5.5

@pytest.mark.anyio
async def test_list_user_orders(client: AsyncClient, session: AsyncSession):
    o1 = OrderModel(user_id=1, total_amount=1.0, status=OrderStatus.pending)
    o2 = OrderModel(user_id=1, total_amount=2.0, status=OrderStatus.canceled)
    session.add_all([o1, o2])
    await session.commit()

    r = await client.get("/orders/")
    assert r.status_code == status.HTTP_200_OK
    all_orders = r.json()
    assert isinstance(all_orders, list) and len(all_orders) == 2

    r = await client.get(
        "/orders/", params={"status": OrderStatus.pending.value}
    )
    pendings = r.json()
    assert isinstance(pendings, list) and len(pendings) == 1
    assert pendings[0]["status"] == OrderStatus.pending.value

@pytest.mark.anyio
async def test_cancel_order_not_found(client: AsyncClient, session: AsyncSession):
    r = await client.post("/orders/orders/999/cancel")
    assert r.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_cancel_order_success(client: AsyncClient, session: AsyncSession):
    o = OrderModel(user_id=1, total_amount=3.0, status=OrderStatus.pending)
    session.add(o)
    await session.commit()

    r = await client.post(f"/orders/orders/{o.id}/cancel")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == o.id
    assert data["status"] == OrderStatus.canceled.value
