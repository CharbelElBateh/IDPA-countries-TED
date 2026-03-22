"""Chat persistence — save/load/list/delete conversations as JSON files."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from agent.config import CHATS_DIR


def _ensure_dir():
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def generate_id() -> str:
    return uuid.uuid4().hex[:12]


def generate_title(first_message: str) -> str:
    """Auto-generate chat title from first user message."""
    text = first_message.strip().replace("\n", " ")
    if len(text) > 50:
        text = text[:47] + "..."
    return text or "New Chat"


def save_chat(chat_id: str, title: str, model: str, messages: list[dict]) -> Path:
    """Save or update a chat."""
    _ensure_dir()
    path = CHATS_DIR / f"{chat_id}.json"

    now = datetime.now().isoformat()
    data = {
        "id": chat_id,
        "title": title,
        "model": model,
        "updated_at": now,
        "messages": messages,
    }

    # Preserve created_at if updating
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            data["created_at"] = existing.get("created_at", now)
        except (json.JSONDecodeError, KeyError):
            data["created_at"] = now
    else:
        data["created_at"] = now

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_chat(chat_id: str) -> dict | None:
    """Load a chat by ID. Returns None if not found."""
    path = CHATS_DIR / f"{chat_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_chats() -> list[dict]:
    """List all chats (id, title, model, created_at, updated_at). Most recent first."""
    _ensure_dir()
    chats = []
    for path in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            chats.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    chats.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return chats


def delete_chat(chat_id: str) -> bool:
    """Delete a chat. Returns True if deleted."""
    path = CHATS_DIR / f"{chat_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
