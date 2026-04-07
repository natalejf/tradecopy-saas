"""Background trade sync service"""
import asyncio
import logging
from datetime import datetime, timedelta
from core.database import Database
from core.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class TradeSyncService:
    def __init__(self, db: Database, ws_manager: WebSocketManager):
        self.db = db
        self.ws_manager = ws_manager

    async def cleanup_loop(self):
        """Periodically mark accounts as disconnected if no heartbeat"""
        while True:
            try:
                await asyncio.sleep(30)
                self._check_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def _check_stale_connections(self):
        """Mark accounts as disconnected if last ping > 60s ago"""
        # This would query all accounts and check last_ping
        # Simplified version
        logger.debug("Checking stale connections...")
