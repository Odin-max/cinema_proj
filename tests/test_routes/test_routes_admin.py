import pytest

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.routes.admin.admin_movies import router as admin_router
from app.db.session import get_db
from app.core.security import get_current_moderator

from app.models.movie_models import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from app.models.cart_models import CartModel, CartItemModel
from app.models.order_models import OrderModel
from app.schemas.movie_schema import MovieCreate
from app.schemas.order_schema import OrderStatus


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
    app.include_router(admin_router)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_moderator] = lambda: None

    return app


@pytest.fixture(scope="function")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_create_movie_success(client: AsyncClient, session: AsyncSession):
    cert = CertificationModel(name="PG-13")
    g1, g2 = GenreModel(name="Drama"), GenreModel(name="Comedy")
    s1, s2 = StarModel(name="Alice"), StarModel(name="Bob")
    d1 = DirectorModel(name="Carol")
    session.add_all([cert, g1, g2, s1, s2, d1])
    await session.commit()

    movie = MovieCreate(
        name="My Movie",
        year=2021,
        time=120,
        imdb=7.8,
        votes=1000,
        meta_score=80,
        gross=1000000,
        description="Great film",
        price=9.99,
        certification_id=cert.id,
        genre_ids=[g1.id, g2.id],
        star_ids=[s1.id, s2.id],
        director_ids=[d1.id],
    )
    payload = jsonable_encoder(movie)

    r = await client.post("/admin/create_movie", json=payload)
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()
    assert body["name"] == "My Movie"
    assert set(body.get("genres", [])) == {"Drama", "Comedy"}
    assert set(body.get("stars", [])) == {"Alice", "Bob"}
    assert body.get("directors", []) == ["Carol"]


@pytest.mark.anyio
async def test_create_movie_bad_cert(client: AsyncClient):
    movie = MovieCreate(
        name="NoCert",
        year=2020,
        time=100,
        imdb=6.5,
        votes=500,
        meta_score=60,
        gross=500000,
        description="No cert",
        price=5.00,
        certification_id=999,
    )
    payload = jsonable_encoder(movie)
    r = await client.post("/admin/create_movie", json=payload)
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "Certification not found" in r.text


@pytest.mark.anyio
async def test_create_movie_duplicate(client: AsyncClient, session: AsyncSession):
    cert = CertificationModel(name="R")
    session.add(cert)
    await session.commit()
    m = MovieModel(
        name="Dup",
        year=2022,
        time=90,
        imdb=5.5,
        votes=100,
        meta_score=50,
        gross=100000,
        description="",
        price=4.99,
        certification_id=cert.id,
    )
    session.add(m)
    await session.commit()

    movie = MovieCreate(
        name="Dup",
        year=2022,
        time=90,
        imdb=5.5,
        votes=100,
        meta_score=50,
        gross=100000,
        description="",
        price=4.99,
        certification_id=cert.id,
    )
    payload = jsonable_encoder(movie)

    with pytest.raises(IntegrityError):
        await client.post("/admin/create_movie", json=payload)


@pytest.mark.anyio
async def test_get_user_cart_not_found(client: AsyncClient):
    r = await client.get("/admin/users/123")
    assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_get_user_cart_success(client: AsyncClient, session: AsyncSession):
    cart = CartModel(user_id=42)
    session.add(cart)
    await session.flush()
    m = MovieModel(
        name="CartMovie",
        year=2021,
        time=90,
        imdb=8.0,
        votes=200,
        meta_score=85,
        gross=200000,
        description="",
        price=3.5,
        certification_id=1,
    )
    session.add(m)
    await session.flush()
    ci = CartItemModel(cart_id=cart.id, movie_id=m.id, quantity=2)
    session.add(ci)
    await session.commit()

    r = await client.get(f"/admin/users/{cart.user_id}")
    assert r.status_code == status.HTTP_200_OK
    j = r.json()
    assert j["user_id"] == 42
    items = j.get("items", [])
    assert len(items) == 1
    item = items[0]
    assert item.get("movie_id") == m.id


@pytest.mark.anyio
async def test_list_orders_and_filters(client: AsyncClient, session: AsyncSession):
    o1 = OrderModel(user_id=1, status=OrderStatus.pending, total_amount=3.5)
    o2 = OrderModel(user_id=2, status=OrderStatus.pending, total_amount=7.0)
    session.add_all([o1, o2])
    await session.commit()

    r = await client.get("/admin/orders")
    assert r.status_code == status.HTTP_200_OK
    data_all = r.json()
    assert len(data_all) == 2

    r = await client.get("/admin/orders", params={"user_id": 1})
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == o1.id
