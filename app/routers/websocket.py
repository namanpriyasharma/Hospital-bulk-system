"""WebSocket router for live progress updates (Bonus 6.2)."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.progress_tracker import progress_tracker
from app.utils.logger import logger

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/batch/{batch_id}")
async def websocket_batch_progress(websocket: WebSocket, batch_id: str):
    """
    WebSocket endpoint for real-time progress streaming.
    Clients connect to /ws/batch/{batch_id} to receive instantaneous JSON status events.
    """
    await progress_tracker.connect(batch_id, websocket)
    try:
        while True:
            # Keep connection alive; clients can also send ping messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await progress_tracker.disconnect(batch_id, websocket)
    except Exception as exc:
        logger.debug(f"WebSocket connection closed for batch {batch_id}: {exc}")
        await progress_tracker.disconnect(batch_id, websocket)
