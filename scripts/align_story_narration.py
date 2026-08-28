"""Generate reusable narration cue JSON from seeded story text and audio.

This is an offline maintenance script. It is never imported by FastAPI and
does not run during application startup.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Literal


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.seed_data.stories import STORIES  # noqa: E402


LANGUAGES = ("zh", "ja", "en")
Language = Literal["zh", "ja", "en"]
OUTPUT_DIR = PROJECT_DIR / "app" / "seed_data" / "narration_timings"
DEFAULT_MAX_CUE_UNITS = {
    "zh": 12,
    "ja": 18,
    "en": 7,
}
CLAUSE_ENDINGS = set("，。！？；：,.!?;:\n")

logger = logging.getLogger("narration_alignment")


def normalize_step(raw_step: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_step, str):
        return {"sentence": raw_step, "audio_url": None}
    return {
        "sentence": str(raw_step.get("sentence", "")).strip(),
        "audio_url": raw_step.get("audio_url"),
    }


def select_story(story_id: int) -> dict[str, Any]:
    if story_id < 1 or story_id > len(STORIES):
        raise ValueError(
            f"story_id must be between 1 and {len(STORIES)}; got {story_id}"
        )
    return STORIES[story_id - 1]


def select_content(
    story: dict[str, Any],
    language: Language,
) -> dict[str, Any]:
    content = next(
        (
            item
            for item in story.get("contents", [])
            if item.get("language") == language
        ),
        None,
    )
    if content is None:
        raise ValueError(
            f"story {story.get('slug')} has no {language!r} content"
        )
    return content


def resolve_audio_path(audio_url: str) -> Path:
    prefix = "/static/"
    if not audio_url.startswith(prefix):
        raise ValueError(
            f"audio_url must start with {prefix!r}; got {audio_url!r}"
        )
    relative_path = Path("static") / audio_url.removeprefix(prefix)
    path = (PROJECT_DIR / relative_path).resolve()
    static_dir = (PROJECT_DIR / "static").resolve()
    if path != static_dir and static_dir not in path.parents:
        raise ValueError(f"audio path escapes static directory: {audio_url}")
    return path


def selected_steps(
    story: dict[str, Any],
    content: dict[str, Any],
    requested_step_order: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    free_creation_orders = set(story.get("free_creation_step_orders", []))
    runnable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for step_order, raw_step in enumerate(content.get("steps", []), start=1):
        if requested_step_order is not None and step_order != requested_step_order:
            continue
        step = normalize_step(raw_step)
        reason = None
        if step_order in free_creation_orders:
            reason = "free_creation"
        elif not step["sentence"]:
            reason = "missing_sentence"
        elif not step["audio_url"]:
            reason = "missing_audio_url"

        if reason:
            skipped.append({"step_order": step_order, "reason": reason})
            continue

        audio_path = resolve_audio_path(step["audio_url"])
        if not audio_path.is_file():
            skipped.append({
                "step_order": step_order,
                "reason": "audio_file_not_found",
                "audio_url": step["audio_url"],
                "audio_path": str(audio_path),
            })
            continue

        runnable.append({
            "step_order": step_order,
            "sentence": step["sentence"],
            "audio_url": step["audio_url"],
            "audio_path": audio_path,
        })

    if requested_step_order is not None and not runnable and not skipped:
        raise ValueError(
            f"step_order {requested_step_order} does not exist for this content"
        )
    return runnable, skipped


def load_whisperx():
    try:
        import whisperx  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "WhisperX is not installed. Install scripts/"
            "requirements-narration-alignment.txt in a separate alignment "
            "environment, then run this script again."
        ) from error
    return whisperx


def _timestamped_chars(aligned: dict[str, Any]) -> list[dict[str, Any]]:
    chars = []
    for segment in aligned.get("segments", []):
        for item in segment.get("chars") or []:
            character = str(item.get("char", ""))
            output = {
                "text": character,
                "start": None,
                "end": None,
            }
            if "start" in item and "end" in item:
                output.update({
                    "start": float(item["start"]),
                    "end": float(item["end"]),
                })
            chars.append(output)
    return chars


def _timestamped_words(aligned: dict[str, Any]) -> list[dict[str, Any]]:
    words = []
    for item in aligned.get("word_segments", []):
        if "start" not in item or "end" not in item:
            continue
        text = str(item.get("word", "")).strip()
        if text:
            words.append({
                "text": text,
                "start": float(item["start"]),
                "end": float(item["end"]),
            })
    return words


def _chunk_units(
    units: Iterable[dict[str, Any]],
    max_units: int,
    joiner: str,
) -> list[dict[str, Any]]:
    cues = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        text = joiner.join(item["text"] for item in current).strip()
        text = re.sub(r"\s+([，。！？；：,.!?;:])", r"\1", text)
        if text:
            cues.append({
                "text": text,
                "start_seconds": round(current[0]["start"], 3),
                "end_seconds": round(current[-1]["end"], 3),
            })
        current.clear()

    for unit in units:
        text = unit["text"]
        if not text.strip():
            continue
        if unit.get("start") is None or unit.get("end") is None:
            if any(character in CLAUSE_ENDINGS for character in text):
                flush()
            continue
        current.append(unit)
        ends_clause = any(character in CLAUSE_ENDINGS for character in text)
        if ends_clause or len(current) >= max_units:
            flush()
    flush()
    return cues


def build_cues(
    aligned: dict[str, Any],
    language: Language,
    max_cue_units: int,
) -> list[dict[str, Any]]:
    if language in {"zh", "ja"}:
        units = _timestamped_chars(aligned)
        cues = _chunk_units(units, max_cue_units, "")
    else:
        units = _timestamped_words(aligned)
        cues = _chunk_units(units, max_cue_units, " ")
    if not cues:
        raise ValueError("alignment returned no timestamped cues")
    return cues


def align_step(
    whisperx,
    align_model,
    align_metadata: dict[str, Any],
    step: dict[str, Any],
    language: Language,
    device: str,
    max_cue_units: int,
) -> dict[str, Any]:
    audio = whisperx.load_audio(str(step["audio_path"]))
    sample_rate = 16000
    duration = len(audio) / sample_rate
    if duration <= 0:
        raise ValueError(f"empty audio file: {step['audio_path']}")

    transcript = [{
        "start": 0.0,
        "end": duration,
        "text": step["sentence"],
    }]
    aligned = whisperx.align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=True,
    )
    cues = build_cues(aligned, language, max_cue_units)
    return {
        "step_order": step["step_order"],
        "audio_url": step["audio_url"],
        "duration_seconds": round(duration, 3),
        "reference_text": step["sentence"],
        "cues": cues,
    }


def write_output(
    payload: dict[str, Any],
    output_path: Path,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"{output_path} already exists; pass --overwrite to replace it"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)


def merge_single_step_output(
    payload: dict[str, Any],
    output_path: Path,
    story_id: int,
    language: Language,
    step_order: int | None,
) -> dict[str, Any]:
    """Preserve other steps when rerunning only one step."""
    if step_order is None or not output_path.is_file():
        return payload
    try:
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"cannot merge invalid existing output: {output_path}"
        ) from error
    if (
        existing.get("story_id") != story_id
        or existing.get("language") != language
    ):
        raise ValueError(
            "existing output belongs to a different story or language"
        )

    old_steps = [
        item
        for item in existing.get("steps", [])
        if item.get("step_order") != step_order
    ]
    payload["steps"] = sorted(
        old_steps + payload["steps"],
        key=lambda item: item["step_order"],
    )
    for field in ("skipped_steps", "failed_steps"):
        old_items = [
            item
            for item in existing.get(field, [])
            if item.get("step_order") != step_order
        ]
        payload[field] = sorted(
            old_items + payload[field],
            key=lambda item: item["step_order"],
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Align seeded story narration audio with its known text and "
            "generate LangGraph narration cue JSON."
        )
    )
    parser.add_argument(
        "--story-id",
        type=int,
        required=True,
        help="1-based story position in app/seed_data/stories.py.",
    )
    parser.add_argument(
        "--language",
        choices=LANGUAGES,
        required=True,
    )
    parser.add_argument(
        "--step-order",
        type=int,
        help="Align one step only; omit to align every runnable step.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="WhisperX alignment device. CPU is the safest macOS default.",
    )
    parser.add_argument(
        "--align-model",
        help="Optional WhisperX/Hugging Face alignment model name.",
    )
    parser.add_argument(
        "--max-cue-units",
        type=int,
        help="Maximum characters (zh/ja) or words (en) per cue.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path; defaults to the LangGraph timing directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write successful steps even if another selected step fails.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate selection and files without loading WhisperX.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        language: Language = args.language
        story = select_story(args.story_id)
        content = select_content(story, language)
        runnable, skipped = selected_steps(
            story,
            content,
            args.step_order,
        )
        output_path = args.output or (
            OUTPUT_DIR / f"story_{args.story_id}_{language}.json"
        )

        logger.info(
            "Selected story | story_id=%s | slug=%s | language=%s | "
            "runnable_steps=%s | skipped=%s",
            args.story_id,
            story["slug"],
            language,
            [step["step_order"] for step in runnable],
            skipped,
        )
        if not runnable:
            raise ValueError("no runnable narration steps were found")
        if args.dry_run:
            logger.info("Dry run complete | output=%s", output_path)
            return 0

        whisperx = load_whisperx()
        model_kwargs = {
            "language_code": language,
            "device": args.device,
        }
        if args.align_model:
            model_kwargs["model_name"] = args.align_model
        logger.info(
            "Loading alignment model | language=%s | device=%s | model=%s",
            language,
            args.device,
            args.align_model or "WhisperX default",
        )
        align_model, align_metadata = whisperx.load_align_model(
            **model_kwargs
        )

        max_cue_units = (
            args.max_cue_units
            or DEFAULT_MAX_CUE_UNITS[language]
        )
        if max_cue_units < 1:
            raise ValueError("max-cue-units must be positive")

        aligned_steps = []
        failed_steps = []
        for step in runnable:
            logger.info(
                "Aligning narration | step_order=%s | audio=%s",
                step["step_order"],
                step["audio_path"],
            )
            try:
                result = align_step(
                    whisperx,
                    align_model,
                    align_metadata,
                    step,
                    language,
                    args.device,
                    max_cue_units,
                )
                aligned_steps.append(result)
                logger.info(
                    "Alignment complete | step_order=%s | duration=%.3f | "
                    "cues=%d",
                    result["step_order"],
                    result["duration_seconds"],
                    len(result["cues"]),
                )
            except Exception as error:  # Continue so one bad step is visible.
                logger.exception(
                    "Alignment failed | step_order=%s",
                    step["step_order"],
                )
                failed_steps.append({
                    "step_order": step["step_order"],
                    "reason": str(error),
                })

        if not aligned_steps:
            raise RuntimeError("all selected narration steps failed alignment")
        if failed_steps and not args.allow_partial:
            raise RuntimeError(
                "one or more steps failed; no file was written. Fix the "
                "errors or pass --allow-partial explicitly"
            )

        payload = {
            "story_id": args.story_id,
            "story_slug": story["slug"],
            "language": language,
            "alignment_method": "whisperx_forced_alignment_known_text",
            "steps": aligned_steps,
            "skipped_steps": skipped,
            "failed_steps": failed_steps,
        }
        payload = merge_single_step_output(
            payload,
            output_path,
            args.story_id,
            language,
            args.step_order,
        )
        write_output(payload, output_path, args.overwrite)
        logger.info(
            "Narration timing written | path=%s | aligned=%d | failed=%d",
            output_path,
            len(aligned_steps),
            len(failed_steps),
        )
        return 0 if not failed_steps else 2
    except Exception as error:
        logger.error("Narration alignment stopped: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
