from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from typing import List

from app.core.security import get_current_user, get_db, get_current_moderator
from app.models.movie_models import StarModel, StarCreate, StarRead, StarUpdate


router = APIRouter(prefix="/stars", tags=["stars"])


@router.post(
    "/",
    response_model=StarRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_star(star_in: StarCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(StarModel).where(StarModel.name == star_in.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Star already exists"
        )
    star = StarModel(name=star_in.name)
    db.add(star)
    await db.commit()
    await db.refresh(star)
    return star


@router.get(
    "/", response_model=List[StarRead], dependencies=[Depends(get_current_user)]
)
async def list_stars(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StarModel))
    return result.scalars().all()


@router.get(
    "/{star_id}", response_model=StarRead, dependencies=[Depends(get_current_user)]
)
async def get_star(star_id: int, db: AsyncSession = Depends(get_db)):
    star = await db.get(StarModel, star_id)
    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Star not found"
        )
    return star


@router.put(
    "/{star_id}", response_model=StarRead, dependencies=[Depends(get_current_moderator)]
)
async def update_star(
    star_id: int, star_in: StarUpdate, db: AsyncSession = Depends(get_db)
):
    star = await db.get(StarModel, star_id)
    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Star not found"
        )
    existing = await db.scalar(
        select(StarModel).where(StarModel.name == star_in.name, StarModel.id != star_id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Star name already in use"
        )
    star.name = star_in.name
    db.add(star)
    await db.commit()
    await db.refresh(star)
    return star


@router.delete(
    "/{star_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_star(star_id: int, db: AsyncSession = Depends(get_db)):
    star = await db.get(StarModel, star_id)
    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Star not found"
        )
    await db.execute(sql_delete(StarModel).where(StarModel.id == star_id))
    await db.commit()
    return None
