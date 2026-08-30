import json
import hashlib
import logging
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from app.core.config import BASE_DIR


logger = logging.getLogger(__name__)

USER_EVENT_LOG_DIR = BASE_DIR / "user_event_logs"
_file_lock = threading.Lock()


def _safe_log_filename(username: str) -> str:
    """Keep ordinary usernames readable while preventing unsafe paths."""
    normalized = unicodedata.normalize("NFKC", username).strip()
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", normalized)
    safe_name = safe_name.strip(". ")
    if not safe_name:
        safe_name = "user"
    if safe_name != normalized:
        digest = hashlib.sha256(username.encode("utf-8")).hexdigest()[:8]
        safe_name = f"{safe_name}_{digest}"
    return safe_name


def get_user_event_log_path(username: str) -> Path:
    return USER_EVENT_LOG_DIR / f"{_safe_log_filename(username)}.jsonl"


def ensure_user_event_log(username: str) -> Path:
    path = get_user_event_log_path(username)
    with _file_lock:
        USER_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
    return path


def append_user_event_records(
    username: str,
    records: Iterable[dict[str, Any]],
) -> None:
    """Append newline-delimited JSON records to one user's experiment file."""
    serialized = [
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    ]
    if not serialized:
        return

    path = get_user_event_log_path(username)
    with _file_lock:
        USER_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(serialized))
            log_file.write("\n")


def safely_append_user_event_records(
    username: str,
    records: Iterable[dict[str, Any]],
) -> None:
    """File mirroring must never break authentication or creative work."""
    try:
        append_user_event_records(username, records)
    except (OSError, TypeError, ValueError):
        logger.exception(
            "Failed to append per-user event file | username=%s",
            username,
        )
