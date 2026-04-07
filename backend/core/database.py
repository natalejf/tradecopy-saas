"""
Multi-tenant Database — PostgreSQL + SQLite fallback
Si DATABASE_URL empieza con postgresql:// usa PostgreSQL, sino SQLite
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict
import secrets

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tradecopy.db")

# Detectar si es PostgreSQL o SQLite
IS_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")


def get_conn():
    if IS_POSTGRES:
        import psycopg2
        import psycopg2.extras
        url = DATABASE_URL
        # Railway a veces da "postgres://" en lugar de "postgresql://"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        db_path = DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def row_to_dict(row, cursor=None):
    """Convierte row a dict para PostgreSQL y SQLite"""
    if row is None:
        return None
    if IS_POSTGRES:
        if cursor:
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))
        return dict(row)
    else:
        return dict(row)


def rows_to_dicts(rows, cursor=None):
    if IS_POSTGRES and cursor:
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, r)) for r in rows]
    return [dict(r) for r in rows]


def PH():
    """Placeholder — %s para PostgreSQL, ? para SQLite"""
    return "%s" if IS_POSTGRES else "?"


class Database:
    def get_conn(self):
        return get_conn()

    def init_db(self):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT,
                        plan TEXT DEFAULT 'free',
                        plan_expires_at TEXT,
                        api_key TEXT UNIQUE,
                        stripe_customer_id TEXT,
                        stripe_subscription_id TEXT,
                        created_at TEXT DEFAULT (to_char(now(),'YYYY-MM-DD HH24:MI:SS')),
                        active INTEGER DEFAULT 1
                    );
                    CREATE TABLE IF NOT EXISTS accounts (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        login BIGINT NOT NULL,
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
                        created_at TEXT DEFAULT (to_char(now(),'YYYY-MM-DD HH24:MI:SS'))
                    );
                    CREATE TABLE IF NOT EXISTS copy_groups (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        master_account_id INTEGER NOT NULL,
                        active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT (to_char(now(),'YYYY-MM-DD HH24:MI:SS'))
                    );
                    CREATE TABLE IF NOT EXISTS group_followers (
                        group_id INTEGER NOT NULL,
                        account_id INTEGER NOT NULL,
                        PRIMARY KEY (group_id, account_id)
                    );
                    CREATE TABLE IF NOT EXISTS trades (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        master_account_id INTEGER NOT NULL,
                        follower_account_id INTEGER,
                        master_ticket BIGINT,
                        follower_ticket BIGINT,
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
                        created_at TEXT DEFAULT (to_char(now(),'YYYY-MM-DD HH24:MI:SS'))
                    );
                    CREATE TABLE IF NOT EXISTS symbol_mappings (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        master_symbol TEXT NOT NULL,
                        follower_symbol TEXT NOT NULL,
                        account_id INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS open_positions (
                        id SERIAL PRIMARY KEY,
                        master_account_id INTEGER NOT NULL,
                        ticket BIGINT NOT NULL,
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
            else:
                cur.executescript("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT,
                        plan TEXT DEFAULT 'free',
                        plan_expires_at TEXT,
                        api_key TEXT UNIQUE,
                        stripe_customer_id TEXT,
                        stripe_subscription_id TEXT,
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
                        created_at TEXT DEFAULT (datetime('now'))
                    );
                    CREATE TABLE IF NOT EXISTS copy_groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        master_account_id INTEGER NOT NULL,
                        active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT (datetime('now'))
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
            conn.commit()
            logger.info(f"Database initialized ({'PostgreSQL' if IS_POSTGRES else 'SQLite'})")

    # ── Users ──────────────────────────────────────────────────────
    def create_user(self, email: str, password_hash: str, full_name: str = None) -> int:
        api_key = "tc_" + secrets.token_hex(24)
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute(
                    f"INSERT INTO users (email, password_hash, full_name, api_key) VALUES ({ph},{ph},{ph},{ph}) RETURNING id",
                    (email, password_hash, full_name, api_key)
                )
                uid = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO users (email, password_hash, full_name, api_key) VALUES ({ph},{ph},{ph},{ph})",
                    (email, password_hash, full_name, api_key)
                )
                uid = cur.lastrowid
            conn.commit()
            return uid

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE email={ph}", (email,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE id={ph}", (user_id,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE api_key={ph}", (api_key,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def get_user_by_stripe_customer(self, customer_id: str) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE stripe_customer_id={ph}", (customer_id,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def update_user_plan(self, user_id: int, plan: str, expires_at: str):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET plan={ph}, plan_expires_at={ph} WHERE id={ph}",
                        (plan, expires_at, user_id))
            conn.commit()

    def update_stripe_customer(self, user_id: int, customer_id: str):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET stripe_customer_id={ph} WHERE id={ph}",
                        (customer_id, user_id))
            conn.commit()

    def update_stripe_subscription(self, user_id: int, subscription_id: str):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE users SET stripe_subscription_id={ph} WHERE id={ph}",
                        (subscription_id, user_id))
            conn.commit()

    def get_all_users(self) -> List[Dict]:
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id,email,full_name,plan,created_at,active FROM users")
            return rows_to_dicts(cur.fetchall(), cur)

    # ── Accounts ───────────────────────────────────────────────────
    def add_account(self, data: Dict) -> int:
        ea_token = data.get("ea_token") or "ea_" + secrets.token_hex(20)
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            sql = f"""INSERT INTO accounts (user_id, name, login, server, broker, role,
                      ea_token, lot_multiplier, fixed_lot, max_lot, copy_sl, copy_tp, reverse)
                      VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})"""
            vals = (data["user_id"], data["name"], data["login"], data["server"],
                    data.get("broker"), data["role"], ea_token,
                    data.get("lot_multiplier", 1.0), data.get("fixed_lot"),
                    data.get("max_lot"), data.get("copy_sl", 1),
                    data.get("copy_tp", 1), data.get("reverse", 0))
            if IS_POSTGRES:
                cur.execute(sql + " RETURNING id", vals)
                aid = cur.fetchone()[0]
            else:
                cur.execute(sql, vals)
                aid = cur.lastrowid
            conn.commit()
            return aid

    def get_user_accounts(self, user_id: int) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM accounts WHERE user_id={ph}", (user_id,))
            return rows_to_dicts(cur.fetchall(), cur)

    def get_account(self, account_id: int) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM accounts WHERE id={ph}", (account_id,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def get_account_by_ea_token(self, ea_token: str) -> Optional[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM accounts WHERE ea_token={ph}", (ea_token,))
            row = cur.fetchone()
            return row_to_dict(row, cur) if row else None

    def update_account(self, account_id: int, data: Dict):
        ph = PH()
        fields = ", ".join(f"{k}={ph}" for k in data)
        values = list(data.values()) + [account_id]
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE accounts SET {fields} WHERE id={ph}", values)
            conn.commit()

    def delete_account(self, account_id: int):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM accounts WHERE id={ph}", (account_id,))
            conn.commit()

    def get_account_followers(self, master_account_id: int) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT a.* FROM accounts a
                JOIN group_followers gf ON gf.account_id = a.id
                JOIN copy_groups cg ON cg.id = gf.group_id
                WHERE cg.master_account_id = {ph} AND a.active = 1
            """, (master_account_id,))
            return rows_to_dicts(cur.fetchall(), cur)

    # ── Copy Groups ────────────────────────────────────────────────
    def create_group(self, user_id: int, name: str, master_account_id: int) -> int:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            sql = f"INSERT INTO copy_groups (user_id, name, master_account_id) VALUES ({ph},{ph},{ph})"
            if IS_POSTGRES:
                cur.execute(sql + " RETURNING id", (user_id, name, master_account_id))
                gid = cur.fetchone()[0]
            else:
                cur.execute(sql, (user_id, name, master_account_id))
                gid = cur.lastrowid
            conn.commit()
            return gid

    def get_user_groups(self, user_id: int) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM copy_groups WHERE user_id={ph}", (user_id,))
            return rows_to_dicts(cur.fetchall(), cur)

    def add_follower_to_group(self, group_id: int, account_id: int):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute(
                    f"INSERT INTO group_followers VALUES ({ph},{ph}) ON CONFLICT DO NOTHING",
                    (group_id, account_id)
                )
            else:
                cur.execute(
                    "INSERT OR IGNORE INTO group_followers VALUES (?,?)",
                    (group_id, account_id)
                )
            conn.commit()

    def remove_follower_from_group(self, group_id: int, account_id: int):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM group_followers WHERE group_id={ph} AND account_id={ph}",
                (group_id, account_id)
            )
            conn.commit()

    # ── Trades ─────────────────────────────────────────────────────
    def log_trade(self, data: Dict) -> int:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            sql = f"""INSERT INTO trades (user_id, master_account_id, follower_account_id,
                      master_ticket, follower_ticket, symbol, action, lots, open_price,
                      sl, tp, status, opened_at)
                      VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})"""
            vals = (data["user_id"], data["master_account_id"], data.get("follower_account_id"),
                    data.get("master_ticket"), data.get("follower_ticket"),
                    data["symbol"], data["action"], data["lots"],
                    data.get("open_price"), data.get("sl"), data.get("tp"),
                    data.get("status", "copied"),
                    data.get("opened_at", datetime.utcnow().isoformat()))
            if IS_POSTGRES:
                cur.execute(sql + " RETURNING id", vals)
                tid = cur.fetchone()[0]
            else:
                cur.execute(sql, vals)
                tid = cur.lastrowid
            conn.commit()
            return tid

    def get_user_trades(self, user_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM trades WHERE user_id={ph} ORDER BY created_at DESC LIMIT {ph} OFFSET {ph}",
                (user_id, limit, offset)
            )
            return rows_to_dicts(cur.fetchall(), cur)

    # ── Open Positions ─────────────────────────────────────────────
    def upsert_position(self, master_account_id: int, pos: Dict):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute(f"""
                    INSERT INTO open_positions
                    (master_account_id, ticket, symbol, action, lots, open_price, sl, tp, profit, opened_at, last_update)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    ON CONFLICT (master_account_id, ticket) DO UPDATE SET
                        profit=EXCLUDED.profit, sl=EXCLUDED.sl, tp=EXCLUDED.tp,
                        last_update=EXCLUDED.last_update
                """, (master_account_id, pos["ticket"], pos["symbol"], pos["action"],
                      pos["lots"], pos.get("open_price"), pos.get("sl"), pos.get("tp"),
                      pos.get("profit"), pos.get("opened_at"), datetime.utcnow().isoformat()))
            else:
                cur.execute("""
                    INSERT INTO open_positions
                    (master_account_id, ticket, symbol, action, lots, open_price, sl, tp, profit, opened_at, last_update)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(master_account_id, ticket) DO UPDATE SET
                        profit=excluded.profit, sl=excluded.sl, tp=excluded.tp,
                        last_update=excluded.last_update
                """, (master_account_id, pos["ticket"], pos["symbol"], pos["action"],
                      pos["lots"], pos.get("open_price"), pos.get("sl"), pos.get("tp"),
                      pos.get("profit"), pos.get("opened_at"), datetime.utcnow().isoformat()))
            conn.commit()

    def remove_position(self, master_account_id: int, ticket: int):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM open_positions WHERE master_account_id={ph} AND ticket={ph}",
                (master_account_id, ticket)
            )
            conn.commit()

    def get_open_positions(self, master_account_id: int) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM open_positions WHERE master_account_id={ph}",
                (master_account_id,)
            )
            return rows_to_dicts(cur.fetchall(), cur)

    # ── Stats ──────────────────────────────────────────────────────
    def get_user_stats(self, user_id: int) -> Dict:
        ph = PH()
        today = date.today().isoformat()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM trades WHERE user_id={ph} AND created_at LIKE {ph}",
                (user_id, f"{today}%")
            )
            trades_today = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM trades WHERE user_id={ph}", (user_id,))
            total_trades = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM accounts WHERE user_id={ph}", (user_id,))
            accounts = cur.fetchone()[0]
            return {"trades_today": trades_today, "total_trades": total_trades, "accounts": accounts}

    # ── Symbol Mappings ────────────────────────────────────────────
    def get_symbol_mappings(self, user_id: int) -> List[Dict]:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM symbol_mappings WHERE user_id={ph}", (user_id,))
            return rows_to_dicts(cur.fetchall(), cur)

    def add_symbol_mapping(self, data: Dict) -> int:
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            sql = f"INSERT INTO symbol_mappings (user_id, master_symbol, follower_symbol, account_id) VALUES ({ph},{ph},{ph},{ph})"
            if IS_POSTGRES:
                cur.execute(sql + " RETURNING id",
                            (data["user_id"], data["master_symbol"], data["follower_symbol"], data["account_id"]))
                mid = cur.fetchone()[0]
            else:
                cur.execute(sql, (data["user_id"], data["master_symbol"], data["follower_symbol"], data["account_id"]))
                mid = cur.lastrowid
            conn.commit()
            return mid

    def delete_symbol_mapping(self, mapping_id: int, user_id: int):
        ph = PH()
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM symbol_mappings WHERE id={ph} AND user_id={ph}",
                        (mapping_id, user_id))
            conn.commit()