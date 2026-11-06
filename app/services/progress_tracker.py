"""Real-time progress broadcasting manager (Bonus 6.2)."""

import asyncio
from typing import Dict, List, Optional
from fastapi import WebSocket
from app.utils.logger import logger


class ProgressTracker:
    """Manages active WebSocket connections per batch ID to broadcast live progress."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create lock within the running event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def connect(self, batch_id: str, websocket: WebSocket) -> None:
        """Register a client websocket connection."""
        await websocket.accept()
        async with self._get_lock():
            if batch_id not in self._connections:
                self._connections[batch_id] = []
            self._connections[batch_id].append(websocket)
        logger.info(f"WebSocket client connected to stream batch: {batch_id}")

    async def disconnect(self, batch_id: str, websocket: WebSocket) -> None:
        """Remove a client websocket connection."""
        async with self._get_lock():
            if batch_id in self._connections:
                if websocket in self._connections[batch_id]:
                    self._connections[batch_id].remove(websocket)
                if not self._connections[batch_id]:
                    del self._connections[batch_id]
        logger.info(f"WebSocket client disconnected from batch: {batch_id}")

    async def broadcast(self, batch_id: str, payload: dict) -> None:
        """Broadcast status update to all connected clients for a batch."""
        # Short-circuit if no connections registered (most common path)
        if batch_id not in self._connections:
            return

        async with self._get_lock():
            targets = list(self._connections.get(batch_id, []))

        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.debug(f"Failed to send WS message to client: {exc}")
                await self.disconnect(batch_id, ws)


progress_tracker = ProgressTracker()
