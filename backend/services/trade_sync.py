"""Background trade sync service"""
import asyncio
import logging
from core.database import Database
from core.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class TradeSyncService:
    def __init__(self, db: Database, ws_manager: WebSocketManager):
        self.db = db
        self.ws_manager = ws_manager
        self._ensure_local_user()

    def _ensure_local_user(self):
        """Crear usuario local automaticamente si no existe"""
        try:
            existing = self.db.get_user_by_email("local@tradecopy.app")
            if not existing:
                from core.auth import hash_password
                user_id = self.db.create_user(
                    email="local@tradecopy.app",
                    password_hash=hash_password("localmode2024"),
                    full_name="Usuario Local"
                )
                self.db.update_user_plan(user_id, "pro", None)
                logger.info("Usuario local creado automaticamente con plan Pro")
            else:
                if existing.get("plan") != "pro":
                    self.db.update_user_plan(existing["id"], "pro", None)
                logger.info("Usuario local verificado OK")
        except Exception as e:
            logger.error(f"Error creando usuario local: {e}")

    async def cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(30)
                self._check_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def _check_stale_connections(self):
        logger.debug("Checking stale connections...")
