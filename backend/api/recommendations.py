"""Recommendations API endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.database import get_db, PaperRecommendation, Paper

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationResponse(BaseModel):
    """Recommendation response model."""
    id: int
    paper: dict
    score: float
    reason: Optional[str]
    is_viewed: bool
    is_dismissed: bool
    recommended_at: Optional[datetime]


class RecommendationListResponse(BaseModel):
    """Paginated recommendation list response."""
    recommendations: list[RecommendationResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    viewed: Optional[bool] = None,
    dismissed: Optional[bool] = None,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """List paper recommendations."""
    query = select(PaperRecommendation).options(selectinload(PaperRecommendation.paper))

    # Apply filters
    if viewed is not None:
        query = query.where(PaperRecommendation.is_viewed == viewed)
    if dismissed is not None:
        query = query.where(PaperRecommendation.is_dismissed == dismissed)
    if min_score > 0:
        query = query.where(PaperRecommendation.score >= min_score)

    # Sort by score descending, then by date
    query = query.order_by(
        PaperRecommendation.score.desc(),
        PaperRecommendation.recommended_at.desc(),
    )

    # Get total count
    count_result = await db.execute(
        select(func.count(PaperRecommendation.id))
    )
    total = count_result.scalar() or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    recommendations = result.scalars().all()

    return RecommendationListResponse(
        recommendations=[RecommendationResponse(**r.to_dict()) for r in recommendations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/today")
async def get_today_recommendations(db: AsyncSession = Depends(get_db)):
    """Get today's recommendations."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(PaperRecommendation)
        .options(selectinload(PaperRecommendation.paper))
        .where(PaperRecommendation.recommended_at >= today)
        .where(PaperRecommendation.is_dismissed == False)
        .order_by(PaperRecommendation.score.desc())
    )

    result = await db.execute(query)
    recommendations = result.scalars().all()

    return {
        "recommendations": [r.to_dict() for r in recommendations],
        "count": len(recommendations),
        "date": today.isoformat(),
    }


@router.get("/digest")
async def get_daily_digest(db: AsyncSession = Depends(get_db)):
    """Get the daily research digest."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(PaperRecommendation)
        .options(selectinload(PaperRecommendation.paper))
        .where(PaperRecommendation.recommended_at >= today)
        .where(PaperRecommendation.is_dismissed == False)
        .order_by(PaperRecommendation.score.desc())
        .limit(10)
    )

    result = await db.execute(query)
    recommendations = result.scalars().all()

    if not recommendations:
        return {"digest": "No new recommendations today.", "papers": []}

    # Generate digest using LLM
    from backend.services.llm_service import get_llm_service
    llm_service = get_llm_service()

    papers = [
        {
            "title": r.paper.title,
            "ai_summary": r.paper.ai_summary or r.paper.abstract[:200],
        }
        for r in recommendations
        if r.paper
    ]

    try:
        digest = await llm_service.generate_daily_digest(papers)
    except Exception as e:
        digest = f"Found {len(papers)} relevant papers today."

    return {
        "digest": digest,
        "papers": [r.paper.to_dict() for r in recommendations if r.paper],
        "date": today.isoformat(),
    }


@router.put("/{rec_id}/viewed")
async def mark_viewed(rec_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a recommendation as viewed."""
    result = await db.execute(
        select(PaperRecommendation).where(PaperRecommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.is_viewed = True
    await db.commit()

    return {"message": "Recommendation marked as viewed"}


@router.put("/{rec_id}/dismiss")
async def dismiss_recommendation(rec_id: int, db: AsyncSession = Depends(get_db)):
    """Dismiss a recommendation."""
    result = await db.execute(
        select(PaperRecommendation).where(PaperRecommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.is_dismissed = True
    await db.commit()

    return {"message": "Recommendation dismissed"}


async def run_refresh_workflow(interests_data: list[dict]):
    """Background task to refresh recommendations."""
    from backend.agents.paper_agent import run_paper_agent
    from loguru import logger

    logger.info("Starting background refresh workflow...")

    try:
        result = await run_paper_agent(
            interests_data=interests_data,
            task_id=None,
        )
        logger.info(f"Refresh completed: {result.get('papers_saved', 0)} papers saved")
    except Exception as e:
        logger.error(f"Refresh failed: {e}")


@router.post("/refresh")
async def refresh_recommendations(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a refresh of recommendations (runs in background)."""
    from backend.models.database import UserInterest

    # Get active interests
    result = await db.execute(
        select(UserInterest).where(UserInterest.is_active == True)
    )
    interests = result.scalars().all()

    if not interests:
        return {
            "status": "no_interests",
            "message": "No active interests configured. Please add interests first.",
        }

    # Run workflow in background
    interests_data = [i.to_dict() for i in interests]
    background_tasks.add_task(run_refresh_workflow, interests_data)

    return {
        "status": "started",
        "message": f"Refresh started for {len(interests)} interests",
        "interests_count": len(interests),
    }
