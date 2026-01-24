import os
import asyncio
import tempfile
import json

import pytest

from utils import helpers


def test_safe_write_and_load_json(tmp_path):
    p = tmp_path / "data.json"
    data = {"a": 1, "b": "çalışıyor"}
    helpers.safe_write_json(str(p), data)

    loaded = helpers.safe_load_json(str(p), {})
    assert loaded == data


def test_strip_emojis():
    s = "Merhaba 😊! Bugün hava ☀️ çok güzel."
    out = helpers.strip_emojis(s)
    assert "😊" not in out
    assert "☀️" not in out
    assert "Merhaba" in out


@pytest.mark.asyncio
async def test_mark_and_clear_recent_message():
    # Use a small ttl so test completes quickly
    msg_id = 123456789
    assert not helpers.is_recent_message(msg_id)
    helpers.mark_recent_message(msg_id, ttl=0)
    # after scheduling, allow the event loop to run scheduled tasks
    await asyncio.sleep(0.01)
    # mark_recent_message with ttl=0 should remove immediately
    assert not helpers.is_recent_message(msg_id)
