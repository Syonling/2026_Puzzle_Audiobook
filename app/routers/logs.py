import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.core.security import get_current_user
from app.db.database import get_db
from app.schemas.logs import (
    CanvasSnapshotData,
    EventBatchRequest,
    EventBatchResponse,
    InteractionEvent,
)
from app.services.user_event_files import safely_append_user_event_records


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])

MAX_EVENT_DATA_BYTES = 1_000_000


def _identity_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _event_suggestion_id(event: InteractionEvent) -> str | None:
    suggestion_id = event.suggestion_id
    if suggestion_id is None:
        suggestion_id = event.event_data.get("suggestion_id")
    if suggestion_id is None:
        suggestion_id = event.event_data.get("suggestionId")
    if (
        suggestion_id is None
        and event.target_type == "ai_suggestion"
    ):
        suggestion_id = event.target_id
    if suggestion_id is None:
        return None
    if not isinstance(suggestion_id, str) or not suggestion_id:
        raise ValueError("suggestion_id must be a non-empty string")
    if len(suggestion_id) > 128:
        raise ValueError("suggestion_id is too long")
    return suggestion_id


def _validate_event_identity(event: InteractionEvent, current_user) -> None:
    expected_participant_id = (
        current_user["participant_id"]
        if current_user["participant_id"] is not None
        else current_user["id"]
    )
    if _identity_value(event.participant_id) != _identity_value(
        expected_participant_id
    ):
        raise ValueError("participant_id does not match current user")

    if _identity_value(event.pair_id) != _identity_value(
        current_user["pair_id"]
    ):
        raise ValueError("pair_id does not match current user")

    if _identity_value(event.condition) != _identity_value(
        current_user["condition"]
    ):
        raise ValueError("condition does not match current user")


def _insert_snapshot(
    db: sqlite3.Connection,
    event: InteractionEvent,
    user_id: int,
    received_at: str,
) -> None:
    snapshot = CanvasSnapshotData.model_validate(event.event_data)
    db.execute(
        """
        INSERT INTO canvas_snapshots (
            event_id,
            user_id,
            session_id,
            story_id,
            page_id,
            snapshot_type,
            snapshot_timestamp,
            icons_json,
            audio_clips_json,
            canvas_json,
            audio_json,
            received_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            user_id,
            event.session_id,
            event.story_id,
            event.page_id,
            snapshot.snapshot_type,
            snapshot.snapshot_timestamp,
            json.dumps(snapshot.icons, ensure_ascii=False),
            json.dumps(snapshot.audio_clips, ensure_ascii=False),
            json.dumps(snapshot.canvas, ensure_ascii=False),
            json.dumps(snapshot.audio, ensure_ascii=False),
            received_at,
        ),
    )


def _update_ai_display_link(
    db: sqlite3.Connection,
    event: InteractionEvent,
    suggestion_id: str | None,
    user_id: int,
) -> None:
    if suggestion_id is None:
        return

    # The first linked event supplies session_id when the AI request only had
    # X-Suggestion-ID. Only an explicit display event sets display_timestamp.
    db.execute(
        """
        UPDATE ai_suggestions
        SET session_id = COALESCE(session_id, ?)
        WHERE suggestion_id = ?
          AND user_id = ?
        """,
        (event.session_id, suggestion_id, user_id),
    )
    if event.event_type == "ai_result_displayed":
        db.execute(
            """
            UPDATE ai_suggestions
            SET display_timestamp = COALESCE(display_timestamp, ?)
            WHERE suggestion_id = ?
              AND user_id = ?
            """,
            (event.timestamp, suggestion_id, user_id),
        )


@router.post(
    "/events/batch",
    response_model=EventBatchResponse,
)
def create_event_batch(
    request: EventBatchRequest,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    accepted_event_ids: list[str] = []
    rejected_events: list[dict[str, str | None]] = []
    file_records: list[dict[str, Any]] = []
    user_id = current_user["id"]

    for raw_event in request.events:
        raw_event_id = raw_event.get("event_id")
        event_id = (
            raw_event_id
            if isinstance(raw_event_id, str)
            else None
        )
        try:
            event = InteractionEvent.model_validate(raw_event)
            _validate_event_identity(event, current_user)
            suggestion_id = _event_suggestion_id(event)
            event_data_json = json.dumps(
                event.event_data,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(event_data_json.encode("utf-8")) > MAX_EVENT_DATA_BYTES:
                raise ValueError("event_data exceeds 1 MB")

            existing = db.execute(
                """
                SELECT user_id
                FROM interaction_events
                WHERE event_id = ?
                """,
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                if existing["user_id"] != user_id:
                    raise ValueError("event_id belongs to another user")
                accepted_event_ids.append(event.event_id)
                continue

            received_at = datetime.now(timezone.utc).isoformat()
            db.execute("SAVEPOINT interaction_event")
            try:
                db.execute(
                    """
                    INSERT INTO interaction_events (
                        event_id,
                        user_id,
                        session_id,
                        suggestion_id,
                        pair_id,
                        participant_id,
                        condition,
                        story_id,
                        page_id,
                        client_timestamp,
                        received_at,
                        event_type,
                        target_id,
                        target_type,
                        source,
                        action_origin,
                        event_data_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        user_id,
                        event.session_id,
                        suggestion_id,
                        event.pair_id,
                        str(event.participant_id),
                        event.condition,
                        event.story_id,
                        event.page_id,
                        event.timestamp,
                        received_at,
                        event.event_type,
                        event.target_id,
                        event.target_type,
                        event.source,
                        event.action_origin,
                        event_data_json,
                    ),
                )
                if event.event_type == "canvas_snapshot":
                    _insert_snapshot(db, event, user_id, received_at)
                _update_ai_display_link(
                    db,
                    event,
                    suggestion_id,
                    user_id,
                )
                db.execute("RELEASE SAVEPOINT interaction_event")
            except (sqlite3.DatabaseError, ValidationError, ValueError):
                db.execute("ROLLBACK TO SAVEPOINT interaction_event")
                db.execute("RELEASE SAVEPOINT interaction_event")
                raise

            accepted_event_ids.append(event.event_id)
            file_records.append(
                {
                    "record_type": "interaction_event",
                    "user_id": user_id,
                    "received_at": received_at,
                    **event.model_dump(),
                    "participant_id": str(event.participant_id),
                    "suggestion_id": suggestion_id,
                }
            )

        except (ValidationError, ValueError, TypeError) as error:
            rejected_events.append(
                {
                    "event_id": event_id,
                    "reason": str(error),
                }
            )
        except sqlite3.DatabaseError as error:
            db.rollback()
            logger.exception(
                "Failed to store interaction event batch | user_id=%s | "
                "event_id=%s",
                user_id,
                event_id,
            )
            # A database failure is retryable. Returning 500 lets the existing
            # frontend backoff retain and resend the complete idempotent batch.
            raise HTTPException(
                status_code=500,
                detail="Failed to save event batch",
            ) from error

    try:
        db.commit()
    except sqlite3.DatabaseError as error:
        db.rollback()
        logger.exception(
            "Failed to commit interaction event batch | user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save event batch",
        ) from error

    safely_append_user_event_records(current_user["username"], file_records)
    logger.info(
        "Interaction event batch processed | user_id=%s | received=%d | "
        "accepted=%d | rejected=%d | new_records=%d",
        user_id,
        len(request.events),
        len(accepted_event_ids),
        len(rejected_events),
        len(file_records),
    )
    return {
        "accepted_event_ids": accepted_event_ids,
        "rejected_events": rejected_events,
    }
