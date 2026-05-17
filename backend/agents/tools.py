"""LangChain tools for the autonomous paper agent."""

import json
import asyncio
import contextvars
from typing import Optional
from langchain_core.tools import tool
from loguru import logger

# Context variables for task tracking across tools
_task_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('task_id', default=None)
_stats_ctx: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar('stats', default=None)
_selected_interests_ctx: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar('selected_interests', default=None)
_cancel_event_ctx: contextvars.ContextVar[Optional[asyncio.Event]] = contextvars.ContextVar('cancel_event', default=None)


def set_task_id(task_id: Optional[str]) -> None:
    _task_id_ctx.set(task_id)


def set_selected_interests(interests: Optional[list]) -> None:
    _selected_interests_ctx.set(interests)


def set_cancel_event(event: asyncio.Event) -> None:
    _cancel_event_ctx.set(event)


def _get_interest_value(interest, key: str):
    if isinstance(interest, dict):
        return interest.get(key)
    return getattr(interest, key, None)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _dedupe_strings(values) -> list[str]:
    result = []
    seen = set()
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _selected_interest_scope(selected_interests: Optional[list]) -> tuple[list[str], list[str]]:
    """Build the hard search boundary for the current selected interests."""
    if not selected_interests:
        return [], []

    keywords = []
    categories = []
    for interest in selected_interests:
        topic = _get_interest_value(interest, "topic")
        if topic:
            keywords.append(topic)
        keywords.extend(_as_list(_get_interest_value(interest, "keywords")))
        categories.extend(_as_list(_get_interest_value(interest, "categories")))

    return _dedupe_strings(keywords), _dedupe_strings(categories)


def _interest_dicts_from_selected(selected_interests: list) -> list[dict]:
    return [
        {
            "topic": _get_interest_value(interest, "topic") or "",
            "description": _get_interest_value(interest, "description") or "",
            "keywords": _as_list(_get_interest_value(interest, "keywords")),
        }
        for interest in selected_interests
    ]


async def _get_relevance_interest_dicts() -> list[dict]:
    """Return interests used by relevance checks, scoped to the current run."""
    selected = _selected_interests_ctx.get()
    if selected is not None:
        return _interest_dicts_from_selected(selected)

    from backend.models.database import get_session_factory, UserInterest
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserInterest).where(UserInterest.is_active == True)
        )
        interests = result.scalars().all()

    return [
        {
            "topic": i.topic,
            "description": i.description or "",
            "keywords": i.keywords or [],
        }
        for i in interests
    ]


def _constrain_search_to_selected_interests(
    keywords: Optional[list[str]],
    categories: Optional[list[str]],
    selected_interests: Optional[list],
) -> tuple[list[str], list[str], bool]:
    """Return search params that cannot escape the selected interests."""
    requested_keywords = _dedupe_strings(keywords)
    requested_categories = _dedupe_strings(categories)

    if selected_interests is None:
        return requested_keywords, requested_categories, False

    allowed_keywords, allowed_categories = _selected_interest_scope(selected_interests)
    if not selected_interests:
        return [], [], True

    allowed_keyword_lookup = {kw.casefold(): kw for kw in allowed_keywords}
    matched_keywords = [
        allowed_keyword_lookup[kw.casefold()]
        for kw in requested_keywords
        if kw.casefold() in allowed_keyword_lookup
    ]
    effective_keywords = _dedupe_strings(matched_keywords or allowed_keywords)

    if allowed_categories:
        allowed_category_lookup = {cat.casefold(): cat for cat in allowed_categories}
        matched_categories = [
            allowed_category_lookup[cat.casefold()]
            for cat in requested_categories
            if cat.casefold() in allowed_category_lookup
        ]
        effective_categories = _dedupe_strings(matched_categories or allowed_categories)
    else:
        effective_categories = []

    constrained = (
        requested_keywords != effective_keywords
        or requested_categories != effective_categories
    )
    return effective_keywords, effective_categories, constrained


def check_cancelled():
    """Raise CancelledError if the current task has been cancelled."""
    event = _cancel_event_ctx.get()
    if event and event.is_set():
        raise asyncio.CancelledError("Cancelled by user")


def get_stats() -> dict:
    stats = _stats_ctx.get()
    if stats is None:
        stats = {
            "papers_found": 0,
            "papers_analyzed": 0,
            "papers_relevant": 0,
            "papers_saved": 0,
            "saved_paper_ids": [],
        }
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
    """Get the user's selected research interests. Call this first to understand what topics to search for."""
    check_cancelled()
    try:
        # Use pre-selected interests if available (user chose specific topics in UI)
        selected = _selected_interests_ctx.get()
        if selected is not None:
            return json.dumps(selected)

        # Fallback: get all active interests from database
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
    """Get a summary of the user's past feedback for the SELECTED interests only."""
    check_cancelled()
    try:
        from backend.models.database import get_session_factory, Paper
        from sqlalchemy import select, func

        selected = _selected_interests_ctx.get()

        factory = get_session_factory()
        async with factory() as session:
            # Build category filter from selected interests
            if selected:
                selected_categories = set()
                for interest in selected:
                    for cat in (interest.get("categories") or []):
                        selected_categories.add(cat)

                # Filter bookmarked papers by selected categories
                all_bm = await session.execute(
                    select(Paper).where(Paper.is_bookmarked == True)
                )
                bm_papers = [p for p in all_bm.scalars().all()
                             if any(cat in selected_categories for cat in (p.categories or []))]

                total = (await session.execute(select(func.count(Paper.id)))).scalar() or 0
                bookmarked = len(bm_papers)
                read = (await session.execute(
                    select(func.count(Paper.id)).where(Paper.is_read == True)
                )).scalar() or 0
            else:
                bm_result = await session.execute(
                    select(Paper).where(Paper.is_bookmarked == True).order_by(Paper.created_at.desc()).limit(10)
                )
                bm_papers = bm_result.scalars().all()
                total = (await session.execute(select(func.count(Paper.id)))).scalar() or 0
                bookmarked = len(bm_papers)
                read = (await session.execute(
                    select(func.count(Paper.id)).where(Paper.is_read == True)
                )).scalar() or 0

            # Categories from filtered bookmarked papers
            category_counts = {}
            for p in bm_papers:
                for cat in (p.categories or []):
                    category_counts[cat] = category_counts.get(cat, 0) + 1
            top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            recent_titles = [p.title for p in bm_papers[:5]]

        return json.dumps({
            "total_papers": total,
            "total_bookmarked": bookmarked,
            "total_read": read,
            "top_bookmarked_categories": top_categories,
            "recent_bookmarked_titles": recent_titles,
            "note": "These are based on your selected interests only" if selected else "",
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
    check_cancelled()
    logger.info(f"TOOL search_arxiv: keywords={keywords}, categories={categories}, days_back={days_back}")
    try:
        selected = _selected_interests_ctx.get()
        effective_keywords, effective_categories, constrained = _constrain_search_to_selected_interests(
            keywords=keywords,
            categories=categories,
            selected_interests=selected,
        )

        if selected is not None and not effective_keywords:
            logger.warning("Refusing broad arXiv search because no selected-interest keywords are available")
            return json.dumps({
                "error": "No selected-interest keywords available; refusing to run a broad search.",
            })

        if constrained:
            logger.info(
                "Constrained arXiv search to selected interests: "
                f"effective_keywords={effective_keywords}, effective_categories={effective_categories}"
            )

        progress_terms = effective_keywords[:3] or effective_categories[:3] or ["recent papers"]
        await _send_progress("fetch", 15, f"Searching arXiv: {', '.join(progress_terms)}...")
        from backend.services.arxiv_service import get_arxiv_service

        arxiv_service = get_arxiv_service()
        papers = await arxiv_service.search_papers(
            categories=effective_categories if effective_categories else None,
            keywords=effective_keywords if effective_keywords else None,
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
    check_cancelled()
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
    check_cancelled()
    logger.info(f"TOOL check_relevance: {title[:50]}...")
    try:
        from backend.services.llm_service import get_llm_service

        interest_dicts = await _get_relevance_interest_dicts()
        if not interest_dicts:
            return json.dumps({
                "is_relevant": False,
                "score": 0.0,
                "reason": "No selected interests available for relevance checking",
            })

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
    """Fully analyze a paper and score relevance against the current selected interests."""
    check_cancelled()
    logger.info(f"TOOL analyze_paper: {arxiv_id} - {title[:50]}...")
    try:
        await _send_progress("analyze", 40, f"Analyzing: {title[:40]}...")
        from backend.services.llm_service import get_llm_service

        llm_service = get_llm_service()
        interest_dicts = await _get_relevance_interest_dicts()
        summary = await llm_service.generate_summary(
            title=title, abstract=abstract, authors=authors, categories=categories,
        )
        if interest_dicts:
            relevance = await llm_service.check_relevance(
                title=title,
                abstract=abstract,
                categories=categories,
                interests=interest_dicts,
            )
            relevance_score = relevance.score
            relevance_reason = relevance.reason
            is_relevant = relevance.is_relevant
        else:
            relevance_score = 0.0
            relevance_reason = "No selected interests available for relevance checking"
            is_relevant = False

        stats = get_stats()
        stats["papers_analyzed"] += 1
        if relevance_score >= 0.6:
            stats["papers_relevant"] += 1

        return json.dumps({
            "arxiv_id": arxiv_id,
            "summary": summary.summary,
            "summary_zh": summary.summary_zh,
            "key_findings": summary.key_findings,
            "methodology": summary.methodology,
            "relevance_score": relevance_score,
            "relevance_reason": relevance_reason,
            "is_relevant": is_relevant,
        })
    except Exception as e:
        logger.error(f"analyze_paper failed: {e}")
        return json.dumps({"error": str(e)})


@tool
async def save_paper(
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
    """Save relevant paper metadata without downloading the PDF. Only call this for papers with relevance_score >= 0.6."""
    check_cancelled()
    logger.info(f"TOOL save_paper: {arxiv_id} - {title[:50]}...")
    try:
        from backend.models.database import get_session_factory, Paper, PaperRecommendation
        from backend.services.vector_store import get_vector_store
        from backend.services.llm_service import get_llm_service
        from sqlalchemy import select
        from datetime import datetime

        if relevance_score < 0.6:
            return json.dumps({
                "status": "skipped",
                "arxiv_id": arxiv_id,
                "message": "Paper relevance score is below the save threshold",
                "relevance_score": relevance_score,
            })

        interest_dicts = await _get_relevance_interest_dicts()
        if not interest_dicts:
            return json.dumps({
                "status": "skipped",
                "arxiv_id": arxiv_id,
                "message": "No selected interests available for save-time relevance gate",
                "relevance_score": 0.0,
            })

        relevance = await get_llm_service().check_relevance(
            title=title,
            abstract=abstract,
            categories=categories,
            interests=interest_dicts,
        )
        if not relevance.is_relevant or relevance.score < 0.6:
            return json.dumps({
                "status": "skipped",
                "arxiv_id": arxiv_id,
                "message": "Paper did not pass the selected-interest save gate",
                "relevance_score": relevance.score,
                "relevance_reason": relevance.reason,
            })

        relevance_score = relevance.score
        relevance_reason = relevance.reason

        await _send_progress("save", 70, f"Saving: {title[:40]}...")

        factory = get_session_factory()
        vector_store = get_vector_store()

        async with factory() as session:
            # Check exists
            result = await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
            if result.scalar_one_or_none():
                return json.dumps({"status": "exists", "arxiv_id": arxiv_id, "message": "Paper already in database"})

            # Parse published_date
            try:
                pub_date = datetime.fromisoformat(str(published_date).replace("Z", "+00:00"))
            except Exception:
                pub_date = datetime.utcnow()

            # Save to DB
            paper = Paper(
                arxiv_id=arxiv_id, title=title, authors=authors, abstract=abstract,
                categories=categories, published_date=pub_date, pdf_url=pdf_url,
                local_pdf_path=None,
                ai_summary=ai_summary, ai_summary_zh=ai_summary_zh,
                key_findings=key_findings, relevance_score=relevance_score,
                is_downloaded=False,
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
        except Exception as e:
            logger.warning(f"Vector store indexing failed: {e}")

        stats = get_stats()
        stats["papers_saved"] += 1
        stats.setdefault("saved_paper_ids", []).append(paper_id)

        await _send_progress("save", 85, f"Saved: {title[:40]}")
        return json.dumps({"status": "saved", "arxiv_id": arxiv_id, "paper_id": paper_id, "is_downloaded": False})
    except Exception as e:
        logger.error(f"save_paper failed: {e}")
        return json.dumps({"error": str(e)})
