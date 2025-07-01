from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from typing import List

from app.core.security import get_current_user, get_db, get_current_moderator
from app.models.movie_models import (
    CertificationModel,
    CertificationCreate,
    CertificationUpdate,
    CertificationRead,
)


router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.post(
    "/",
    response_model=CertificationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_certification(
    cert_in: CertificationCreate, db: AsyncSession = Depends(get_db)
):
    existing = await db.scalar(
        select(CertificationModel).where(CertificationModel.name == cert_in.name)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certification already exists",
        )
    cert = CertificationModel(name=cert_in.name)
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


@router.get(
    "/",
    response_model=List[CertificationRead],
    dependencies=[Depends(get_current_user)],
)
async def list_certifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CertificationModel))
    return result.scalars().all()


@router.get(
    "/{cert_id}",
    response_model=CertificationRead,
    dependencies=[Depends(get_current_user)],
)
async def get_certification(cert_id: int, db: AsyncSession = Depends(get_db)):
    cert = await db.get(CertificationModel, cert_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found"
        )
    return cert


@router.put(
    "/{cert_id}",
    response_model=CertificationRead,
    dependencies=[Depends(get_current_moderator)],
)
async def update_certification(
    cert_id: int, cert_in: CertificationUpdate, db: AsyncSession = Depends(get_db)
):
    cert = await db.get(CertificationModel, cert_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found"
        )
    existing = await db.scalar(
        select(CertificationModel).where(
            CertificationModel.name == cert_in.name, CertificationModel.id != cert_id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certification name already in use",
        )
    cert.name = cert_in.name
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


@router.delete(
    "/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_certification(cert_id: int, db: AsyncSession = Depends(get_db)):
    cert = await db.get(CertificationModel, cert_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found"
        )
    await db.execute(
        sql_delete(CertificationModel).where(CertificationModel.id == cert_id)
    )
    await db.commit()
    return None
