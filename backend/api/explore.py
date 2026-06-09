"""Topic exploration API endpoints."""

import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/explore", tags=["explore"])

# Registry of running exploration tasks
_running_tasks: dict[str, asyncio.Task] = {}
_cancel_events: dict[str, asyncio.Event] = {}


class ExploreRequest(BaseModel):
    """Request model for topic exploration."""
    query: str = Field(..., min_length=3, max_length=500, description="Natural language topic query")
    max_results: int = Field(default=10, ge=1, le=20, description="Maximum number of results")


class ExplorePaper(BaseModel):
    """Paper result from topic exploration."""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: str
    pdf_url: Optional[str] = None
    relevance_score: float
    relevance_reason: str
    summary: str


class ExploreResponse(BaseModel):
    """Response model for topic exploration."""
    status: str
    query: str
    topic_understanding: str
    keywords: list[str]
    expanded_keywords: list[str]
    categories: list[str]
    papers: list[ExplorePaper]
    total_found: int
    total_analyzed: int
    task_id: Optional[str] = None


class SaveExploredPaperRequest(BaseModel):
    """Request to save an explored paper."""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: str
    pdf_url: Optional[str] = None
    relevance_score: float
    relevance_reason: str
    summary: str


class SaveExploredPaperResponse(BaseModel):
    """Response for saving an explored paper."""
    status: str
    message: str
    paper_id: Optional[int] = None
    is_new: bool = True


async def _run_explore_task(
    query: str,
    max_results: int,
    task_id: str,
    cancel_event: asyncio.Event,
):
    """Background task to run topic exploration."""
    from backend.agents.topic_explorer import explore_topic_workflow
    from backend.api.websocket import send_complete, send_error

    try:
        result = await explore_topic_workflow(
            query=query,
            max_results=max_results,
            task_id=task_id,
            cancel_event=cancel_event,
        )

        if result.get("status") == "cancelled":
            await send_error(task_id, "Exploration was cancelled")
        elif result.get("status") == "failed":
            await send_error(task_id, result.get("error", "Exploration failed"))
        else:
            await send_complete(task_id, {
                "type": "explore_result",
                "result": result,
            })

    except Exception as e:
        logger.exception(f"Explore task failed: {e}")
        await send_error(task_id, str(e))


@router.post("", response_model=None)
async def explore_topic(
    request: ExploreRequest,
    background_tasks: BackgroundTasks,
):
    """
    Explore a topic using natural language query.

    This endpoint starts an asynchronous exploration workflow:
    1. LLM understands the topic and extracts keywords
    2. Searches arXiv with multiple strategies
    3. Analyzes and scores papers
    4. Returns recommended papers via WebSocket

    Returns a task_id for tracking progress via WebSocket.
    """
    # Generate task ID
    task_id = str(uuid.uuid4())[:8]

    # Create cancel event
    cancel_event = asyncio.Event()
    _cancel_events[task_id] = cancel_event

    # Start background task
    task = asyncio.create_task(
        _run_explore_task(
            query=request.query,
            max_results=request.max_results,
            task_id=task_id,
            cancel_event=cancel_event,
        )
    )
    _running_tasks[task_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_id, None))
    task.add_done_callback(lambda t: _cancel_events.pop(task_id, None))

    return {
        "status": "started",
        "task_id": task_id,
        "message": f"Exploring topic: {request.query}",
    }


@router.post("/{task_id}/cancel")
async def cancel_explore(task_id: str):
    """Cancel a running exploration task."""
    task = _running_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or already completed")

    # Set cancel event
    cancel_event = _cancel_events.get(task_id)
    if cancel_event:
        cancel_event.set()

    task.cancel()
    _running_tasks.pop(task_id, None)
    _cancel_events.pop(task_id, None)
    logger.info(f"Cancelled explore task: {task_id}")

    return {"message": "Exploration cancelled", "task_id": task_id}


@router.post("/save", response_model=SaveExploredPaperResponse)
async def save_explored_paper(request: SaveExploredPaperRequest):
    """
    Save an explored paper to the database.

    This endpoint saves a paper from exploration results to the user's paper collection.
    It checks for duplicates and creates a recommendation record.
    """
    from backend.models.database import Paper, PaperRecommendation, get_session_factory
    from backend.services.vector_store import get_vector_store
    from sqlalchemy import select
    from datetime import datetime

    factory = get_session_factory()
    vector_store = get_vector_store()

    try:
        async with factory() as session:
            # Check if paper already exists
            result = await session.execute(
                select(Paper).where(Paper.arxiv_id == request.arxiv_id)
            )
            existing_paper = result.scalar_one_or_none()

            if existing_paper:
                return SaveExploredPaperResponse(
                    "exists",
                    "Paper already exists in your collection",
                    paper_id=existing_paper.id,
                    is_new=False,
                )

            # Parse published date
            try:
                pub_date = datetime.fromisoformat(
                    request.published_date.replace("Z", "+00:00")
                )
            except Exception:
                pub_date = datetime.utcnow()

            # Create paper record
            paper = Paper(
                arxiv_id=request.arxiv_id,
                title=request.title,
                authors=request.authors,
                abstract=request.abstract,
                categories=request.categories,
                published_date=pub_date,
                pdf_url=request.pdf_url or "",
                local_pdf_path=None,
                ai_summary=request.summary,
                ai_summary_zh="",
                key_findings=[],
                relevance_score=request.relevance_score,
                is_downloaded=False,
            )
            session.add(paper)
            await session.flush()

            # Create recommendation record
            recommendation = PaperRecommendation(
                paper_id=paper.id,
                interest_id=None,  # No specific interest for explored papers
                score=request.relevance_score,
                reason=request.relevance_reason,
            )
            session.add(recommendation)
            await session.commit()

            paper_id = paper.id

        # Add to vector store (async, non-blocking)
        try:
            await vector_store.add_paper(
                arxiv_id=request.arxiv_id,
                title=request.title,
                abstract=request.abstract,
                metadata={"relevance_score": request.relevance_score},
            )
        except Exception as e:
            logger.warning(f"Failed to add paper to vector store: {e}")

        logger.info(f"Saved explored paper: {request.arxiv_id} (ID: {paper_id})")

        return SaveExploredPaperResponse(
            "saved",
            "Paper saved to your collection",
            paper_id=paper_id,
            is_new=True,
        )

    except Exception as e:
        logger.exception(f"Failed to save explored paper: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save paper: {str(e)}")
