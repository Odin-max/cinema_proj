from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from typing import List

from app.core.security import get_current_user, get_db, get_current_moderator
from app.models.movie_models import (
    DirectorModel,
    DirectorCreate,
    DirectorRead,
    DirectorUpdate,
)

router = APIRouter(prefix="/directors", tags=["directors"])


@router.post(
    "/",
    response_model=DirectorRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_director(
    director_in: DirectorCreate, db: AsyncSession = Depends(get_db)
):
    existing = await db.scalar(
        select(DirectorModel).where(DirectorModel.name == director_in.name)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Director already exists"
        )
    director = DirectorModel(name=director_in.name)
    db.add(director)
    await db.commit()
    await db.refresh(director)
    return director


@router.get(
    "/", response_model=List[DirectorRead], dependencies=[Depends(get_current_user)]
)
async def list_directors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DirectorModel))
    return result.scalars().all()


@router.get(
    "/{director_id}",
    response_model=DirectorRead,
    dependencies=[Depends(get_current_user)],
)
async def get_director(director_id: int, db: AsyncSession = Depends(get_db)):
    director = await db.get(DirectorModel, director_id)
    if not director:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Director not found"
        )
    return director


@router.put(
    "/{director_id}",
    response_model=DirectorRead,
    dependencies=[Depends(get_current_moderator)],
)
async def update_director(
    director_id: int, director_in: DirectorUpdate, db: AsyncSession = Depends(get_db)
):
    director = await db.get(DirectorModel, director_id)
    if not director:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Director not found"
        )
    existing = await db.scalar(
        select(DirectorModel).where(
            DirectorModel.name == director_in.name, DirectorModel.id != director_id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Director name already in use",
        )
    director.name = director_in.name
    db.add(director)
    await db.commit()
    await db.refresh(director)
    return director


@router.delete(
    "/{director_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_director(director_id: int, db: AsyncSession = Depends(get_db)):
    director = await db.get(DirectorModel, director_id)
    if not director:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Director not found"
        )
    await db.execute(sql_delete(DirectorModel).where(DirectorModel.id == director_id))
    await db.commit()
    return None
