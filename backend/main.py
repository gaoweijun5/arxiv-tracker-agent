"""Main FastAPI application for ArXiv Tracker Agent."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.core.config import get_settings
from backend.models.database import init_db
from backend.api import api_router, ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Create data directories
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.papers_dir.mkdir(parents=True, exist_ok=True)
    settings.vectors_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    logger.info("Initializing database...")
    await init_db(settings.database_url)

    # Start scheduler
    logger.info("Starting scheduler...")
    from backend.scheduler import start_scheduler
    scheduler = start_scheduler()

    logger.info(f"ArXiv Tracker Agent started on {settings.app_name}")
    yield

    # Shutdown
    logger.info("Shutting down scheduler...")
    scheduler.shutdown()

    logger.info("ArXiv Tracker Agent stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered arXiv paper tracking and recommendation agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)
    app.include_router(ws_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
