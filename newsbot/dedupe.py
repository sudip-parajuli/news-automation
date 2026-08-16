import hashlib
import json
import os

from . import config


def _normalize(item):
    key = (item.get("link") or item.get("title") or "").strip().lower()
    key = key.split("?")[0].rstrip("/")
    return key


def item_hash(item):
    return hashlib.sha256(_normalize(item).encode("utf-8")).hexdigest()


def load_history():
    if not os.path.exists(config.HISTORY_FILE):
        return {"posted": []}
    try:
        with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"posted": []}


def save_history(history):
    os.makedirs(os.path.dirname(config.HISTORY_FILE), exist_ok=True)
    posted = history.get("posted", [])
    if len(posted) > config.MAX_HISTORY_ENTRIES:
        posted = posted[-config.MAX_HISTORY_ENTRIES:]
    history["posted"] = posted
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def already_posted(item, history):
    seen = {p["hash"] for p in history.get("posted", [])}
    return item_hash(item) in seen
