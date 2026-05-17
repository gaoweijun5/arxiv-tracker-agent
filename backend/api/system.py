"""System API endpoints."""

import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.models.database import get_db, Paper, UserInterest, PaperRecommendation, FetchLog

router = APIRouter(prefix="/system", tags=["system"])

# Registry of running background tasks
_running_tasks: dict[str, asyncio.Task] = {}
_cancel_events: dict[str, asyncio.Event] = {}


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
    cancel_event: asyncio.Event = None,
):
    """Background task to run the autonomous paper agent."""
    from backend.agents.paper_agent import run_paper_agent
    from backend.models.database import get_session_factory, FetchLog
    from backend.api.websocket import send_complete, send_error

    logger.info(f"Starting paper agent (days_back={days_back}, max_results={max_results})")

    try:
        result = await run_paper_agent(
            interests_data=interests_data,
            days_back=days_back,
            max_results=max_results,
            task_id=task_id,
            cancel_event=cancel_event,
        )

        # Log the fetch
        factory = get_session_factory()
        async with factory() as db:
            log = FetchLog(
                fetch_date=datetime.utcnow(),
                source="manual",
                categories_fetched=[i.get("topic") for i in interests_data],
                papers_found=result.get("papers_found", 0),
                papers_relevant=result.get("papers_relevant", 0),
                papers_downloaded=result.get("papers_saved", 0),
                status=result.get("status", "success"),
                error_message=result.get("error"),
            )
            db.add(log)
            await db.commit()

        logger.info(f"Agent completed: {result.get('papers_found', 0)} found, {result.get('papers_saved', 0)} saved")

        if task_id:
            payload = {
                "papers_found": result.get("papers_found", 0),
                "papers_relevant": result.get("papers_relevant", 0),
                "papers_downloaded": result.get("papers_saved", 0),
                "status": result.get("status", "success"),
            }
            if result.get("status") == "failed":
                await send_error(task_id, result.get("error") or "Fetch failed")
            else:
                await send_complete(task_id, payload)

    except Exception as e:
        logger.error(f"Fetch failed: {e}")

        if task_id:
            await send_error(task_id, str(e))

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

    # Get interests. An omitted interest_ids means "all active"; an explicit
    # empty list means the caller selected nothing and should not fan out.
    if request.interest_ids is not None:
        if not request.interest_ids:
            raise HTTPException(status_code=400, detail="Select at least one interest.")

        # Use specific interests
        interest_ids = list(dict.fromkeys(request.interest_ids))
        result = await db.execute(
            select(UserInterest).where(
                UserInterest.id.in_(interest_ids),
                UserInterest.is_active == True,
            )
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
    cancel_event = asyncio.Event()
    _cancel_events[task_id] = cancel_event
    task = asyncio.create_task(
        run_fetch_workflow(
            interests_data,
            request.days_back,
            request.max_results,
            task_id,
            cancel_event,
        )
    )
    _running_tasks[task_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_id, None))
    task.add_done_callback(lambda t: _cancel_events.pop(task_id, None))

    return {
        "status": "started",
        "task_id": task_id,
        "message": f"Fetch started for {len(interests)} interests (last {request.days_back} days)",
        "interests": [{"id": i.id, "topic": i.topic} for i in interests],
        "days_back": request.days_back,
        "max_results": request.max_results,
    }


@router.post("/fetch/{task_id}/cancel")
async def cancel_fetch(task_id: str):
    """Cancel a running fetch task."""
    task = _running_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or already completed")

    # Set cancel event so tools can check it
    cancel_event = _cancel_events.get(task_id)
    if cancel_event:
        cancel_event.set()

    task.cancel()
    _running_tasks.pop(task_id, None)
    _cancel_events.pop(task_id, None)
    logger.info(f"Cancelled fetch task: {task_id}")

    # Try to send cancellation via WebSocket
    try:
        from backend.api.websocket import send_error
        await send_error(task_id, "Cancelled by user")
    except Exception:
        pass

    return {"message": "Fetch cancelled", "task_id": task_id}


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
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Get recent fetch logs with pagination."""
    from sqlalchemy import func

    # Get total count
    total = (await db.execute(select(func.count(FetchLog.id)))).scalar() or 0

    # Get paginated results
    offset = (page - 1) * limit
    result = await db.execute(
        select(FetchLog).order_by(FetchLog.fetch_date.desc()).offset(offset).limit(limit)
    )
    logs = result.scalars().all()

    return {
        "logs": [
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
        ],
        "total": total,
        "page": page,
        "page_size": limit,
    }


@router.delete("/fetch-logs/{log_id}")
async def delete_fetch_log(log_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a fetch log entry."""
    result = await db.execute(select(FetchLog).where(FetchLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Fetch log not found")
    await db.delete(log)
    await db.commit()
    return {"message": "Fetch log deleted"}


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
