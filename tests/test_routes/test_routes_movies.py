import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_models import (
    MovieModel,
    FavoriteModel,
    MovieLikeModel,
    RatingModel,
    PurchaseModel,
    GenreModel,
    CertificationModel,
    DirectorModel,
    StarModel,
)
from app.models.user_models import User, UserGroup
from app.main import app
from app.core.security import get_current_user


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def prepare_users(session: AsyncSession):
    result = await session.execute(select(UserGroup).where(UserGroup.name == "default"))
    default_group = result.scalar_one_or_none()
    if default_group is None:
        default_group = UserGroup(name="default")
        session.add(default_group)
        await session.commit()
        await session.refresh(default_group)

    u1 = User(
        email="user1@example.com", hashed_password="pwdhash1", group_id=default_group.id
    )
    u2 = User(
        email="user2@example.com", hashed_password="pwdhash2", group_id=default_group.id
    )
    session.add_all([u1, u2])
    await session.commit()


@pytest.fixture(autouse=True)
def override_auth():
    class DummyUser:
        def __init__(self, id: int):
            self.id = id
            self.group_id = 1

    app.dependency_overrides[get_current_user] = lambda: DummyUser(1)
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_list_movies_filters_and_pagination(
    client: AsyncClient, session: AsyncSession
):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()

    m1 = MovieModel(
        name="Alpha",
        year=2000,
        time=100,
        imdb=7.0,
        votes=10,
        meta_score=50,
        gross=100000,
        description="first movie",
        price=5.0,
        certification_id=cert.id,
    )
    m2 = MovieModel(
        name="Beta",
        year=2001,
        time=110,
        imdb=8.0,
        votes=20,
        meta_score=60,
        gross=200000,
        description="second movie",
        price=6.0,
        certification_id=cert.id,
    )
    m3 = MovieModel(
        name="Gamma",
        year=2000,
        time=120,
        imdb=9.0,
        votes=30,
        meta_score=70,
        gross=300000,
        description="third entry",
        price=7.0,
        certification_id=cert.id,
    )
    session.add_all([m1, m2, m3])
    await session.commit()

    r = await client.get("/movies/")
    assert r.status_code == status.HTTP_200_OK
    names = [m["name"] for m in r.json() if m["name"] in ("Alpha", "Beta", "Gamma")]
    assert names == ["Alpha", "Beta", "Gamma"]

    r = await client.get("/movies/", params={"year": 2000})
    names = sorted([m["name"] for m in r.json() if m["name"] in ("Alpha", "Gamma")])
    assert names == ["Alpha", "Gamma"]

    r = await client.get("/movies/", params={"min_imdb": 8.5})
    assert [m["name"] for m in r.json()] == ["Gamma"]

    r = await client.get("/movies/", params={"search": "second"})
    assert r.json()[0]["name"] == "Beta"

    r = await client.get("/movies/", params={"sort_by": "price"})
    prices = [m["price"] for m in r.json() if m["name"] in ("Alpha", "Beta", "Gamma")]
    assert prices == [5.0, 6.0, 7.0]

    r = await client.get("/movies/", params={"year": 2000, "per_page": 1, "page": 2})
    assert r.json()[0]["name"] == "Gamma"


@pytest.mark.anyio
async def test_favorite_endpoints(client: AsyncClient, session: AsyncSession):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()

    movie = MovieModel(
        name="FavMe",
        year=2010,
        time=90,
        imdb=5.5,
        votes=5,
        meta_score=40,
        gross=50000,
        description="",
        price=3.0,
        certification_id=cert.id,
    )
    session.add(movie)
    await session.commit()

    r = await client.post(f"/movies/{movie.id}/favorite")
    assert r.status_code == status.HTTP_204_NO_CONTENT
    fav = (
        await session.execute(select(FavoriteModel).where(FavoriteModel.user_id == 1))
    ).scalar_one()
    assert fav.movie_id == movie.id

    r = await client.get("/movies/favorites")
    assert [m["id"] for m in r.json()] == [movie.id]

    r = await client.delete(f"/movies/{movie.id}/favorite")
    assert r.status_code == status.HTTP_204_NO_CONTENT
    r = await client.get("/movies/favorites")
    assert r.json() == []


@pytest.mark.anyio
async def test_movie_detail_likes_dislikes_and_rating(
    client: AsyncClient, session: AsyncSession
):
    cert = CertificationModel(name="PG")
    genre = GenreModel(name="Drama")
    director = DirectorModel(name="Dir")
    star = StarModel(name="Star")
    session.add_all([cert, genre, director, star])
    await session.commit()

    movie = MovieModel(
        name="DetailMe",
        year=2020,
        time=100,
        imdb=7.5,
        votes=50,
        meta_score=75,
        gross=150000,
        description="desc",
        price=4.0,
        certification_id=cert.id,
    )
    movie.genres.append(genre)
    movie.directors.append(director)
    movie.stars.append(star)
    session.add(movie)
    await session.commit()

    session.add_all(
        [
            MovieLikeModel(movie_id=movie.id, user_id=1, is_like=1),
            MovieLikeModel(movie_id=movie.id, user_id=2, is_like=0),
            RatingModel(movie_id=movie.id, user_id=1, score=8),
            RatingModel(movie_id=movie.id, user_id=2, score=6),
        ]
    )
    await session.commit()

    r = await client.get(f"/movies/{movie.id}")
    assert r.status_code == status.HTTP_200_OK
    d = r.json()
    assert d["likes"] == 1 and d["dislikes"] == 1
    assert abs(d["average_rating"] - 7.0) < 1e-6
    assert d["certification"] == "PG"
    assert d["genres"] == ["Drama"]
    assert d["directors"] == ["Dir"]
    assert d["stars"] == ["Star"]


@pytest.mark.anyio
async def test_like_movie_endpoint(client: AsyncClient, session: AsyncSession):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()

    movie = MovieModel(
        name="LikeMe",
        year=2022,
        time=95,
        imdb=7.0,
        votes=2,
        meta_score=70,
        gross=100000,
        description="",
        price=2.5,
        certification_id=cert.id,
    )
    session.add(movie)
    await session.commit()

    r = await client.post(f"/movies/{movie.id}/like", json={"is_like": True})
    assert r.status_code == status.HTTP_204_NO_CONTENT
    like = (
        await session.execute(select(MovieLikeModel).where(MovieLikeModel.user_id == 1))
    ).scalar_one()
    assert like.is_like == 1

    r = await client.post(f"/movies/{movie.id}/like", json={"is_like": False})
    dislike = (
        await session.execute(select(MovieLikeModel).where(MovieLikeModel.user_id == 1))
    ).scalar_one()
    assert dislike.is_like == 0


@pytest.mark.anyio
async def test_comments_and_replies(client: AsyncClient, session: AsyncSession):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()

    movie = MovieModel(
        name="CommentMe",
        year=2015,
        time=80,
        imdb=6.0,
        votes=5,
        meta_score=60,
        gross=80000,
        description="",
        price=1.0,
        certification_id=cert.id,
    )
    session.add(movie)
    await session.commit()

    r = await client.post(
        f"/movies/{movie.id}/comments", json={"text": "Hello", "parent_id": None}
    )
    assert r.status_code == status.HTTP_201_CREATED
    root = r.json()
    assert root["text"] == "Hello" and root["replies"] == []

    r = await client.post(
        f"/movies/{movie.id}/comments", json={"text": "Reply", "parent_id": root["id"]}
    )
    assert r.status_code == status.HTTP_201_CREATED

    r = await client.get(f"/movies/{movie.id}/comments")
    assert len(r.json()) == 1

    r = await client.post(
        f"/movies/{movie.id}/comments", json={"text": "Bad", "parent_id": 999}
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.anyio
async def test_rate_and_purchase_and_delete_movie(
    client: AsyncClient, session: AsyncSession
):
    cert = CertificationModel(name="PG")
    session.add(cert)
    await session.commit()

    movie = MovieModel(
        name="PurchaseMe",
        year=2018,
        time=85,
        imdb=7.2,
        votes=10,
        meta_score=65,
        gross=120000,
        description="",
        price=2.0,
        certification_id=cert.id,
    )
    session.add(movie)
    await session.commit()

    resp = await client.delete(f"/movies/{movie.id}")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["detail"] == "You do not have the required permissions"

    await session.execute(
        delete(PurchaseModel).where(PurchaseModel.movie_id == movie.id)
    )
    await session.commit()

    resp = await client.delete(f"/movies/{movie.id}")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["detail"] == "You do not have the required permissions"

    moderator_group = UserGroup(name="moderator")
    session.add(moderator_group)
    await session.commit()

    def override_moderator():
        class ModUser:
            id = 1
            group_id = moderator_group.id

        return ModUser()

    app.dependency_overrides[get_current_user] = override_moderator

    resp = await client.delete(f"/movies/{movie.id}")
    assert resp.status_code == status.HTTP_204_NO_CONTENT
