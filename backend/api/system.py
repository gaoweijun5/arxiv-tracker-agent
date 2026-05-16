"""System API endpoints."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.models.database import get_db, Paper, UserInterest, PaperRecommendation, FetchLog

router = APIRouter(prefix="/system", tags=["system"])


class SystemStats(BaseModel):
    """System statistics."""
    total_papers: int
    total_interests: int
    total_recommendations: int
    unread_papers: int
    bookmarked_papers: int
    last_fetch: Optional[datetime]


class FetchRequest(BaseModel):
    """Fetch request with options."""
    interest_ids: Optional[list[int]] = None  # Specific interest IDs to use
    days_back: int = 7  # How many days back to search
    max_results: int = 30  # Max results per interest


@router.get("/stats", response_model=SystemStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get system statistics."""
    # Paper stats
    result = await db.execute(select(func.count(Paper.id)))
    total_papers = result.scalar() or 0

    result = await db.execute(select(func.count(Paper.id)).where(Paper.is_read == False))
    unread_papers = result.scalar() or 0

    result = await db.execute(select(func.count(Paper.id)).where(Paper.is_bookmarked == True))
    bookmarked_papers = result.scalar() or 0

    # Interest stats
    result = await db.execute(
        select(func.count(UserInterest.id)).where(UserInterest.is_active == True)
    )
    total_interests = result.scalar() or 0

    # Recommendation stats
    result = await db.execute(select(func.count(PaperRecommendation.id)))
    total_recommendations = result.scalar() or 0

    # Last fetch
    result = await db.execute(
        select(FetchLog).order_by(FetchLog.fetch_date.desc()).limit(1)
    )
    last_fetch_log = result.scalar_one_or_none()
    last_fetch = last_fetch_log.fetch_date if last_fetch_log else None

    return SystemStats(
        total_papers=total_papers,
        total_interests=total_interests,
        total_recommendations=total_recommendations,
        unread_papers=unread_papers,
        bookmarked_papers=bookmarked_papers,
        last_fetch=last_fetch,
    )


async def run_fetch_workflow(
    interests_data: list[dict],
    days_back: int = 7,
    max_results: int = 30,
    task_id: str = None,
):
    """Background task to run the fetch workflow with progress updates."""
    from backend.agents import get_paper_workflow
    from backend.models.database import get_session_factory, FetchLog
    from backend.api.websocket import send_progress, send_complete, send_error

    logger.info(f"Starting fetch workflow (days_back={days_back}, max_results={max_results})")

    workflow = get_paper_workflow()
    state = {
        "user_interests": interests_data,
        "categories": [],
        "keywords": [],
        "fetched_papers": [],
        "analyzed_papers": [],
        "relevant_papers": [],
        "recommendations": [],
        "messages": [],
        "daily_digest": "",
        "error": None,
        "days_back": days_back,
        "max_results": max_results,
        "task_id": task_id,
    }

    try:
        # Send progress: Starting
        if task_id:
            await send_progress(task_id, "start", 0, "Starting paper fetch...")

        result = await workflow.ainvoke(state)

        # Log the fetch
        factory = get_session_factory()
        async with factory() as db:
            log = FetchLog(
                fetch_date=datetime.utcnow(),
                source="manual",
                categories_fetched=[i.get("topic") for i in interests_data],
                papers_found=len(result.get("fetched_papers", [])),
                papers_relevant=len(result.get("relevant_papers", [])),
                papers_downloaded=len([p for p in result.get("relevant_papers", []) if p.get("is_downloaded")]),
                status="success",
            )
            db.add(log)
            await db.commit()

        logger.info(f"Fetch completed: {log.papers_found} found, {log.papers_relevant} relevant")

        # Send completion
        if task_id:
            await send_complete(task_id, {
                "papers_found": log.papers_found,
                "papers_relevant": log.papers_relevant,
                "papers_downloaded": log.papers_downloaded,
                "status": "success",
            })

    except Exception as e:
        logger.error(f"Fetch failed: {e}")

        # Send error
        if task_id:
            await send_error(task_id, str(e))

        # Log failure
        factory = get_session_factory()
        async with factory() as db:
            log = FetchLog(
                fetch_date=datetime.utcnow(),
                source="manual",
                categories_fetched=[],
                papers_found=0,
                papers_relevant=0,
                papers_downloaded=0,
                status="failed",
                error_message=str(e),
            )
            db.add(log)
            await db.commit()


@router.post("/fetch")
async def trigger_fetch(
    request: FetchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a paper fetch with options."""
    from backend.models.database import UserInterest

    # Get interests
    if request.interest_ids:
        # Use specific interests
        result = await db.execute(
            select(UserInterest).where(UserInterest.id.in_(request.interest_ids))
        )
    else:
        # Use all active interests
        result = await db.execute(
            select(UserInterest).where(UserInterest.is_active == True)
        )
    interests = result.scalars().all()

    if not interests:
        return {"status": "no_interests", "message": "No interests found. Please add research interests first."}

    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())[:8]

    # Run workflow in background
    interests_data = [i.to_dict() for i in interests]
    background_tasks.add_task(
        run_fetch_workflow,
        interests_data,
        request.days_back,
        request.max_results,
        task_id,
    )

    return {
        "status": "started",
        "task_id": task_id,
        "message": f"Fetch started for {len(interests)} interests (last {request.days_back} days)",
        "interests": [{"id": i.id, "topic": i.topic} for i in interests],
        "days_back": request.days_back,
        "max_results": request.max_results,
    }


@router.get("/interests")
async def list_interests_for_fetch(db: AsyncSession = Depends(get_db)):
    """List all interests for fetch selection."""
    result = await db.execute(select(UserInterest).where(UserInterest.is_active == True))
    interests = result.scalars().all()

    return [
        {"id": i.id, "topic": i.topic, "keywords": i.keywords}
        for i in interests
    ]


@router.get("/fetch-logs")
async def get_fetch_logs(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get recent fetch logs."""
    result = await db.execute(
        select(FetchLog).order_by(FetchLog.fetch_date.desc()).limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "fetch_date": log.fetch_date.strftime("%Y-%m-%dT%H:%M:%SZ") if log.fetch_date else None,
            "source": getattr(log, "source", "manual") or "manual",
            "categories_fetched": log.categories_fetched,
            "papers_found": log.papers_found,
            "papers_relevant": log.papers_relevant,
            "papers_downloaded": log.papers_downloaded,
            "status": log.status,
            "error_message": log.error_message,
        }
        for log in logs
    ]


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@router.get("/scheduler")
async def get_scheduler_config():
    """Get scheduler configuration."""
    from backend.scheduler import get_scheduler_config
    config = await get_scheduler_config()
    return config


@router.put("/scheduler")
async def update_scheduler(
    hour: int = Query(ge=0, le=23),
    minute: int = Query(ge=0, le=59),
    is_enabled: bool = True,
):
    """Update scheduler configuration."""
    from backend.scheduler import update_scheduler_config

    await update_scheduler_config(hour, minute, is_enabled)

    return {
        "message": "Scheduler updated",
        "hour": hour,
        "minute": minute,
        "is_enabled": is_enabled,
    }
