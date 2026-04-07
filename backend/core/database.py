"""
Multi-tenant SQLite database (swap for PostgreSQL in production)
"""
import sqlite3
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import os

logger = logging.getLogger(__name__)
DB_PATH = os.environ.get("DATABASE_URL", "tradecopy.db")


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    plan TEXT DEFAULT 'free',
                    plan_expires_at TEXT,
                    api_key TEXT UNIQUE,
                    stripe_customer_id TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    login INTEGER NOT NULL,
                    server TEXT NOT NULL,
                    broker TEXT,
                    role TEXT NOT NULL,
                    ea_token TEXT UNIQUE NOT NULL,
                    lot_multiplier REAL DEFAULT 1.0,
                    fixed_lot REAL,
                    max_lot REAL,
                    copy_sl INTEGER DEFAULT 1,
                    copy_tp INTEGER DEFAULT 1,
                    reverse INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    connected INTEGER DEFAULT 0,
                    last_ping TEXT,
                    balance REAL DEFAULT 0,
                    equity REAL DEFAULT 0,
                    currency TEXT DEFAULT 'USD',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS copy_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    master_account_id INTEGER NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (master_account_id) REFERENCES accounts(id)
                );

                CREATE TABLE IF NOT EXISTS group_followers (
                    group_id INTEGER NOT NULL,
                    account_id INTEGER NOT NULL,
                    PRIMARY KEY (group_id, account_id)
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    master_account_id INTEGER NOT NULL,
                    follower_account_id INTEGER,
                    master_ticket INTEGER,
                    follower_ticket INTEGER,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    lots REAL NOT NULL,
                    open_price REAL,
                    close_price REAL,
                    sl REAL,
                    tp REAL,
                    profit REAL,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    opened_at TEXT,
                    closed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS symbol_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    master_symbol TEXT NOT NULL,
                    follower_symbol TEXT NOT NULL,
                    account_id INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS open_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    master_account_id INTEGER NOT NULL,
                    ticket INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    lots REAL NOT NULL,
                    open_price REAL,
                    sl REAL,
                    tp REAL,
                    profit REAL,
                    opened_at TEXT,
                    last_update TEXT,
                    UNIQUE(master_account_id, ticket)
                );
            """)
            logger.info("Database initialized")

    # ── Users ──────────────────────────────────────────────────────
    def create_user(self, email: str, password_hash: str, full_name: str = None) -> int:
        import secrets
        api_key = "tc_" + secrets.token_hex(24)
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, api_key) VALUES (?,?,?,?)",
                (email, password_hash, full_name, api_key)
            )
            return cur.lastrowid

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE api_key=?", (api_key,)).fetchone()
            return dict(row) if row else None

    def update_user_plan(self, user_id: int, plan: str, expires_at: str):
        with self.get_conn() as conn:
            conn.execute("UPDATE users SET plan=?, plan_expires_at=? WHERE id=?", (plan, expires_at, user_id))

    # ── Accounts ───────────────────────────────────────────────────
    def add_account(self, data: Dict) -> int:
        import secrets
        ea_token = data.get("ea_token") or "ea_" + secrets.token_hex(20)
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO accounts (user_id, name, login, server, broker, role, ea_token,
                lot_multiplier, fixed_lot, max_lot, copy_sl, copy_tp, reverse)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["user_id"], data["name"], data["login"], data["server"],
                data.get("broker"), data["role"], ea_token,
                data.get("lot_multiplier", 1.0), data.get("fixed_lot"),
                data.get("max_lot"), data.get("copy_sl", 1),
                data.get("copy_tp", 1), data.get("reverse", 0)
            ))
            return cur.lastrowid

    def get_user_accounts(self, user_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_account(self, account_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            return dict(row) if row else None

    def get_account_by_ea_token(self, ea_token: str) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE ea_token=?", (ea_token,)).fetchone()
            return dict(row) if row else None

    def update_account(self, account_id: int, data: Dict):
        fields = ", ".join(f"{k}=?" for k in data)
        values = list(data.values()) + [account_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE accounts SET {fields} WHERE id=?", values)

    def delete_account(self, account_id: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))

    def get_account_followers(self, master_account_id: int) -> List[Dict]:
        """Get all follower accounts linked to a master via copy groups"""
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT a.* FROM accounts a
                JOIN group_followers gf ON gf.account_id = a.id
                JOIN copy_groups cg ON cg.id = gf.group_id
                WHERE cg.master_account_id = ? AND a.active = 1
            """, (master_account_id,)).fetchall()
            return [dict(r) for r in rows]

    # ── Copy Groups ────────────────────────────────────────────────
    def create_group(self, user_id: int, name: str, master_account_id: int) -> int:
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO copy_groups (user_id, name, master_account_id) VALUES (?,?,?)",
                (user_id, name, master_account_id)
            )
            return cur.lastrowid

    def get_user_groups(self, user_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT * FROM copy_groups WHERE user_id=?", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def add_follower_to_group(self, group_id: int, account_id: int):
        with self.get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO group_followers VALUES (?,?)", (group_id, account_id))

    def remove_follower_from_group(self, group_id: int, account_id: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM group_followers WHERE group_id=? AND account_id=?", (group_id, account_id))

    # ── Trades ─────────────────────────────────────────────────────
    def log_trade(self, data: Dict) -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO trades (user_id, master_account_id, follower_account_id,
                master_ticket, follower_ticket, symbol, action, lots, open_price,
                sl, tp, status, opened_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["user_id"], data["master_account_id"], data.get("follower_account_id"),
                data.get("master_ticket"), data.get("follower_ticket"),
                data["symbol"], data["action"], data["lots"],
                data.get("open_price"), data.get("sl"), data.get("tp"),
                data.get("status", "copied"), data.get("opened_at", datetime.utcnow().isoformat())
            ))
            return cur.lastrowid

    def get_user_trades(self, user_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Open Positions ─────────────────────────────────────────────
    def upsert_position(self, master_account_id: int, pos: Dict):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT INTO open_positions (master_account_id, ticket, symbol, action, lots,
                open_price, sl, tp, profit, opened_at, last_update)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(master_account_id, ticket) DO UPDATE SET
                    profit=excluded.profit, sl=excluded.sl, tp=excluded.tp,
                    last_update=excluded.last_update
            """, (
                master_account_id, pos["ticket"], pos["symbol"], pos["action"],
                pos["lots"], pos.get("open_price"), pos.get("sl"), pos.get("tp"),
                pos.get("profit"), pos.get("opened_at"), datetime.utcnow().isoformat()
            ))

    def remove_position(self, master_account_id: int, ticket: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM open_positions WHERE master_account_id=? AND ticket=?",
                         (master_account_id, ticket))

    def get_open_positions(self, master_account_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM open_positions WHERE master_account_id=?", (master_account_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Stats ──────────────────────────────────────────────────────
    def get_user_stats(self, user_id: int) -> Dict:
        with self.get_conn() as conn:
            today = date.today().isoformat()
            trades_today = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id=? AND created_at LIKE ?",
                (user_id, f"{today}%")
            ).fetchone()[0]
            total_trades = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            accounts = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            return {"trades_today": trades_today, "total_trades": total_trades, "accounts": accounts}

    def get_all_users(self) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT id,email,full_name,plan,created_at,active FROM users").fetchall()
            return [dict(r) for r in rows]

    def get_symbol_mappings(self, user_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("SELECT * FROM symbol_mappings WHERE user_id=?", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def add_symbol_mapping(self, data: Dict) -> int:
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO symbol_mappings (user_id, master_symbol, follower_symbol, account_id) VALUES (?,?,?,?)",
                (data["user_id"], data["master_symbol"], data["follower_symbol"], data["account_id"])
            )
            return cur.lastrowid

    def delete_symbol_mapping(self, mapping_id: int, user_id: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM symbol_mappings WHERE id=? AND user_id=?", (mapping_id, user_id))
