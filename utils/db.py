import sqlite3
import json
import threading
from typing import Any, Optional

# Simple thread-safe key/value JSON store using SQLite.
# File created lazily on first access.

_DB_PATH = "data.sqlite3"
_LOCK = threading.Lock()

def _conn():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(path: Optional[str] = None):
    global _DB_PATH
    if path:
        _DB_PATH = path
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS json_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

def kv_set(key: str, obj: Any) -> None:
    init_db()
    txt = json.dumps(obj, ensure_ascii=False)
    with _LOCK:
        conn = _conn()
        try:
            conn.execute("REPLACE INTO json_store (key, value) VALUES (?, ?)", (key, txt))
            conn.commit()
        finally:
            conn.close()

def kv_get(key: str, default: Any = None) -> Any:
    init_db()
    with _LOCK:
        conn = _conn()
        try:
            cur = conn.execute("SELECT value FROM json_store WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return default
            try:
                return json.loads(row[0])
            except Exception:
                return default
        finally:
            conn.close()

def kv_delete(key: str) -> None:
    init_db()
    with _LOCK:
        conn = _conn()
        try:
            conn.execute("DELETE FROM json_store WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()
