"""WebSocket endpoint for real-time progress updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(tags=["websocket"])

# Store active connections
active_connections: dict[str, WebSocket] = {}


async def send_progress(task_id: str, step: str, progress: int, message: str, data: dict = None):
    """Send progress update to connected clients."""
    if task_id in active_connections:
        try:
            await active_connections[task_id].send_json({
                "type": "progress",
                "step": step,
                "progress": progress,
                "message": message,
                "data": data or {},
            })
        except Exception:
            pass


async def send_complete(task_id: str, result: dict):
    """Send completion notification."""
    if task_id in active_connections:
        try:
            await active_connections[task_id].send_json({
                "type": "complete",
                "result": result,
            })
        except Exception:
            pass


async def send_error(task_id: str, error: str):
    """Send error notification."""
    if task_id in active_connections:
        try:
            await active_connections[task_id].send_json({
                "type": "error",
                "error": error,
            })
        except Exception:
            pass


@router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for progress updates."""
    await websocket.accept()
    active_connections[task_id] = websocket
    logger.info(f"WebSocket connected: {task_id}")

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {task_id}")
    finally:
        active_connections.pop(task_id, None)
