"""LangChain tools for the autonomous paper agent."""

import json
import contextvars
from typing import Optional
from langchain_core.tools import tool
from loguru import logger

# Context variables for task tracking across tools
_task_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('task_id', default=None)
_stats_ctx: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar('stats', default=None)


def set_task_id(task_id: Optional[str]) -> None:
    _task_id_ctx.set(task_id)


def get_stats() -> dict:
    stats = _stats_ctx.get()
    if stats is None:
        stats = {"papers_found": 0, "papers_analyzed": 0, "papers_relevant": 0, "papers_saved": 0}
        _stats_ctx.set(stats)
    return stats


async def _send_progress(step: str, progress: int, message: str):
    task_id = _task_id_ctx.get()
    logger.debug(f"Progress: step={step}, progress={progress}, task_id={task_id}, msg={message}")
    if task_id:
        try:
            from backend.api.websocket import send_progress
            await send_progress(task_id, step, progress, message)
        except Exception as e:
            logger.warning(f"Failed to send progress: {e}")
    else:
        logger.warning(f"No task_id for progress: {step} {progress} {message}")


@tool
async def get_user_interests() -> str:
    """Get the user's active research interests. Call this first to understand what topics to search for."""
    try:
        from backend.models.database import get_session_factory, UserInterest
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(UserInterest).where(UserInterest.is_active == True)
            )
            interests = result.scalars().all()

        return json.dumps([{
            "id": i.id,
            "topic": i.topic,
            "description": i.description,
            "keywords": i.keywords or [],
            "categories": i.categories or [],
            "weight": i.weight,
        } for i in interests])
    except Exception as e:
        logger.error(f"get_user_interests failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def get_user_feedback_summary() -> str:
    """Get a summary of the user's past feedback (bookmarked, read, skipped papers) to learn their preferences. Use this to guide search strategy."""
    try:
        from backend.models.database import get_session_factory, Paper
        from sqlalchemy import select, func

        factory = get_session_factory()
        async with factory() as session:
            # Count by status
            total = (await session.execute(select(func.count(Paper.id)))).scalar() or 0
            bookmarked = (await session.execute(
                select(func.count(Paper.id)).where(Paper.is_bookmarked == True)
            )).scalar() or 0
            read = (await session.execute(
                select(func.count(Paper.id)).where(Paper.is_read == True)
            )).scalar() or 0

            # Top categories among bookmarked papers
            bm_result = await session.execute(
                select(Paper).where(Paper.is_bookmarked == True).order_by(Paper.created_at.desc()).limit(10)
            )
            bm_papers = bm_result.scalars().all()

            category_counts = {}
            for p in bm_papers:
                for cat in (p.categories or []):
                    category_counts[cat] = category_counts.get(cat, 0) + 1
            top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            # Recent bookmarked titles
            recent_titles = [p.title for p in bm_papers[:5]]

            # Average relevance of bookmarked vs non-bookmarked
            avg_bm = (await session.execute(
                select(func.avg(Paper.relevance_score)).where(Paper.is_bookmarked == True)
            )).scalar()
            avg_nbm = (await session.execute(
                select(func.avg(Paper.relevance_score)).where(Paper.is_bookmarked == False)
            )).scalar()

        return json.dumps({
            "total_papers": total,
            "total_bookmarked": bookmarked,
            "total_read": read,
            "top_bookmarked_categories": top_categories,
            "avg_relevance_bookmarked": round(avg_bm, 2) if avg_bm else None,
            "avg_relevance_not_bookmarked": round(avg_nbm, 2) if avg_nbm else None,
            "recent_bookmarked_titles": recent_titles,
        })
    except Exception as e:
        logger.error(f"get_user_feedback_summary failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def search_arxiv(
    keywords: list[str],
    categories: list[str],
    days_back: int = 7,
    max_results: int = 30,
) -> str:
    """Search arXiv for recent papers matching keywords and categories. Returns a list of papers with title, arxiv_id, abstract snippet, authors, and categories."""
    logger.info(f"TOOL search_arxiv: keywords={keywords}, categories={categories}, days_back={days_back}")
    try:
        await _send_progress("fetch", 15, f"Searching arXiv: {', '.join(keywords[:3])}...")
        from backend.services.arxiv_service import get_arxiv_service

        arxiv_service = get_arxiv_service()
        papers = await arxiv_service.search_papers(
            categories=categories if categories else None,
            keywords=keywords,
            days_back=days_back,
            max_results=max_results,
        )

        seen = set()
        results = []
        for p in papers:
            info = arxiv_service.extract_paper_info(p)
            if info["arxiv_id"] not in seen:
                seen.add(info["arxiv_id"])
                results.append({
                    "arxiv_id": info["arxiv_id"],
                    "title": info["title"],
                    "abstract": info["abstract"][:500],
                    "authors": info["authors"][:5],
                    "categories": info["categories"],
                    "pdf_url": info["pdf_url"],
                    "published_date": str(info["published_date"]),
                })

        stats = get_stats()
        stats["papers_found"] += len(results)
        await _send_progress("fetch", 25, f"Found {len(results)} papers")
        return json.dumps(results)
    except Exception as e:
        logger.error(f"search_arxiv failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def check_paper_exists(arxiv_id: str) -> str:
    """Check if a paper already exists in the database. Use this before analyzing to skip duplicates."""
    logger.info(f"TOOL check_paper_exists: {arxiv_id}")
    try:
        from backend.models.database import get_session_factory, Paper
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
            paper = result.scalar_one_or_none()

        if paper:
            return json.dumps({"exists": True, "arxiv_id": arxiv_id, "title": paper.title, "is_downloaded": paper.is_downloaded})
        return json.dumps({"exists": False, "arxiv_id": arxiv_id})
    except Exception as e:
        logger.error(f"check_paper_exists failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def check_relevance(title: str, abstract: str, categories: list[str]) -> str:
    """Quickly check if a paper is relevant to the user's interests. Returns a relevance score (0-1). Use this before full analysis to filter out irrelevant papers."""
    logger.info(f"TOOL check_relevance: {title[:50]}...")
    try:
        from backend.services.llm_service import get_llm_service
        from backend.models.database import get_session_factory, UserInterest
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(UserInterest).where(UserInterest.is_active == True)
            )
            interests = result.scalars().all()

        interest_dicts = [{"topic": i.topic, "description": i.description or "", "keywords": i.keywords or []} for i in interests]

        llm_service = get_llm_service()
        check = await llm_service.check_relevance(
            title=title, abstract=abstract, categories=categories, interests=interest_dicts,
        )
        return json.dumps({"is_relevant": check.is_relevant, "score": check.score, "reason": check.reason})
    except Exception as e:
        logger.error(f"check_relevance failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def analyze_paper(
    arxiv_id: str,
    title: str,
    abstract: str,
    authors: list[str],
    categories: list[str],
) -> str:
    """Fully analyze a paper: generate AI summary, key findings, methodology, and relevance score. Use this for papers that pass the relevance check."""
    logger.info(f"TOOL analyze_paper: {arxiv_id} - {title[:50]}...")
    try:
        await _send_progress("analyze", 40, f"Analyzing: {title[:40]}...")
        from backend.services.llm_service import get_llm_service

        llm_service = get_llm_service()
        summary = await llm_service.generate_summary(
            title=title, abstract=abstract, authors=authors, categories=categories,
        )

        stats = get_stats()
        stats["papers_analyzed"] += 1
        if summary.relevance_score >= 0.6:
            stats["papers_relevant"] += 1

        return json.dumps({
            "arxiv_id": arxiv_id,
            "summary": summary.summary,
            "summary_zh": summary.summary_zh,
            "key_findings": summary.key_findings,
            "methodology": summary.methodology,
            "relevance_score": summary.relevance_score,
            "relevance_reason": summary.relevance_reason,
        })
    except Exception as e:
        logger.error(f"analyze_paper failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def download_and_save_paper(
    arxiv_id: str,
    title: str,
    abstract: str,
    authors: list[str],
    categories: list[str],
    published_date: str,
    pdf_url: str,
    ai_summary: str,
    ai_summary_zh: str,
    key_findings: list[str],
    relevance_score: float,
    relevance_reason: str,
) -> str:
    """Download the PDF and save a paper to the database. Only call this for papers with relevance_score >= 0.6."""
    logger.info(f"TOOL download_and_save_paper: {arxiv_id} - {title[:50]}...")
    try:
        from backend.models.database import get_session_factory, Paper, PaperRecommendation
        from backend.services.vector_store import get_vector_store
        from backend.services.pdf_service import get_pdf_service
        from backend.services.arxiv_service import get_arxiv_service
        from sqlalchemy import select
        from datetime import datetime

        await _send_progress("save", 70, f"Saving: {title[:40]}...")

        factory = get_session_factory()
        vector_store = get_vector_store()
        pdf_service = get_pdf_service()

        async with factory() as session:
            # Check exists
            result = await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
            if result.scalar_one_or_none():
                return json.dumps({"status": "exists", "arxiv_id": arxiv_id, "message": "Paper already in database"})

            # Download PDF directly using pdf_url
            pdf_path = None
            full_text = None
            is_downloaded = False

            if pdf_url:
                try:
                    from backend.core.config import get_settings
                    settings = get_settings()
                    settings.papers_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"{arxiv_id.replace('/', '_')}.pdf"
                    pdf_path = settings.papers_dir / filename

                    if not pdf_path.exists():
                        import httpx as httpx_lib
                        async with httpx_lib.AsyncClient() as client:
                            response = await client.get(pdf_url, follow_redirects=True, timeout=60.0)
                            response.raise_for_status()
                            pdf_path.write_bytes(response.content)

                    is_downloaded = True
                    full_text = pdf_service.extract_text(pdf_path)
                except Exception as e:
                    logger.warning(f"PDF download failed for {arxiv_id}: {e}")
                    is_downloaded = False

            # Parse published_date
            try:
                pub_date = datetime.fromisoformat(str(published_date).replace("Z", "+00:00"))
            except Exception:
                pub_date = datetime.utcnow()

            # Save to DB
            paper = Paper(
                arxiv_id=arxiv_id, title=title, authors=authors, abstract=abstract,
                categories=categories, published_date=pub_date, pdf_url=pdf_url,
                local_pdf_path=str(pdf_path) if pdf_path else None,
                ai_summary=ai_summary, ai_summary_zh=ai_summary_zh,
                key_findings=key_findings, relevance_score=relevance_score,
                is_downloaded=is_downloaded,
            )
            session.add(paper)
            await session.flush()

            recommendation = PaperRecommendation(
                paper_id=paper.id, score=relevance_score, reason=relevance_reason,
            )
            session.add(recommendation)
            await session.commit()
            paper_id = paper.id

        # Index in vector store
        try:
            await vector_store.add_paper(arxiv_id=arxiv_id, title=title, abstract=abstract)
            if full_text:
                chunks = pdf_service.chunk_text(full_text)
                if chunks:
                    await vector_store.add_paper_chunks(arxiv_id=arxiv_id, title=title, chunks=chunks)
        except Exception as e:
            logger.warning(f"Vector store indexing failed: {e}")

        stats = get_stats()
        stats["papers_saved"] += 1

        await _send_progress("save", 85, f"Saved: {title[:40]}")
        return json.dumps({"status": "saved", "arxiv_id": arxiv_id, "paper_id": paper_id, "is_downloaded": is_downloaded})
    except Exception as e:
        logger.error(f"download_and_save_paper failed: {e}")
        return json.dumps({"error": str(e)})
