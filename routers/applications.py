from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatus,
    ApplicationUpdate,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> models.Application:
    application = await db.get(models.Application, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return application


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    status: ApplicationStatus | None = None,
    db: AsyncSession = Depends(get_db),
) -> Sequence[models.Application]:
    statement = select(models.Application)
    if status is not None:
        statement = statement.where(models.Application.status == status)
    result = await db.scalars(statement)
    return result.all()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
)
async def create_application(
    application: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
) -> models.Application:
    created_application = models.Application(**application.model_dump())
    db.add(created_application)
    await db.commit()
    await db.refresh(created_application)
    return created_application


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    application_update: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
) -> models.Application:
    application = await db.get(models.Application, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    update_data = application_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(application, field, value)

    await db.commit()
    await db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    application = await db.get(models.Application, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    await db.delete(application)
    await db.commit()
