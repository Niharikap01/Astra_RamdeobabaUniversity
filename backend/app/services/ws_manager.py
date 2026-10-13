"""WebSocket connection manager for real-time Digital Twin updates."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("nightwatch.ws")


class ConnectionManager:
    """Manages active WebSocket connections grouped by patient_id."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, patient_id: str) -> None:
        """Accept connection and register under patient topic."""
        await websocket.accept()
        if patient_id not in self.active_connections:
            self.active_connections[patient_id] = set()
        self.active_connections[patient_id].add(websocket)
        logger.info(f"WebSocket client connected for patient {patient_id}. Total: {len(self.active_connections[patient_id])}")

    def disconnect(self, websocket: WebSocket, patient_id: str) -> None:
        """Remove connection on close."""
        if patient_id in self.active_connections:
            self.active_connections[patient_id].discard(websocket)
            if not self.active_connections[patient_id]:
                del self.active_connections[patient_id]
        logger.info(f"WebSocket client disconnected for patient {patient_id}")

    async def broadcast_twin_update(self, patient_id: str, payload: dict) -> None:
        """Broadcast updated twin payload to all active clients for patient_id."""
        if patient_id not in self.active_connections:
            return

        dead_connections: List[WebSocket] = []
        for ws in self.active_connections[patient_id]:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.warning(f"Failed to send WS message: {e}")
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws, patient_id)


ws_manager = ConnectionManager()
