import datetime
from typing import List, Optional, Dict, Any
from . import db


KEY_PREFIX = "warnings"


def _key(guild_id: int) -> str:
    return f"{KEY_PREFIX}:{guild_id}"


def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """Add a warning and return its numeric id."""
    data = db.kv_get(_key(guild_id), []) or []
    # compute next id
    next_id = 1
    if data:
        try:
            next_id = max(w.get("id", 0) for w in data) + 1
        except Exception:
            next_id = len(data) + 1

    warn = {
        "id": next_id,
        "user_id": int(user_id),
        "moderator_id": int(moderator_id),
        "reason": reason or "Sebep yok",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    data.append(warn)
    db.kv_set(_key(guild_id), data)
    return next_id


def list_warnings(guild_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    data = db.kv_get(_key(guild_id), []) or []
    if user_id is None:
        return list(data)
    return [w for w in data if int(w.get("user_id")) == int(user_id)]


def remove_warning(guild_id: int, warn_id: int) -> bool:
    data = db.kv_get(_key(guild_id), []) or []
    new = [w for w in data if int(w.get("id")) != int(warn_id)]
    if len(new) == len(data):
        return False
    db.kv_set(_key(guild_id), new)
    return True


def clear_warnings(guild_id: int, user_id: Optional[int] = None) -> int:
    data = db.kv_get(_key(guild_id), []) or []
    if user_id is None:
        count = len(data)
        db.kv_set(_key(guild_id), [])
        return count
    new = [w for w in data if int(w.get("user_id")) != int(user_id)]
    removed = len(data) - len(new)
    db.kv_set(_key(guild_id), new)
    return removed
