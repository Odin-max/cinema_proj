import pytest
from sqlalchemy import select, exc
from sqlalchemy.orm import selectinload

from datetime import datetime, timedelta
from app.models.user_models import User
from app.models.movie_models import (
    CertificationModel, GenreModel, StarModel, DirectorModel, MovieModel,
    CommentModel, CommentLikeModel, MovieLikeModel,
    FavoriteModel, RatingModel, NotificationModel, PurchaseModel
)
from app.models.cart_models import CartModel, CartItemModel
from app.models.order_models import OrderModel, OrderItemModel, OrderStatus
from app.models.user_models import (
    UserGroup, User,
    ActivationToken, PasswordResetToken, RefreshToken
)

@pytest.mark.asyncio
async def test_cart_creation_and_relationships(session):
    user = User(email="u1@example.com", hashed_password="hash", is_active=True, group_id=1)
    cert = CertificationModel(name="PG-13")
    movie = MovieModel(
        name="Test Movie",
        year=2023,
        time=100,
        imdb=7.5,
        votes=1000,
        meta_score=80,
        gross=1.0,
        description="desc",
        price=9.99,
        certification=cert
    )
    session.add_all([user, cert, movie])
    await session.commit()

    cart = CartModel(user_id=user.id)
    session.add(cart)
    await session.commit()

    result = await session.execute(
        select(CartModel)
          .options(selectinload(CartModel.items))
          .where(CartModel.id == cart.id)
    )
    cart = result.scalar_one()

    assert cart.id is not None
    assert cart.user.id == user.id
    assert isinstance(cart.created_at, datetime)

    item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    session.add(item)
    await session.commit()

    await session.refresh(cart, attribute_names=["items"])
    assert len(cart.items) == 1
    assert cart.items[0].movie.id == movie.id


@pytest.mark.asyncio
async def test_unique_cart_movie_constraint(session):
    user = User(email="u2@example.com", hashed_password="hash", is_active=True, group_id=1)
    cert = CertificationModel(name="R")
    movie = MovieModel(
        name="Another Movie", year=2021, time=90, imdb=8.0,
        votes=500, meta_score=75, gross=2.0, description="desc",
        price=12.5, certification=cert
    )
    session.add_all([user, cert, movie])
    await session.commit()

    cart = CartModel(user_id=user.id)
    session.add(cart)
    await session.commit()

    item1 = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    session.add(item1)
    await session.commit()

    item2 = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    session.add(item2)
    with pytest.raises(exc.IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_cascade_delete_cart_items(session):
    user = User(email="u3@example.com", hashed_password="hash", is_active=True, group_id=1)
    cert = CertificationModel(name="G")
    movie1 = MovieModel(name="M1", year=2020, time=80, imdb=7.0, votes=100, meta_score=60, gross=0.5, description="d", price=5.0, certification=cert)
    movie2 = MovieModel(name="M2", year=2019, time=85, imdb=6.5, votes=80, meta_score=55, gross=0.3, description="d", price=6.0, certification=cert)
    session.add_all([user, cert, movie1, movie2])
    await session.commit()

    cart = CartModel(user_id=user.id)
    cart.items.append(CartItemModel(movie_id=movie1.id))
    cart.items.append(CartItemModel(movie_id=movie2.id))
    session.add(cart)
    await session.commit()

    await session.refresh(cart, attribute_names=["items"])
    assert len(cart.items) == 2

    await session.delete(cart)
    await session.commit()

    result = await session.execute(select(CartItemModel))
    assert result.scalars().all() == []

    result = await session.execute(
        select(CartModel).where(CartModel.id == cart.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_certification_and_movie_relationships(session):
    cert = CertificationModel(name="PG-13")
    m1 = MovieModel(
        name="A", year=2000, time=100, imdb=7.0, votes=100,
        meta_score=50, gross=1.0, description="d", price=5.0,
        certification=cert
    )
    m2 = MovieModel(
        name="B", year=2001, time=110, imdb=6.5, votes=200,
        meta_score=60, gross=2.0, description="d2", price=6.0,
        certification=cert
    )
    session.add_all([cert, m1, m2])
    await session.commit()

    result = await session.execute(
        select(CertificationModel)
        .options(selectinload(CertificationModel.movies))
        .where(CertificationModel.id == cert.id)
    )
    cert_db = result.scalar_one()
    assert len(cert_db.movies) == 2
    names = {m.name for m in cert_db.movies}
    assert names == {"A", "B"}

    dup = CertificationModel(name="PG-13")
    session.add(dup)
    with pytest.raises(exc.IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_genre_star_director_many_to_many(session):
    cert = CertificationModel(name="R")
    g = GenreModel(name="Action")
    s = StarModel(name="Star One")
    d = DirectorModel(name="Dir One")
    m = MovieModel(
        name="X", year=2022, time=120, imdb=8.0, votes=300,
        meta_score=70, gross=3.0, description="desc", price=7.5,
        certification=cert
    )

    m.genres.append(g)
    m.stars.append(s)
    m.directors.append(d)
    session.add_all([cert, g, s, d, m])
    await session.commit()

    result = await session.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors),
        )
        .where(MovieModel.id == m.id)
    )
    m_db = result.scalar_one()
    assert [g.name for g in m_db.genres] == ["Action"]
    assert [s.name for s in m_db.stars] == ["Star One"]
    assert [d.name for d in m_db.directors] == ["Dir One"]

    dup = MovieModel(
        name="X", year=2022, time=120, imdb=5.0, votes=10,
        meta_score=10, gross=0.0, description="dup", price=1.0,
        certification=cert
    )
    session.add(dup)
    with pytest.raises(exc.IntegrityError):
        await session.commit()
    await session.rollback()



@pytest.mark.asyncio
async def test_comment_and_likes_cascade(session):
    user = User(email="u@e", hashed_password="h", is_active=True, group_id=1)
    cert = CertificationModel(name="G")
    movie = MovieModel(
        name="C", year=2021, time=90, imdb=7.5, votes=150,
        meta_score=65, gross=2.5, description="d", price=4.5,
        certification=cert,
    )
    session.add_all([user, cert, movie])
    await session.commit()
    await session.refresh(user)
    await session.refresh(movie)
    uid, mid = user.id, movie.id

    parent = CommentModel(user_id=uid, movie_id=mid, text="parent")
    session.add(parent)
    await session.commit()
    await session.refresh(parent)
    pid = parent.id

    child = CommentModel(user_id=uid, movie_id=mid, text="child", parent_id=pid)
    session.add(child)
    await session.commit()
    await session.refresh(child)
    cid = child.id

    like = CommentLikeModel(comment_id=cid, user_id=uid)
    session.add(like)
    await session.commit()

    comments = (await session.execute(select(CommentModel))).scalars().all()
    assert len(comments) == 2
    likes = (await session.execute(select(CommentLikeModel))).scalars().all()
    assert len(likes) == 1

    await session.delete(parent)
    await session.commit()

    comments = (await session.execute(select(CommentModel))).scalars().all()
    assert len(comments) == 1
    assert comments[0].id == cid
    assert comments[0].text == "child"

    likes = (await session.execute(select(CommentLikeModel))).scalars().all()
    assert len(likes) == 1
    assert likes[0].comment_id == cid


@pytest.mark.asyncio
async def test_favorites_ratings_likes_notifications_purchases(session):
    user = User(email="fav@e", hashed_password="h", is_active=True, group_id=1)
    cert = CertificationModel(name="Z")
    movie = MovieModel(
        name="F", year=2020, time=95, imdb=6.0, votes=80,
        meta_score=55, gross=1.2, description="d", price=3.0,
        certification=cert,
    )
    session.add_all([user, cert, movie])
    await session.commit()
    await session.refresh(user)
    await session.refresh(movie)

    uid = user.id
    mid = movie.id

    session.add(FavoriteModel(user_id=uid, movie_id=mid))
    await session.commit()
    favs = (await session.execute(select(FavoriteModel))).scalars().all()
    assert len(favs) == 1 and favs[0].movie_id == mid

    session.add(RatingModel(user_id=uid, movie_id=mid, score=4))
    await session.commit()
    rates = (await session.execute(select(RatingModel))).scalars().all()
    assert len(rates) == 1 and rates[0].score == 4

    session.add(MovieLikeModel(movie_id=mid, user_id=uid, is_like=1))
    await session.commit()
    session.add(MovieLikeModel(movie_id=mid, user_id=uid, is_like=0))
    with pytest.raises(exc.IntegrityError):
        await session.commit()
    await session.rollback()

    note = NotificationModel(
        user_id=uid,
        text="you have mail",
        is_read=0,
        created_at=datetime.utcnow()
    )
    session.add(note)
    await session.commit()
    notes = (await session.execute(select(NotificationModel))).scalars().all()
    assert len(notes) == 1
    assert notes[0].text == "you have mail"
    assert notes[0].is_read == 0

    session.add(PurchaseModel(user_id=uid, movie_id=mid))
    await session.commit()
    purchases = (await session.execute(select(PurchaseModel))).scalars().all()
    assert len(purchases) == 1
    assert purchases[0].movie_id == mid


@pytest.mark.asyncio
async def test_create_order_and_items(session):
    user = User(email="u@e", hashed_password="h", is_active=True, group_id=1)
    cert = CertificationModel(name="G")
    session.add_all([user, cert])
    await session.commit()
    await session.refresh(user)
    await session.refresh(cert)

    movie1 = MovieModel(
        name="M1", year=2021, time=100, imdb=8.0, votes=1000,
        meta_score=80, gross=5.0, description="d", price=4.0,
        certification_id=cert.id
    )
    movie2 = MovieModel(
        name="M2", year=2022, time=110, imdb=7.5, votes=800,
        meta_score=75, gross=4.0, description="d2", price=5.0,
        certification_id=cert.id
    )
    session.add_all([movie1, movie2])
    await session.commit()
    await session.refresh(movie1)
    await session.refresh(movie2)

    order = OrderModel(
        user_id=user.id,
        total_amount=movie1.price + movie2.price
    )
    order.items.append(
        OrderItemModel(movie_id=movie1.id, price_at_order=movie1.price)
    )
    order.items.append(
        OrderItemModel(movie_id=movie2.id, price_at_order=movie2.price)
    )
    session.add(order)
    await session.commit()

    await session.refresh(order, attribute_names=['items'])

    assert order.user_id == user.id
    assert order.status == OrderStatus.pending
    assert float(order.total_amount) == float(movie1.price + movie2.price)

    assert len(order.items) == 2
    prices = sorted(float(i.price_at_order) for i in order.items)
    assert prices == sorted([float(movie1.price), float(movie2.price)])


@pytest.mark.asyncio
async def test_order_items_cascade_and_status_change(session):
    user = User(email="x@e", hashed_password="h", is_active=True, group_id=1)
    cert = CertificationModel(name="Z")
    session.add_all([user, cert])
    await session.commit()
    await session.refresh(user)
    await session.refresh(cert)

    movie = MovieModel(
        name="X", year=2020, time=90, imdb=6.5, votes=500,
        meta_score=60, gross=3.0, description="dx", price=3.5,
        certification_id=cert.id
    )
    session.add(movie)
    await session.commit()
    await session.refresh(movie)

    order = OrderModel(user_id=user.id, total_amount=movie.price)
    order.items = [OrderItemModel(movie_id=movie.id, price_at_order=movie.price)]
    session.add(order)
    await session.commit()
    await session.refresh(order)

    order.status = OrderStatus.paid
    await session.commit()
    await session.refresh(order)
    assert order.status == OrderStatus.paid

    await session.delete(order)
    await session.commit()

    remaining_orders = (await session.execute(select(OrderModel))).scalars().all()
    remaining_items = (await session.execute(select(OrderItemModel))).scalars().all()
    assert remaining_orders == []
    assert remaining_items == []


@pytest.mark.asyncio
async def test_user_group_and_tokens_relationships(session):
    group = UserGroup(name="testers")
    user = User(
        email="foo@example.com",
        hashed_password="hash",
        is_active=True,
        group=group
    )
    session.add(user)
    await session.commit()
    await session.refresh(group)
    await session.refresh(user)

    assert user.group_id == group.id
    assert user.group.name == "testers"

    await session.refresh(group, attribute_names=["users"])
    assert group.users == [user]

    exp = datetime.utcnow() + timedelta(hours=1)
    act = ActivationToken(user=user, expires_at=exp)
    session.add(act)
    await session.commit()
    await session.refresh(act)

    with pytest.raises(exc.IntegrityError):
        session.add(ActivationToken(user_id=user.id, expires_at=exp))
        await session.commit()
    await session.rollback()

    prt = PasswordResetToken(user=user, expires_at=exp)
    session.add(prt)
    await session.commit()
    await session.refresh(prt)

    with pytest.raises(exc.IntegrityError):
        session.add(PasswordResetToken(user_id=user.id, expires_at=exp))
        await session.commit()
    await session.rollback()

    rt1 = RefreshToken(user=user, expires_at=exp)
    rt2 = RefreshToken(user=user, expires_at=exp + timedelta(days=1))
    session.add_all([rt1, rt2])
    await session.commit()

    await session.refresh(user, attribute_names=["refresh_tokens"])
    assert len(user.refresh_tokens) == 2
    tokens = {t.token for t in user.refresh_tokens}
    assert rt1.token in tokens and rt2.token in tokens

    fetched = (await session.execute(
        select(User)
        .options(
            selectinload(User.activation_token),
            selectinload(User.password_reset_token),
            selectinload(User.refresh_tokens),
        )
        .where(User.id == user.id)
    )).scalar_one()

    assert fetched.activation_token.id == act.id
    assert fetched.password_reset_token.id == prt.id
    assert {t.id for t in fetched.refresh_tokens} == {rt1.id, rt2.id}


@pytest.mark.asyncio
async def test_cascade_delete_user_removes_tokens_and_group_untouched(session):
    group = UserGroup(name="admins")
    user = User(
        email="bar@example.com",
        hashed_password="hash2",
        is_active=False,
        group=group
    )
    user.activation_token = ActivationToken(
        expires_at=datetime.utcnow() + timedelta(hours=2)
    )
    user.password_reset_token = PasswordResetToken(
        expires_at=datetime.utcnow() + timedelta(hours=2)
    )
    user.refresh_tokens.append(
        RefreshToken(expires_at=datetime.utcnow() + timedelta(days=1))
    )

    session.add(user)
    await session.commit()

    act_list = (await session.execute(select(ActivationToken))).scalars().all()
    prt_list = (await session.execute(select(PasswordResetToken))).scalars().all()
    rt_list  = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(act_list) == 1
    assert len(prt_list) == 1
    assert len(rt_list)  == 1

    await session.delete(user)
    await session.commit()

    assert (await session.execute(select(ActivationToken))).scalars().all() == []
    assert (await session.execute(select(PasswordResetToken))).scalars().all() == []
    assert (await session.execute(select(RefreshToken))).scalars().all()  == []

    remaining = (await session.execute(select(UserGroup))).scalars().all()
    names = [g.name for g in remaining]
    assert "admins" in names
