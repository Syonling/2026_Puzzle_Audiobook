"""Read optional, precomputed story-narration timing data for LangGraph."""

import json
import logging
from pathlib import Path
from typing import Literal, TypedDict


logger = logging.getLogger(__name__)

# Future offline alignment scripts should write files here as:
# app/seed_data/narration_timings/story_{story_id}_{language}.json
NARRATION_TIMING_DIR = (
    Path(__file__).resolve().parents[2]
    / "seed_data"
    / "narration_timings"
)


class NarrationCue(TypedDict):
    text: str
    start_seconds: float
    end_seconds: float


class NarrationTiming(TypedDict):
    duration_seconds: float
    cues: list[NarrationCue]


def load_narration_timing(
    story_id: int,
    language: Literal["zh", "ja", "en"],
    step_order: int,
) -> NarrationTiming | None:
    """Return one step's validated timing data, or None when unavailable."""
    path = NARRATION_TIMING_DIR / f"story_{story_id}_{language}.json"
    if not path.is_file():
        logger.info(
            "Narration timing skipped: file not found | story_id=%s | "
            "language=%s | path=%s",
            story_id,
            language,
            path,
        )
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        steps = payload.get("steps", [])
        step = next(
            (
                item
                for item in steps
                if item.get("step_order") == step_order
            ),
            None,
        )
        if step is None:
            return None

        duration = float(step["duration_seconds"])
        if duration <= 0:
            raise ValueError("duration_seconds must be positive")

        cues: list[NarrationCue] = []
        for item in step.get("cues", []):
            text = str(item["text"]).strip()
            start = float(item["start_seconds"])
            end = float(item["end_seconds"])
            if not text or start < 0 or end < start or end > duration:
                raise ValueError("invalid narration cue")
            cues.append({
                "text": text,
                "start_seconds": start,
                "end_seconds": end,
            })

        if not cues:
            return None
        return {
            "duration_seconds": duration,
            "cues": cues,
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.exception(
            "Invalid narration timing file; keeping original AI timing | "
            "story_id=%s | language=%s | step_order=%s | path=%s",
            story_id,
            language,
            step_order,
            path,
        )
        return None
