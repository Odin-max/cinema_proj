from app.models.cart_models import CartModel
from app.routes.cart.carts import _load_and_build_cart
from app.schemas.cart_schema import CartRead
from app.schemas.order_schema import OrderRead, OrderStatus
from app.models.order_models import OrderItemModel, OrderModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.security import get_current_moderator
from app.models.movie_models import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from app.schemas.movie_schema import MovieCreate, MovieRead

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_moderator)],
)

@router.post(
    "/create_movie",
    response_model=MovieRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie_in: MovieCreate,
    db: AsyncSession = Depends(get_db),
):
    cert = await db.get(CertificationModel, movie_in.certification_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certification not found",
        )

    movie = MovieModel(
        name=movie_in.name,
        year=movie_in.year,
        time=movie_in.time,
        imdb=movie_in.imdb,
        votes=movie_in.votes,
        meta_score=movie_in.meta_score,
        gross=movie_in.gross,
        description=movie_in.description,
        price=movie_in.price,
        certification_id=movie_in.certification_id,
    )

    if movie_in.genre_ids:
        res = await db.execute(
            select(GenreModel).where(GenreModel.id.in_(movie_in.genre_ids))
        )
        genres = res.scalars().all()
        if len(genres) != len(movie_in.genre_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more genres not found",
            )
        movie.genres = genres

    if movie_in.star_ids:
        res = await db.execute(
            select(StarModel).where(StarModel.id.in_(movie_in.star_ids))
        )
        stars = res.scalars().all()
        if len(stars) != len(movie_in.star_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more stars not found",
            )
        movie.stars = stars

    if movie_in.director_ids:
        res = await db.execute(
            select(DirectorModel).where(DirectorModel.id.in_(movie_in.director_ids))
        )
        directors = res.scalars().all()
        if len(directors) != len(movie_in.director_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more directors not found",
            )
        movie.directors = directors

    db.add(movie)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "uq_movie_name_year_time" in str(e.orig).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie with this name, year and duration already exists",
            )
        raise
    await db.refresh(movie)

    result = await db.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors),
        )
        .where(MovieModel.id == movie.id)
    )
    full_movie: MovieModel = result.scalar_one()

    return MovieRead(
        id=full_movie.id,
        uuid=full_movie.uuid,
        name=full_movie.name,
        year=full_movie.year,
        time=full_movie.time,
        imdb=full_movie.imdb,
        votes=full_movie.votes,
        meta_score=full_movie.meta_score,
        gross=full_movie.gross,
        description=full_movie.description,
        price=full_movie.price,
        certification_id=full_movie.certification_id,
        genres=[g.name for g in full_movie.genres],
        stars=[s.name for s in full_movie.stars],
        directors=[d.name for d in full_movie.directors],
    )

@router.get("/users/{user_id}", response_model=CartRead)
async def get_user_cart(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(CartModel).where(CartModel.user_id == user_id))
    cart = q.scalar_one_or_none()
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return await _load_and_build_cart(cart.id, db)


@router.get("/orders", response_model=list[OrderRead])
async def list_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    user_id: Optional[int] = Query(None, description="Filter by user id"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(OrderModel)
        .options(
            selectinload(OrderModel.items)
            .selectinload(OrderItemModel.movie)
        )
    )
    
    if status is not None:
        stmt = stmt.where(OrderModel.status == status)
    if user_id is not None:
        stmt = stmt.where(OrderModel.user_id == user_id)

    result = await db.execute(stmt)
    orders: List[OrderModel] = result.scalars().all()

    return orders
