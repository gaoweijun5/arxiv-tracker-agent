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
        from backend.services.arxiv_service import get_arxiv_service
        from backend.services.hybrid_retrieval_service import get_hybrid_retrieval_service

        arxiv_service = get_arxiv_service()
        hybrid_retrieval = get_hybrid_retrieval_service()

        pdf_path = await arxiv_service.download_pdf_url(paper.pdf_url, paper.arxiv_id)
        if not pdf_path:
            raise HTTPException(status_code=502, detail="Failed to download PDF from arXiv")

        # Parse with Docling and store paragraph-aware chunks in SQLite FTS + Chroma.
        chunks, parsed = await hybrid_retrieval.replace_paper_chunks_from_pdf(
            paper_id=paper.id,
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            pdf_path=pdf_path,
        )
        if not chunks:
            raise HTTPException(status_code=500, detail="Failed to generate chunks from PDF")

        # Update database
        paper.local_pdf_path = str(pdf_path)
        paper.is_downloaded = True
        await db.commit()

        return {
            "message": "PDF downloaded and processed",
            "arxiv_id": paper.arxiv_id,
            "text_length": len(parsed.full_text),
            "chunks": len(chunks),
            "parser": parsed.parser,
            "chunker": parsed.chunker,
            "table_blocks_removed": parsed.table_blocks_removed,
            "table_captions_added": parsed.table_captions_added,
            "figure_captions_added": parsed.figure_captions_added,
            "caption_errors": parsed.caption_errors,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-chunks")
async def rebuild_chunks(force: bool = False, db: AsyncSession = Depends(get_db)):
    """Backfill or rebuild chunks for downloaded papers."""
    from backend.services.hybrid_retrieval_service import get_hybrid_retrieval_service
    from pathlib import Path

    hybrid_retrieval = get_hybrid_retrieval_service()

    result = await db.execute(
        select(Paper).where(Paper.is_downloaded.is_(True), Paper.local_pdf_path.isnot(None))
    )
    papers = result.scalars().all()

    processed = 0
    skipped = 0
    errors = []

    for paper in papers:
        has_chunks = await hybrid_retrieval.has_chunks(paper.id)
        if has_chunks and not force:
            skipped += 1
            continue

        pdf_path = Path(paper.local_pdf_path)
        if not pdf_path.exists():
            errors.append(f"{paper.arxiv_id}: PDF file not found")
            continue

        try:
            chunks, parsed = await hybrid_retrieval.replace_paper_chunks_from_pdf(
                paper_id=paper.id,
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                pdf_path=pdf_path,
            )
            if not chunks:
                errors.append(f"{paper.arxiv_id}: Docling generated 0 chunks")
                continue
            logger.info(
                f"Rebuilt {len(chunks)} chunks for {paper.arxiv_id}; "
                f"dropped {parsed.table_blocks_removed} table blocks; "
                f"captioned {parsed.table_captions_added} tables and "
                f"{parsed.figure_captions_added} figures"
            )
            processed += 1
        except Exception as e:
            errors.append(f"{paper.arxiv_id}: {e}")

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }


@router.post("/search")
async def search_papers(
    query: str,
    k: int = Query(10, ge=1, le=50),
):
    """Search papers using semantic similarity."""
    vector_store = get_vector_store()
    results = await vector_store.search_similar_papers(query=query, k=k)

    return {"results": results, "query": query}


@router.get("/{paper_id}/similar")
async def get_similar_papers(
    paper_id: int,
    k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get papers similar to the given paper using vector search."""
    # Get the current paper
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Search vector store using paper's title + abstract as query
    vector_store = get_vector_store()
    query = f"{paper.title}\n\n{paper.abstract}"
    search_results = await vector_store.search_papers(
        query=query,
        k=k + 5,  # fetch extra to account for filtering
        filter_dict={"type": "paper"},
    )

    # Filter out current paper and collect arxiv_ids
    similar_items = []
    for doc, score in search_results:
        doc_arxiv_id = doc.metadata.get("arxiv_id", "")
        if doc_arxiv_id == paper.arxiv_id:
            continue
        similar_items.append({"arxiv_id": doc_arxiv_id, "score": score})
        if len(similar_items) >= k:
            break

    if not similar_items:
        return {"papers": [], "total": 0}

    # Fetch full paper info from database
    arxiv_ids = [item["arxiv_id"] for item in similar_items]
    db_result = await db.execute(select(Paper).where(Paper.arxiv_id.in_(arxiv_ids)))
    db_papers = {p.arxiv_id: p for p in db_result.scalars().all()}

    # Build response with similarity scores
    papers = []
    for item in similar_items:
        p = db_papers.get(item["arxiv_id"])
        if not p:
            continue
        papers.append({
            "id": p.id,
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "authors": p.authors,
            "abstract": p.abstract,
            "ai_summary": p.ai_summary,
            "relevance_score": p.relevance_score,
            "is_bookmarked": p.is_bookmarked,
            "is_read": p.is_read,
            "similarity_score": round(1.0 / (1.0 + item["score"]), 4),
        })

    return {"papers": papers, "total": len(papers)}
