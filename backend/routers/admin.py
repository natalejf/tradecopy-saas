"""Admin router"""
import os
from fastapi import APIRouter, HTTPException, Depends, Header
from core.database import Database

router = APIRouter()
db = Database()
ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin-secret-change-me")


def require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Forbidden")


@router.get("/users")
async def list_users(_=Depends(require_admin)):
    return db.get_all_users()


@router.post("/users/{user_id}/plan")
async def set_plan(user_id: int, plan: str, expires_at: str = None, _=Depends(require_admin)):
    db.update_user_plan(user_id, plan, expires_at)
    return {"success": True}
