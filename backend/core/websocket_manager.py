"""WebSocket manager - multi-tenant rooms by user_id"""
import json
import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.connections:
            self.connections[user_id] = []
        self.connections[user_id].append(websocket)
        logger.info(f"WS connected: user={user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.connections:
            self.connections[user_id].discard(websocket) if hasattr(self.connections[user_id], 'discard') else None
            try:
                self.connections[user_id].remove(websocket)
            except ValueError:
                pass

    async def send_to_user(self, user_id: str, data: dict):
        dead = []
        for ws in self.connections.get(str(user_id), []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, str(user_id))

    async def broadcast(self, data: dict):
        for user_id in list(self.connections.keys()):
            await self.send_to_user(user_id, data)
