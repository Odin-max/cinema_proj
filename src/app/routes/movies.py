from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_moderator, get_current_user
from app.db.session import get_db
from app.models.movie_models import (
    CommentModel,
    FavoriteModel,
    MovieLikeModel,
    MovieModel,
    PurchaseModel,
    RatingModel,
)
from app.schemas.movie_schema import (
    CommentCreate,
    CommentRead,
    LikeAction,
    MovieDetail,
    MovieListItem,
    RatingCreate,
)


router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/", response_model=List[MovieListItem])
async def list_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    year: Optional[int] = None,
    min_imdb: Optional[float] = None,
    sort_by: Optional[str] = Query("name", regex="^(name|price|year|imdb)$"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieModel)
    if year is not None:
        stmt = stmt.where(MovieModel.year == year)
    if min_imdb is not None:
        stmt = stmt.where(MovieModel.imdb >= min_imdb)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(MovieModel.name).ilike(like)
            | func.lower(MovieModel.description).ilike(like)
        )
    sort_col = getattr(MovieModel, sort_by)
    stmt = stmt.order_by(sort_col).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    movies = result.scalars().all()
    return movies


@router.post("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    movie_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FavoriteModel).where(
        FavoriteModel.movie_id == movie_id, FavoriteModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    exists = result.scalars().first()
    if not exists:
        fav = FavoriteModel(movie_id=movie_id, user_id=current_user.id)
        db.add(fav)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    movie_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del_stmt = select(FavoriteModel).where(
        FavoriteModel.movie_id == movie_id, FavoriteModel.user_id == current_user.id
    )
    result = await db.execute(del_stmt)
    fav = result.scalars().first()
    if fav:
        await db.delete(fav)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/favorites", response_model=List[MovieListItem])
async def list_favorites(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subq = select(FavoriteModel.movie_id).where(
        FavoriteModel.user_id == current_user.id
    )
    stmt = select(MovieModel).where(MovieModel.id.in_(subq))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{movie_id}", response_model=MovieDetail)
async def get_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.certification),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.stars),
        )
        .where(MovieModel.id == movie_id)
    )
    result = await db.execute(stmt)
    movie: MovieModel | None = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")

    likes = (
        await db.scalar(
            select(func.count())
            .select_from(MovieLikeModel)
            .where(MovieLikeModel.movie_id == movie_id, MovieLikeModel.is_like == 1)
        )
    ) or 0

    dislikes = (
        await db.scalar(
            select(func.count())
            .select_from(MovieLikeModel)
            .where(MovieLikeModel.movie_id == movie_id, MovieLikeModel.is_like == 0)
        )
    ) or 0

    avg_rating = await db.scalar(
        select(func.avg(RatingModel.score)).where(RatingModel.movie_id == movie_id)
    )

    return MovieDetail(
        id=movie.id,
        uuid=str(movie.uuid),
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=movie.imdb,
        votes=movie.votes,
        meta_score=movie.meta_score,
        gross=movie.gross,
        description=movie.description,
        price=float(movie.price) if movie.price is not None else None,
        certification=movie.certification.name,
        genres=[g.name for g in movie.genres],
        directors=[d.name for d in movie.directors],
        stars=[s.name for s in movie.stars],
        average_rating=float(avg_rating) if avg_rating is not None else None,
        likes=likes,
        dislikes=dislikes,
    )


@router.post("/{movie_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_movie(
    movie_id: int,
    action: LikeAction,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieLikeModel).where(
        MovieLikeModel.movie_id == movie_id, MovieLikeModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    entry = result.scalars().first()
    if entry:
        entry.is_like = 1 if action.is_like else 0
    else:
        entry = MovieLikeModel(
            movie_id=movie_id,
            user_id=current_user.id,
            is_like=1 if action.is_like else 0,
        )
        db.add(entry)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{movie_id}/comments", response_model=List[CommentRead])
async def list_comments(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    q = select(CommentModel).where(
        CommentModel.movie_id == movie_id, CommentModel.parent_id.is_(None)
    )
    result = await db.execute(q)
    comments: list[CommentModel] = result.scalars().all()

    return [
        CommentRead(
            id=c.id,
            user_id=c.user_id,
            text=c.text,
            created_at=c.created_at,
            replies=[],
        )
        for c in comments
    ]


@router.post(
    "/{movie_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    movie_id: int,
    data: CommentCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")

    pid: Optional[int] = data.parent_id
    if not pid or pid <= 0:
        pid = None

    if pid is not None:
        parent = await db.get(CommentModel, pid)
        if not parent:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent comment not found")

    comment = CommentModel(
        user_id=current_user.id,
        movie_id=movie_id,
        text=data.text,
        **({"parent_id": pid} if pid is not None else {}),
    )

    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentRead(
        id=comment.id,
        user_id=comment.user_id,
        text=comment.text,
        created_at=comment.created_at,
        replies=[],
    )


@router.post("/{movie_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
async def rate_movie(
    movie_id: int,
    rating_in: RatingCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RatingModel).where(
        RatingModel.movie_id == movie_id, RatingModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    entry = result.scalars().first()
    if entry:
        entry.score = rating_in.score
    else:
        entry = RatingModel(
            movie_id=movie_id, user_id=current_user.id, score=rating_in.score
        )
        db.add(entry)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{movie_id}/purchase",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def purchase_movie(
    movie_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    purchase = PurchaseModel(user_id=current_user.id, movie_id=movie_id)
    db.add(purchase)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    purchased_count = await db.scalar(
        select(func.count())
        .select_from(PurchaseModel)
        .where(PurchaseModel.movie_id == movie_id)
    )
    if purchased_count and purchased_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete movie: it has purchases",
        )
    await db.execute(delete(MovieModel).where(MovieModel.id == movie_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
