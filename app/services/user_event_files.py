import json
import logging
import threading
from pathlib import Path
from typing import Any, Iterable

from app.core.config import BASE_DIR


logger = logging.getLogger(__name__)

USER_EVENT_LOG_DIR = BASE_DIR / "user_event_logs"
_file_lock = threading.Lock()


def get_user_event_log_path(user_id: int) -> Path:
    """Use the internal numeric ID so usernames never become file paths."""
    return USER_EVENT_LOG_DIR / f"user_{int(user_id)}.jsonl"


def ensure_user_event_log(user_id: int) -> Path:
    path = get_user_event_log_path(user_id)
    with _file_lock:
        USER_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
    return path


def append_user_event_records(
    user_id: int,
    records: Iterable[dict[str, Any]],
) -> None:
    """Append newline-delimited JSON records to one user's experiment file."""
    serialized = [
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    ]
    if not serialized:
        return

    path = get_user_event_log_path(user_id)
    with _file_lock:
        USER_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(serialized))
            log_file.write("\n")


def safely_append_user_event_records(
    user_id: int,
    records: Iterable[dict[str, Any]],
) -> None:
    """File mirroring must never break authentication or creative work."""
    try:
        append_user_event_records(user_id, records)
    except (OSError, TypeError, ValueError):
        logger.exception(
            "Failed to append per-user event file | user_id=%s",
            user_id,
        )
