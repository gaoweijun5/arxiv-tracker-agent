"""Scheduler for daily paper fetching and recommendations."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from backend.core.config import get_settings


async def daily_paper_fetch():
    """Daily task to fetch and process new papers."""
    logger.info("Starting daily paper fetch...")

    try:
        from backend.models.database import get_session_factory, UserInterest, FetchLog
        from backend.agents import get_paper_workflow
        from sqlalchemy import select
        from datetime import datetime

        factory = get_session_factory()

        async with factory() as session:
            # Get active interests
            result = await session.execute(
                select(UserInterest).where(UserInterest.is_active == True)
            )
            interests = result.scalars().all()

            if not interests:
                logger.warning("No active interests configured")
                return

            # Run the paper workflow
            workflow = get_paper_workflow()
            state = {
                "user_interests": [i.to_dict() for i in interests],
                "categories": [],
                "keywords": [],
                "fetched_papers": [],
                "analyzed_papers": [],
                "relevant_papers": [],
                "recommendations": [],
                "messages": [],
                "daily_digest": "",
                "error": None,
            }

            result = await workflow.ainvoke(state)

            # Log the fetch
            log = FetchLog(
                fetch_date=datetime.utcnow(),
                categories_fetched=[],
                papers_found=len(result.get("fetched_papers", [])),
                papers_relevant=len(result.get("relevant_papers", [])),
                papers_downloaded=len([p for p in result.get("relevant_papers", []) if p.get("is_downloaded")]),
                status="success" if not result.get("error") else "failed",
                error_message=result.get("error"),
            )
            session.add(log)
            await session.commit()

            logger.info(f"Daily fetch complete: {log.papers_found} found, {log.papers_relevant} relevant")

    except Exception as e:
        logger.error(f"Daily paper fetch failed: {e}")


async def cleanup_old_papers():
    """Weekly task to clean up old papers."""
    logger.info("Starting paper cleanup...")

    try:
        from backend.models.database import get_session_factory, Paper
        from sqlalchemy import select, and_
        from datetime import datetime, timedelta

        factory = get_session_factory()

        async with factory() as session:
            # Find papers older than 30 days that aren't bookmarked
            cutoff = datetime.utcnow() - timedelta(days=30)
            result = await session.execute(
                select(Paper).where(
                    and_(
                        Paper.created_at < cutoff,
                        Paper.is_bookmarked == False,
                        Paper.is_read == True,
                    )
                )
            )
            old_papers = result.scalars().all()

            for paper in old_papers:
                # Delete from vector store
                from backend.services.vector_store import get_vector_store
                vector_store = get_vector_store()
                await vector_store.delete_paper(paper.arxiv_id)

                # Delete PDF if exists
                if paper.local_pdf_path:
                    from pathlib import Path
                    pdf_path = Path(paper.local_pdf_path)
                    if pdf_path.exists():
                        pdf_path.unlink()

                await session.delete(paper)

            await session.commit()
            logger.info(f"Cleaned up {len(old_papers)} old papers")

    except Exception as e:
        logger.error(f"Paper cleanup failed: {e}")


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler."""
    settings = get_settings()

    scheduler = AsyncIOScheduler()

    # Daily paper fetch
    scheduler.add_job(
        daily_paper_fetch,
        CronTrigger(
            hour=settings.daily_fetch_hour,
            minute=settings.daily_fetch_minute,
        ),
        id="daily_paper_fetch",
        name="Daily Paper Fetch",
        replace_existing=True,
    )

    # Weekly cleanup (Sunday at 3 AM)
    scheduler.add_job(
        cleanup_old_papers,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_cleanup",
        name="Weekly Paper Cleanup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. Daily fetch at {settings.daily_fetch_hour:02d}:{settings.daily_fetch_minute:02d}")

    return scheduler
