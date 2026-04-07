"""
EA Webhook Router - The CORE of cloud sync
MT5 EA posts here to send positions/trades to the cloud
Followers poll here to get what to copy
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from core.database import Database
from core.websocket_manager import WebSocketManager

router = APIRouter()
db = Database()
logger = logging.getLogger(__name__)

# Shared ws_manager reference (set from main.py)
_ws_manager: Optional[WebSocketManager] = None


def set_ws_manager(manager: WebSocketManager):
    global _ws_manager
    _ws_manager = manager


class PositionData(BaseModel):
    ticket: int
    symbol: str
    action: str  # "buy" or "sell"
    lots: float
    open_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    profit: Optional[float] = None
    opened_at: Optional[str] = None


class MasterHeartbeat(BaseModel):
    """Master EA sends this periodically with all open positions"""
    balance: float
    equity: float
    currency: str = "USD"
    positions: List[PositionData] = []


class TradeEvent(BaseModel):
    """Master EA sends this on open/close/modify"""
    event: str  # "open", "close", "modify"
    ticket: int
    symbol: str
    action: Optional[str] = None
    lots: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    profit: Optional[float] = None
    opened_at: Optional[str] = None


class FollowerAck(BaseModel):
    """Follower EA confirms it copied a trade"""
    master_ticket: int
    follower_ticket: int
    symbol: str
    lots: float
    status: str  # "copied", "failed"
    error: Optional[str] = None


def get_account_from_token(ea_token: str) -> Dict:
    account = db.get_account_by_ea_token(ea_token)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid EA token")
    if not account["active"]:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return account


# ── MASTER EA endpoints ─────────────────────────────────────────

@router.post("/master/heartbeat")
async def master_heartbeat(data: MasterHeartbeat, x_ea_token: str = Header(...)):
    """
    Master EA calls this every ~1s with all open positions.
    We diff against stored positions to detect opens/closes.
    """
    account = get_account_from_token(x_ea_token)
    if account["role"] != "master":
        raise HTTPException(400, "Only master accounts can use this endpoint")

    # Update account info
    db.update_account(account["id"], {
        "connected": 1,
        "last_ping": datetime.utcnow().isoformat(),
        "balance": data.balance,
        "equity": data.equity,
        "currency": data.currency,
    })

    # Get stored positions
    stored = {p["ticket"]: p for p in db.get_open_positions(account["id"])}
    incoming = {p.ticket: p for p in data.positions}

    new_tickets = set(incoming.keys()) - set(stored.keys())
    closed_tickets = set(stored.keys()) - set(incoming.keys())

    events = []

    # New positions opened
    for ticket in new_tickets:
        pos = incoming[ticket]
        db.upsert_position(account["id"], {
            "ticket": pos.ticket, "symbol": pos.symbol, "action": pos.action,
            "lots": pos.lots, "open_price": pos.open_price,
            "sl": pos.sl, "tp": pos.tp, "profit": pos.profit,
            "opened_at": pos.opened_at or datetime.utcnow().isoformat()
        })
        events.append({
            "event": "open",
            "master_account_id": account["id"],
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "action": pos.action,
            "lots": pos.lots,
            "open_price": pos.open_price,
            "sl": pos.sl,
            "tp": pos.tp,
        })
        logger.info(f"New position detected: {pos.symbol} {pos.action} {pos.lots} lots (ticket={pos.ticket})")

    # Closed positions
    for ticket in closed_tickets:
        db.remove_position(account["id"], ticket)
        events.append({
            "event": "close",
            "master_account_id": account["id"],
            "ticket": ticket,
        })
        logger.info(f"Position closed: ticket={ticket}")

    # Update existing
    for ticket in set(incoming.keys()) & set(stored.keys()):
        pos = incoming[ticket]
        db.upsert_position(account["id"], {
            "ticket": pos.ticket, "symbol": pos.symbol, "action": pos.action,
            "lots": pos.lots, "open_price": pos.open_price,
            "sl": pos.sl, "tp": pos.tp, "profit": pos.profit,
            "opened_at": stored[ticket]["opened_at"]
        })

    # Broadcast events to user's WS clients
    if events and _ws_manager:
        await _ws_manager.send_to_user(str(account["user_id"]), {
            "type": "position_events",
            "events": events
        })

    return {"status": "ok", "new": len(new_tickets), "closed": len(closed_tickets)}


@router.post("/master/trade-event")
async def master_trade_event(event: TradeEvent, x_ea_token: str = Header(...)):
    """Master EA sends individual trade events (open/close/modify)"""
    account = get_account_from_token(x_ea_token)
    if account["role"] != "master":
        raise HTTPException(400, "Only master accounts can use this endpoint")

    db.update_account(account["id"], {
        "connected": 1,
        "last_ping": datetime.utcnow().isoformat(),
    })

    if event.event == "open":
        db.upsert_position(account["id"], {
            "ticket": event.ticket, "symbol": event.symbol,
            "action": event.action, "lots": event.lots,
            "open_price": event.open_price, "sl": event.sl,
            "tp": event.tp, "profit": event.profit,
            "opened_at": event.opened_at or datetime.utcnow().isoformat()
        })
    elif event.event == "close":
        db.remove_position(account["id"], event.ticket)
        db.log_trade({
            "user_id": account["user_id"],
            "master_account_id": account["id"],
            "master_ticket": event.ticket,
            "symbol": event.symbol,
            "action": event.action or "unknown",
            "lots": event.lots or 0,
            "open_price": event.open_price,
            "close_price": event.close_price,
            "profit": event.profit,
            "status": "closed",
            "opened_at": event.opened_at,
        })

    if _ws_manager:
        await _ws_manager.send_to_user(str(account["user_id"]), {
            "type": "trade_event",
            "event": event.dict()
        })

    return {"status": "ok"}


# ── FOLLOWER EA endpoints ────────────────────────────────────────

@router.get("/follower/pending")
async def follower_get_pending(x_ea_token: str = Header(...)):
    """
    Follower EA polls this to get trades to copy.
    Returns open positions from the master(s) linked via copy groups.
    """
    account = get_account_from_token(x_ea_token)
    if account["role"] != "follower":
        raise HTTPException(400, "Only follower accounts can use this endpoint")

    # Update last ping
    db.update_account(account["id"], {
        "connected": 1,
        "last_ping": datetime.utcnow().isoformat(),
    })

    # Find which masters this follower is linked to
    masters = []
    groups = db.get_user_groups(account["user_id"])
    for group in groups:
        followers_in_group = db.get_account_followers(group["master_account_id"])
        if any(f["id"] == account["id"] for f in followers_in_group):
            masters.append(group["master_account_id"])

    if not masters:
        return {"positions": [], "settings": {}}

    all_positions = []
    for master_id in masters:
        positions = db.get_open_positions(master_id)
        for pos in positions:
            all_positions.append({
                **pos,
                "master_account_id": master_id,
            })

    # Get symbol mappings for this follower
    mappings = db.get_symbol_mappings(account["user_id"])
    sym_map = {m["master_symbol"]: m["follower_symbol"]
               for m in mappings if m["account_id"] == account["id"]}

    # Apply symbol mappings
    for pos in all_positions:
        if pos["symbol"] in sym_map:
            pos["mapped_symbol"] = sym_map[pos["symbol"]]
        else:
            pos["mapped_symbol"] = pos["symbol"]

    settings = {
        "lot_multiplier": account["lot_multiplier"],
        "fixed_lot": account["fixed_lot"],
        "max_lot": account["max_lot"],
        "copy_sl": bool(account["copy_sl"]),
        "copy_tp": bool(account["copy_tp"]),
        "reverse": bool(account["reverse"]),
    }

    return {"positions": all_positions, "settings": settings}


@router.post("/follower/ack")
async def follower_acknowledge(ack: FollowerAck, x_ea_token: str = Header(...)):
    """Follower EA confirms it copied a trade"""
    account = get_account_from_token(x_ea_token)

    # Find the master position
    master_pos = None
    groups = db.get_user_groups(account["user_id"])
    for group in groups:
        positions = db.get_open_positions(group["master_account_id"])
        for pos in positions:
            if pos["ticket"] == ack.master_ticket:
                master_pos = pos
                break

    db.log_trade({
        "user_id": account["user_id"],
        "master_account_id": master_pos["master_account_id"] if master_pos else 0,
        "follower_account_id": account["id"],
        "master_ticket": ack.master_ticket,
        "follower_ticket": ack.follower_ticket,
        "symbol": ack.symbol,
        "action": master_pos["action"] if master_pos else "unknown",
        "lots": ack.lots,
        "status": ack.status,
        "opened_at": datetime.utcnow().isoformat(),
    })

    return {"status": "ok"}


@router.post("/follower/heartbeat")
async def follower_heartbeat(
    balance: float, equity: float, currency: str = "USD",
    x_ea_token: str = Header(...)
):
    """Follower EA heartbeat - keeps connection alive"""
    account = get_account_from_token(x_ea_token)
    db.update_account(account["id"], {
        "connected": 1,
        "last_ping": datetime.utcnow().isoformat(),
        "balance": balance,
        "equity": equity,
        "currency": currency,
    })
    return {"status": "ok"}
