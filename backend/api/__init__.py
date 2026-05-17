"""API package for ArXiv Tracker Agent."""

from fastapi import APIRouter

from .papers import router as papers_router
from .interests import router as interests_router
from .recommendations import router as recommendations_router
from .conversations import router as conversations_router
from .system import router as system_router
from .reports import router as reports_router
from .websocket import router as websocket_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(papers_router)
api_router.include_router(interests_router)
api_router.include_router(recommendations_router)
api_router.include_router(conversations_router)
api_router.include_router(system_router)
api_router.include_router(reports_router)

# WebSocket router (no prefix)
ws_router = websocket_router

__all__ = ["api_router", "ws_router"]
