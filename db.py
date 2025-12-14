import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

from config import DB_PATH, DUP_WINDOW_HOURS

UTC = timezone.utc


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # users
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT NOT NULL,
            opt_in INTEGER NOT NULL DEFAULT 1
        )
        """)

        # admins (dynamic)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT NOT NULL
        )
        """)

        # whitelist (bypass rate limit)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT NOT NULL,
            note TEXT
        )
        """)

        # rate window
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit (
            user_id INTEGER PRIMARY KEY,
            window_start TEXT NOT NULL,
            count INTEGER NOT NULL
        )
        """)

        # wizard state
        cur.execute("""
        CREATE TABLE IF NOT EXISTS wizard (
            user_id INTEGER PRIMARY KEY,
            step TEXT NOT NULL,
            category TEXT,
            description TEXT,
            attachment_type TEXT,
            attachment_file_id TEXT,
            attachment_unique_id TEXT,
            updated_at TEXT NOT NULL
        )
        """)

        # feedback submissions (no ticketing, just id)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            attachment_type TEXT,
            attachment_file_id TEXT,
            attachment_unique_id TEXT,
            created_at TEXT NOT NULL,
            dedup_of INTEGER,
            dup_count INTEGER NOT NULL DEFAULT 0
        )
        """)

        # relay mapping admin message -> user
        cur.execute("""
        CREATE TABLE IF NOT EXISTS relay_map (
            admin_chat_id INTEGER NOT NULL,
            admin_message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            feedback_id INTEGER,
            created_at TEXT NOT NULL,
            PRIMARY KEY (admin_chat_id, admin_message_id)
        )
        """)

        # internal notes
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # counters
        cur.execute("""
        CREATE TABLE IF NOT EXISTS counters (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
        """)


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# ===== Users / Opt-in =====
def ensure_user(user_id: int, opt_in_default: bool):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO users(user_id, first_seen, opt_in) VALUES(?,?,?)",
                (user_id, now_iso(), 1 if opt_in_default else 0)
            )


def set_opt_in(user_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET opt_in=? WHERE user_id=?", (1 if enabled else 0, user_id))


def get_opt_in(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT opt_in FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row["opt_in"]) if row else False


# ===== Counters =====
def inc_counter(key: str, delta: int = 1):
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM counters WHERE key=?", (key,)).fetchone()
        if row is None:
            cur.execute("INSERT INTO counters(key, value) VALUES(?,?)", (key, delta))
        else:
            cur.execute("UPDATE counters SET value=? WHERE key=?", (int(row["value"]) + delta, key))


def get_counter(key: str) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM counters WHERE key=?", (key,)).fetchone()
        return int(row["value"]) if row else 0


# ===== Admins =====
def is_admin(user_id: int, owner_id: int) -> bool:
    if user_id == owner_id:
        return True
    with get_conn() as conn:
        row = conn.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return row is not None


def add_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO admins(user_id, added_at) VALUES(?,?)", (user_id, now_iso()))


def del_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))


def list_admins() -> List[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()
        return [int(r["user_id"]) for r in rows]


# ===== Whitelist =====
def is_whitelisted(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM whitelist WHERE user_id=?", (user_id,)).fetchone() is not None


def whitelist_add(user_id: int, note: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO whitelist(user_id, added_at, note) VALUES(?,?,?)",
            (user_id, now_iso(), note)
        )


def whitelist_del(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))


# ===== Rate limit =====
def rate_check_and_inc(user_id: int, window_sec: int, max_msg: int) -> bool:
    """
    return True if allowed, False if exceeded
    """
    now = datetime.now(tz=UTC)
    with get_conn() as conn:
        row = conn.execute("SELECT window_start, count FROM rate_limit WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO rate_limit(user_id, window_start, count) VALUES(?,?,?)",
                         (user_id, now.isoformat(), 1))
            return True

        start = datetime.fromisoformat(row["window_start"])
        count = int(row["count"])

        if (now - start).total_seconds() > window_sec:
            conn.execute("UPDATE rate_limit SET window_start=?, count=? WHERE user_id=?",
                         (now.isoformat(), 1, user_id))
            return True

        if count + 1 > max_msg:
            return False

        conn.execute("UPDATE rate_limit SET count=? WHERE user_id=?", (count + 1, user_id))
        return True


# ===== Wizard =====
def wizard_set(user_id: int, step: str, **fields):
    with get_conn() as conn:
        existing = conn.execute("SELECT user_id FROM wizard WHERE user_id=?", (user_id,)).fetchone()
        cols = {
            "step": step,
            "updated_at": now_iso(),
            **fields
        }
        if existing is None:
            conn.execute("""
                INSERT INTO wizard(user_id, step, category, description, attachment_type, attachment_file_id, attachment_unique_id, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (
                user_id,
                cols.get("step"),
                cols.get("category"),
                cols.get("description"),
                cols.get("attachment_type"),
                cols.get("attachment_file_id"),
                cols.get("attachment_unique_id"),
                cols.get("updated_at")
            ))
        else:
            sets = ", ".join([f"{k}=?" for k in cols.keys()])
            conn.execute(f"UPDATE wizard SET {sets} WHERE user_id=?", (*cols.values(), user_id))


def wizard_get(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM wizard WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def wizard_clear(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM wizard WHERE user_id=?", (user_id,))


# ===== Feedback + Dedup =====
def find_duplicate(category: str, description: str, attachment_unique_id: Optional[str]) -> Optional[int]:
    since = datetime.now(tz=UTC) - timedelta(hours=DUP_WINDOW_HOURS)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, category, description, attachment_unique_id, created_at
            FROM feedback
            WHERE created_at >= ?
            ORDER BY id DESC
            LIMIT 300
        """, (since.isoformat(),)).fetchall()

        d = description.strip()
        for r in rows:
            if r["category"] != category:
                continue
            if (r["description"] or "").strip() != d:
                continue
            if attachment_unique_id and r["attachment_unique_id"]:
                if attachment_unique_id == r["attachment_unique_id"]:
                    return int(r["id"])
            else:
                return int(r["id"])
    return None


def create_feedback(user_id: int, category: str, description: str,
                    attachment_type: Optional[str],
                    attachment_file_id: Optional[str],
                    attachment_unique_id: Optional[str]) -> Tuple[int, Optional[int]]:
    dedup_of = find_duplicate(category, description, attachment_unique_id)
    created_at = now_iso()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO feedback(user_id, category, description, attachment_type, attachment_file_id, attachment_unique_id, created_at, dedup_of, dup_count)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (user_id, category, description, attachment_type, attachment_file_id, attachment_unique_id, created_at, dedup_of, 0))
        fid = int(cur.lastrowid)

        if dedup_of:
            conn.execute("UPDATE feedback SET dup_count = dup_count + 1 WHERE id=?", (dedup_of,))
        return fid, dedup_of


def feedback_get(fid: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM feedback WHERE id=?", (fid,)).fetchone()
        return dict(row) if row else None


# ===== Relay map =====
def relay_put(admin_chat_id: int, admin_message_id: int, user_id: int, feedback_id: Optional[int]):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO relay_map(admin_chat_id, admin_message_id, user_id, feedback_id, created_at)
            VALUES(?,?,?,?,?)
        """, (admin_chat_id, admin_message_id, user_id, feedback_id, now_iso()))


def relay_get(admin_chat_id: int, admin_message_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM relay_map WHERE admin_chat_id=? AND admin_message_id=?
        """, (admin_chat_id, admin_message_id)).fetchone()
        return dict(row) if row else None


# ===== Notes =====
def add_note(feedback_id: int, admin_id: int, note: str) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notes(feedback_id, admin_id, note, created_at)
            VALUES(?,?,?,?)
        """, (feedback_id, admin_id, note, now_iso()))
        return int(cur.lastrowid)


def list_notes(feedback_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM notes WHERE feedback_id=?
            ORDER BY id DESC LIMIT ?
        """, (feedback_id, limit)).fetchall()
        return [dict(r) for r in rows]


# ===== Exports / Stats =====
def export_feedback_rows(limit: int = 5000) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, user_id, category, description, attachment_type, created_at, dedup_of, dup_count
            FROM feedback
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def export_users_optin() -> List[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users WHERE opt_in=1").fetchall()
        return [int(r["user_id"]) for r in rows]


def stats_snapshot() -> Dict[str, int]:
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_feedback = conn.execute("SELECT COUNT(*) AS c FROM feedback").fetchone()["c"]
        total_whitelist = conn.execute("SELECT COUNT(*) AS c FROM whitelist").fetchone()["c"]
    return {
        "users": int(total_users),
        "feedback": int(total_feedback),
        "whitelist": int(total_whitelist),
    }
