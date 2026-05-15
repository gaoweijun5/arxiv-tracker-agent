"""User interests API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db, UserInterest
from backend.services.vector_store import get_vector_store

router = APIRouter(prefix="/interests", tags=["interests"])


class InterestCreate(BaseModel):
    """Interest creation model."""
    topic: str
    description: Optional[str] = None
    keywords: list[str] = []
    categories: list[str] = []
    weight: float = 1.0


class InterestUpdate(BaseModel):
    """Interest update model."""
    topic: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    weight: Optional[float] = None
    is_active: Optional[bool] = None


class InterestResponse(BaseModel):
    """Interest response model."""
    id: int
    topic: str
    description: Optional[str]
    keywords: list[str]
    categories: list[str]
    weight: float
    is_active: bool


@router.get("", response_model=list[InterestResponse])
async def list_interests(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all user interests."""
    query = select(UserInterest)
    if active_only:
        query = query.where(UserInterest.is_active == True)

    result = await db.execute(query)
    interests = result.scalars().all()

    return [InterestResponse(**i.to_dict()) for i in interests]


@router.post("", response_model=InterestResponse)
async def create_interest(
    interest: InterestCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user interest."""
    db_interest = UserInterest(
        topic=interest.topic,
        description=interest.description,
        keywords=interest.keywords,
        categories=interest.categories,
        weight=interest.weight,
    )
    db.add(db_interest)
    await db.commit()
    await db.refresh(db_interest)

    return InterestResponse(**db_interest.to_dict())


@router.get("/{interest_id}", response_model=InterestResponse)
async def get_interest(interest_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific interest."""
    result = await db.execute(select(UserInterest).where(UserInterest.id == interest_id))
    interest = result.scalar_one_or_none()

    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    return InterestResponse(**interest.to_dict())


@router.put("/{interest_id}", response_model=InterestResponse)
async def update_interest(
    interest_id: int,
    update: InterestUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing interest."""
    result = await db.execute(select(UserInterest).where(UserInterest.id == interest_id))
    interest = result.scalar_one_or_none()

    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    # Update fields
    if update.topic is not None:
        interest.topic = update.topic
    if update.description is not None:
        interest.description = update.description
    if update.keywords is not None:
        interest.keywords = update.keywords
    if update.categories is not None:
        interest.categories = update.categories
    if update.weight is not None:
        interest.weight = update.weight
    if update.is_active is not None:
        interest.is_active = update.is_active

    await db.commit()
    await db.refresh(interest)

    return InterestResponse(**interest.to_dict())


@router.delete("/{interest_id}")
async def delete_interest(interest_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an interest."""
    result = await db.execute(select(UserInterest).where(UserInterest.id == interest_id))
    interest = result.scalar_one_or_none()

    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    # Soft delete
    interest.is_active = False
    await db.commit()

    return {"message": "Interest deleted"}
