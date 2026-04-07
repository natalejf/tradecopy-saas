"""
TradeCopy SaaS Platform - Main Backend
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from core.database import Database
from core.websocket_manager import WebSocketManager
from core.auth import verify_token, get_current_user
from routers import accounts, trades, subscriptions, webhooks, admin
from services.trade_sync import TradeSyncService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

db = Database()
ws_manager = WebSocketManager()
sync_service: Optional[TradeSyncService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_service
    logger.info("Starting TradeCopy SaaS Platform...")
    db.init_db()
    sync_service = TradeSyncService(db, ws_manager)
    task = asyncio.create_task(sync_service.cleanup_loop())
    app.state.sync_service = sync_service
    app.state.db = db
    app.state.ws_manager = ws_manager
    logger.info("Platform started successfully")
    yield
    logger.info("Shutting down...")
    task.cancel()


app = FastAPI(title="TradeCopy SaaS", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(webhooks.router, prefix="/api/ea", tags=["EA Webhook"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/status")
async def get_status(current_user=Depends(get_current_user)):
    stats = db.get_user_stats(current_user["id"])
    return {
        "status": "running",
        "user_id": current_user["id"],
        "plan": current_user["plan"],
        "accounts": stats["accounts"],
        "trades_today": stats["trades_today"],
        "total_trades": stats["total_trades"],
        "last_update": datetime.utcnow().isoformat()
    }


@app.websocket("/ws/{user_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str):
    user = verify_token(token)
    if not user or str(user["id"]) != user_id:
        await websocket.close(code=4001)
        return
    await ws_manager.connect(websocket, user_id)
    try:
        await websocket.send_json({
            "type": "init",
            "accounts": db.get_user_accounts(user["id"]),
            "timestamp": datetime.utcnow().isoformat()
        })
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)


# Serve frontend
_fe = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(_fe):
    app.mount("/assets", StaticFiles(directory=_fe), name="frontend")


@app.get("/", include_in_schema=False)
async def serve_index():
    index = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(index)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)