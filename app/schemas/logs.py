from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class EventBatchRequest(BaseModel):
    # 单条事件在路由内分别校验，避免一条错误导致整个批次返回 422。
    events: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=50,
    )


class InteractionEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    suggestion_id: str | None = Field(default=None, max_length=128)
    pair_id: str | None = Field(default=None, max_length=128)
    participant_id: str | int
    condition: str | None = Field(default=None, max_length=64)
    story_id: int | None = Field(default=None, ge=1)
    page_id: int | None = Field(default=None, ge=1)
    timestamp: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=100)
    target_id: str | None = Field(default=None, max_length=256)
    target_type: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=100)
    action_origin: str | None = Field(default=None, max_length=100)
    event_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("timestamp must be an ISO 8601 datetime") from error
        return value


class CanvasSnapshotData(BaseModel):
    snapshot_type: Literal[
        "page_start",
        "ai_result_applied",
        "page_submit",
    ]
    snapshot_timestamp: str = Field(min_length=1, max_length=64)
    icons: list[dict[str, Any]] = Field(default_factory=list)
    audio_clips: list[dict[str, Any]] = Field(default_factory=list)
    canvas: dict[str, Any] = Field(default_factory=dict)
    audio: dict[str, Any] = Field(default_factory=dict)

    @field_validator("snapshot_timestamp")
    @classmethod
    def validate_snapshot_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(
                "snapshot_timestamp must be an ISO 8601 datetime"
            ) from error
        return value


class RejectedEvent(BaseModel):
    event_id: str | None
    reason: str


class EventBatchResponse(BaseModel):
    accepted_event_ids: list[str] = Field(default_factory=list)
    rejected_events: list[RejectedEvent] = Field(default_factory=list)
