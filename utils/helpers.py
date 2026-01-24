import json
import os
import tempfile
from typing import Any

def safe_load_json(path: str, default: Any = None) -> Any:
	if not os.path.exists(path):
		return default
	try:
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return default

def safe_write_json(path: str, data: Any) -> None:
	dirpath = os.path.dirname(path) or "."
	os.makedirs(dirpath, exist_ok=True)
	fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=".tmp_", suffix=".json")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
			json.dump(data, tmpf, indent=4, ensure_ascii=False)
			tmpf.flush()
			os.fsync(tmpf.fileno())
		os.replace(tmp_path, path)
	finally:
		if os.path.exists(tmp_path):
			try:
				os.remove(tmp_path)
			except:
				pass

def ensure_json_file(path: str, default: Any = None) -> None:
	if not os.path.exists(path):
		safe_write_json(path, default or {})

def strip_emojis(text: str) -> str:
	"""Remove emoji and pictograph characters from text."""
	if not text:
		return text
	try:
		import re
		emoji_pattern = re.compile(
			"["
			"\U0001F300-\U0001F5FF"
			"\U0001F600-\U0001F64F"
			"\U0001F680-\U0001F6FF"
			"\U0001F700-\U0001F77F"
			"\U0001F780-\U0001F7FF"
			"\U0001F800-\U0001F8FF"
			"\U0001F900-\U0001F9FF"
			"\U0001FA00-\U0001FA6F"
			"\U0001FA70-\U0001FAFF"
			"\u2600-\u26FF"
			"\u2700-\u27BF"
			"]+",
			flags=re.UNICODE,
		)
		return emoji_pattern.sub(r"", text).strip()
	except Exception:
		return text

_recent_msgs = set()

def is_recent_message(msg_id: int) -> bool:
	return msg_id in _recent_msgs

def mark_recent_message(msg_id: int, ttl: int = 5):
	"""Mark a message id as recently replied-to for `ttl` seconds."""
	import asyncio
	if msg_id in _recent_msgs:
		return
	_recent_msgs.add(msg_id)

	async def _clear():
		await asyncio.sleep(ttl)
		try:
			_recent_msgs.discard(msg_id)
		except:
			pass

	try:
		loop = asyncio.get_running_loop()
		loop.create_task(_clear())
	except RuntimeError:
		pass
