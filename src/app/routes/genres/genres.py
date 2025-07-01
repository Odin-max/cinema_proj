from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from typing import List

from app.core.security import get_current_user, get_db, get_current_moderator
from app.models.movie_models import GenreModel, GenreCreate, GenreRead, GenreUpdate
from pydantic import BaseModel


router = APIRouter(prefix="/genres", tags=["genres"])


@router.post(
    "/",
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_genre(genre_in: GenreCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(
        select(GenreModel).where(GenreModel.name == genre_in.name)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Genre already exists"
        )
    genre = GenreModel(name=genre_in.name)
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return genre


@router.get(
    "/", response_model=List[GenreRead], dependencies=[Depends(get_current_user)]
)
async def list_genres(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenreModel))
    genres = result.scalars().all()
    return genres


@router.get(
    "/{genre_id}", response_model=GenreRead, dependencies=[Depends(get_current_user)]
)
async def get_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    genre = await db.get(GenreModel, genre_id)
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genre not found"
        )
    return genre


@router.put(
    "/{genre_id}",
    response_model=GenreRead,
    dependencies=[Depends(get_current_moderator)],
)
async def update_genre(
    genre_id: int, genre_in: GenreUpdate, db: AsyncSession = Depends(get_db)
):
    genre = await db.get(GenreModel, genre_id)
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genre not found"
        )
    # Check new name uniqueness
    existing = await db.scalar(
        select(GenreModel).where(
            GenreModel.name == genre_in.name, GenreModel.id != genre_id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Genre name already in use"
        )
    genre.name = genre_in.name
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return genre


@router.delete(
    "/{genre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    genre = await db.get(GenreModel, genre_id)
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genre not found"
        )
    await db.execute(sql_delete(GenreModel).where(GenreModel.id == genre_id))
    await db.commit()
    return None
