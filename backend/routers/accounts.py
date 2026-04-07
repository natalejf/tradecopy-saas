"""Accounts CRUD router"""
import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from core.auth import get_current_user
from core.database import Database

router = APIRouter()
db = Database()


class AccountCreate(BaseModel):
    name: str
    login: int
    server: str
    broker: Optional[str] = None
    role: str  # "master" or "follower"
    lot_multiplier: float = 1.0
    fixed_lot: Optional[float] = None
    max_lot: Optional[float] = None
    copy_sl: bool = True
    copy_tp: bool = True
    reverse: bool = False


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    lot_multiplier: Optional[float] = None
    fixed_lot: Optional[float] = None
    max_lot: Optional[float] = None
    copy_sl: Optional[bool] = None
    copy_tp: Optional[bool] = None
    reverse: Optional[bool] = None
    active: Optional[bool] = None


class GroupCreate(BaseModel):
    name: str
    master_account_id: int


class SymbolMappingCreate(BaseModel):
    master_symbol: str
    follower_symbol: str
    account_id: int


PLAN_LIMITS = {"free": 2, "starter": 5, "pro": 20, "enterprise": 999}


@router.get("")
async def get_accounts(current_user=Depends(get_current_user)):
    return db.get_user_accounts(current_user["id"])


@router.post("")
async def create_account(account: AccountCreate, current_user=Depends(get_current_user)):
    if account.role not in ["master", "follower"]:
        raise HTTPException(400, "Role must be 'master' or 'follower'")

    existing = db.get_user_accounts(current_user["id"])
    plan = current_user.get("plan", "free")
    limit = PLAN_LIMITS.get(plan, 2)
    if len(existing) >= limit:
        raise HTTPException(403, f"Account limit reached for plan '{plan}'. Upgrade to add more.")

    account_id = db.add_account({
        **account.dict(),
        "user_id": current_user["id"],
    })
    new_account = db.get_account(account_id)
    return {"account": new_account, "ea_token": new_account["ea_token"]}


@router.get("/{account_id}")
async def get_account(account_id: int, current_user=Depends(get_current_user)):
    acc = db.get_account(account_id)
    if not acc or acc["user_id"] != current_user["id"]:
        raise HTTPException(404, "Account not found")
    return acc


@router.patch("/{account_id}")
async def update_account(account_id: int, updates: AccountUpdate, current_user=Depends(get_current_user)):
    acc = db.get_account(account_id)
    if not acc or acc["user_id"] != current_user["id"]:
        raise HTTPException(404, "Account not found")
    data = {k: v for k, v in updates.dict().items() if v is not None}
    db.update_account(account_id, data)
    return {"success": True}


@router.delete("/{account_id}")
async def delete_account(account_id: int, current_user=Depends(get_current_user)):
    acc = db.get_account(account_id)
    if not acc or acc["user_id"] != current_user["id"]:
        raise HTTPException(404, "Account not found")
    db.delete_account(account_id)
    return {"success": True}


@router.post("/{account_id}/regenerate-token")
async def regenerate_ea_token(account_id: int, current_user=Depends(get_current_user)):
    acc = db.get_account(account_id)
    if not acc or acc["user_id"] != current_user["id"]:
        raise HTTPException(404, "Account not found")
    new_token = "ea_" + secrets.token_hex(20)
    db.update_account(account_id, {"ea_token": new_token})
    return {"ea_token": new_token}


# ── Groups ──────────────────────────────────────────────────────
@router.get("/groups/all")
async def get_groups(current_user=Depends(get_current_user)):
    return db.get_user_groups(current_user["id"])


@router.post("/groups")
async def create_group(group: GroupCreate, current_user=Depends(get_current_user)):
    master = db.get_account(group.master_account_id)
    if not master or master["user_id"] != current_user["id"] or master["role"] != "master":
        raise HTTPException(400, "Invalid master account")
    group_id = db.create_group(current_user["id"], group.name, group.master_account_id)
    return {"id": group_id}


@router.post("/groups/{group_id}/followers/{account_id}")
async def add_follower(group_id: int, account_id: int, current_user=Depends(get_current_user)):
    acc = db.get_account(account_id)
    if not acc or acc["user_id"] != current_user["id"]:
        raise HTTPException(404, "Account not found")
    db.add_follower_to_group(group_id, account_id)
    return {"success": True}


@router.delete("/groups/{group_id}/followers/{account_id}")
async def remove_follower(group_id: int, account_id: int, current_user=Depends(get_current_user)):
    db.remove_follower_from_group(group_id, account_id)
    return {"success": True}


# ── Symbol Mappings ──────────────────────────────────────────────
@router.get("/symbol-mappings")
async def get_mappings(current_user=Depends(get_current_user)):
    return db.get_symbol_mappings(current_user["id"])


@router.post("/symbol-mappings")
async def add_mapping(mapping: SymbolMappingCreate, current_user=Depends(get_current_user)):
    mid = db.add_symbol_mapping({**mapping.dict(), "user_id": current_user["id"]})
    return {"id": mid}


@router.delete("/symbol-mappings/{mapping_id}")
async def delete_mapping(mapping_id: int, current_user=Depends(get_current_user)):
    db.delete_symbol_mapping(mapping_id, current_user["id"])
    return {"success": True}
