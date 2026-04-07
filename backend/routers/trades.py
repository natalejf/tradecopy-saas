"""Trades history router"""
from fastapi import APIRouter, Depends
from core.auth import get_current_user
from core.database import Database

router = APIRouter()
db = Database()


@router.get("")
async def get_trades(limit: int = 100, offset: int = 0, current_user=Depends(get_current_user)):
    return db.get_user_trades(current_user["id"], limit=limit, offset=offset)


@router.get("/open")
async def get_open_trades(current_user=Depends(get_current_user)):
    accounts = db.get_user_accounts(current_user["id"])
    masters = [a for a in accounts if a["role"] == "master"]
    all_positions = []
    for master in masters:
        positions = db.get_open_positions(master["id"])
        for pos in positions:
            pos["master_name"] = master["name"]
        all_positions.extend(positions)
    return all_positions


@router.get("/stats")
async def get_stats(current_user=Depends(get_current_user)):
    return db.get_user_stats(current_user["id"])
