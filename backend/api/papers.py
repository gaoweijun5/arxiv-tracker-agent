"""Papers API endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.models.database import get_db, Paper
from backend.services.vector_store import get_vector_store

router = APIRouter(prefix="/papers", tags=["papers"])


class PaperResponse(BaseModel):
    """Paper response model."""
    id: int
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: Optional[datetime]
    pdf_url: Optional[str]
    ai_summary: Optional[str]
    ai_summary_zh: Optional[str]
    key_findings: Optional[list[str]]
    relevance_score: Optional[float]
    is_downloaded: bool
    is_read: bool
    is_bookmarked: bool
    created_at: Optional[datetime]


class PaperListResponse(BaseModel):
    """Paginated paper list response."""
    papers: list[PaperResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaperListResponse)
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    is_read: Optional[bool] = None,
    is_bookmarked: Optional[bool] = None,
    sort_by: str = Query("created_at", regex="^(created_at|relevance_score|published_date)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    """List papers with filtering and pagination."""
    query = select(Paper)

    # Apply filters
    if category:
        query = query.where(Paper.categories.contains([category]))
    if is_read is not None:
        query = query.where(Paper.is_read == is_read)
    if is_bookmarked is not None:
        query = query.where(Paper.is_bookmarked == is_bookmarked)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Apply sorting
    sort_column = getattr(Paper, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    papers = result.scalars().all()

    return PaperListResponse(
        papers=[PaperResponse(**p.to_dict()) for p in papers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific paper by ID."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return PaperResponse(**paper.to_dict())


@router.put("/{paper_id}/read")
async def mark_paper_read(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a paper as read."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.is_read = True
    await db.commit()

    return {"message": "Paper marked as read"}


@router.put("/{paper_id}/bookmark")
async def toggle_bookmark(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle paper bookmark status."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.is_bookmarked = not paper.is_bookmarked
    await db.commit()

    return {"message": "Bookmark toggled", "is_bookmarked": paper.is_bookmarked}


@router.put("/{paper_id}/relevance")
async def set_relevance(
    paper_id: int,
    is_relevant: bool,
    db: AsyncSession = Depends(get_db),
):
    """Set paper relevance (user feedback)."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.is_relevant = is_relevant
    await db.commit()

    return {"message": "Relevance updated", "is_relevant": is_relevant}


async def _delete_paper_full(paper, db):
    """Delete a paper and all related data."""
    from backend.models.database import PaperRecommendation, Conversation

    # Delete related recommendations
    recs_result = await db.execute(
        select(PaperRecommendation).where(PaperRecommendation.paper_id == paper.id)
    )
    for rec in recs_result.scalars().all():
        await db.delete(rec)

    # Delete related conversations
    convs_result = await db.execute(
        select(Conversation).where(Conversation.paper_id == paper.id)
    )
    for conv in convs_result.scalars().all():
        await db.delete(conv)

    # Delete from vector store
    vector_store = get_vector_store()
    await vector_store.delete_paper(paper.arxiv_id)

    # Delete PDF if exists
    if paper.local_pdf_path:
        from pathlib import Path
        pdf_path = Path(paper.local_pdf_path)
        if pdf_path.exists():
            pdf_path.unlink()

    # Delete from database
    await db.delete(paper)


@router.post("/batch-delete")
async def batch_delete_papers(request: dict, db: AsyncSession = Depends(get_db)):
    """Delete multiple papers by IDs."""
    paper_ids = request.get("paper_ids", [])
    if not paper_ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    result = await db.execute(select(Paper).where(Paper.id.in_(paper_ids)))
    papers = result.scalars().all()

    deleted = 0
    for paper in papers:
        await _delete_paper_full(paper, db)
        deleted += 1

    await db.commit()
    return {"message": f"Deleted {deleted} papers", "deleted": deleted}


@router.delete("/{paper_id}")
async def delete_paper(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a paper from database and vector store."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    await _delete_paper_full(paper, db)
    await db.commit()

    return {"message": "Paper deleted", "arxiv_id": paper.arxiv_id}


@router.post("/{paper_id}/download")
async def download_paper_pdf(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Download and process paper PDF for RAG."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.is_downloaded:
        return {"message": "Paper already downloaded", "arxiv_id": paper.arxiv_id}

    if not paper.pdf_url:
        raise HTTPException(status_code=400, detail="No PDF URL available")

    try:
        from backend.services.pdf_service import get_pdf_service
        from backend.services.vector_store import get_vector_store
        from backend.core.config import get_settings
        import httpx
        from pathlib import Path

        pdf_service = get_pdf_service()
        vector_store = get_vector_store()
        settings = get_settings()

        # Download PDF directly using the URL
        settings.papers_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = settings.papers_dir / f"{paper.arxiv_id.replace('/', '_')}.pdf"

        if not pdf_path.exists():
            logger.info(f"Downloading PDF from {paper.pdf_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(paper.pdf_url, follow_redirects=True, timeout=60.0)
                response.raise_for_status()
                pdf_path.write_bytes(response.content)

        # Extract text
        full_text = pdf_service.extract_text(pdf_path)
        if not full_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from PDF")

        # Chunk and store in vector DB
        chunks = pdf_service.chunk_text(full_text)
        if chunks:
            await vector_store.add_paper_chunks(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                chunks=chunks,
            )

        # Update database
        paper.local_pdf_path = str(pdf_path)
        paper.is_downloaded = True
        await db.commit()

        return {
            "message": "PDF downloaded and processed",
            "arxiv_id": paper.arxiv_id,
            "text_length": len(full_text),
            "chunks": len(chunks),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_papers(
    query: str,
    k: int = Query(10, ge=1, le=50),
):
    """Search papers using semantic similarity."""
    vector_store = get_vector_store()
    results = await vector_store.search_similar_papers(query=query, k=k)

    return {"results": results, "query": query}
