import logging
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Header
from app.db.database import get_db
from app.schemas.schemas import AIQuestion, AIAnswer, AIQuestionRequest
# from app.services.llm import llm_api
from app.services.langgraph.puzzle_agent import router_workflow
from app.core.security import get_current_user

router = APIRouter(prefix="/ai",tags=["ai_questions"])
logger = logging.getLogger(__name__)

@router.get("/getquestions", response_model=list[AIQuestion])
def get_questions(
    x_language: Literal["ja", "zh", "en"] = 
    Header(
        default="zh",
        alias="X-Language",
    ), 
    db:sqlite3.Connection=Depends(get_db)):
    try:
        rows = db.execute("select question_id, question from question_translations where language = ? order by question_id", (x_language, )).fetchall()
    except sqlite3.DatabaseError as e:
        logger.exception("Failed to get questions")
        raise HTTPException(
            status_code=500,
            detail="Failed to get questions"
        ) from e
    
    return [dict(row) for row in rows]

@router.post("/getanswer", response_model= AIAnswer) # 
async def get_answer(request:AIQuestionRequest,
                     x_language: Literal["ja", "zh", "en"] = 
                        Header(
                            default="zh",
                            alias="X-Language",
                        ), current_user = Depends(get_current_user), db:sqlite3.Connection=Depends(get_db)):
    started_at = time.perf_counter()
    ai_input = {}
    try:
        story_steps = db.execute(
            """
            SELECT
                stpt.story_step_id,
                stp.step_order,
                stp.step_type,
                stpt.sentence
            FROM story_steps AS stp
            JOIN story_step_translations AS stpt
                ON stpt.story_step_id = stp.id
            WHERE stp.story_id = ?
            AND stp.step_order <= ?
            AND stpt.language = ?
            ORDER BY stp.step_order
            """,
            (
                request.story_id,
                request.step_order,
                x_language,
            ),
        ).fetchall()
    except sqlite3.DatabaseError as e:
        logger.exception(
            "Failed to get story context: "
            "story_id=%s, step_order=%s, language=%s",
            request.story_id,
            request.step_order,
            x_language,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get story context"
        ) from e

    if not story_steps or story_steps[-1]["step_order"] != request.step_order:
        logger.warning(
            "AI story step not found | story_id=%s | step_order=%s | "
            "language=%s",
            request.story_id,
            request.step_order,
            x_language,
        )
        raise HTTPException(
            status_code=404,
            detail="Story step not found"
        )
    else:
        current_step = story_steps[-1]
        previous_steps = [
            {
                "step_order": row["step_order"],
                "step_type": row["step_type"],
                "sentence": row["sentence"],
            }
            for row in story_steps[:-1]
        ]
        ai_input["language"] = x_language
        ai_input["question"] = request.user_request
        ai_input["story_context"] = {
            "previous_steps": previous_steps,
            "current_step": {
                "step_order": current_step["step_order"],
                "step_type": current_step["step_type"],
                "sentence": current_step["sentence"],
            },
        }

        keep_fields = {
            "instance_id",
            "asset_key",
            "selected_audio_key",
            "x",
            "y",
            "scale",
            "rotation",
        }

        new_canvas = {
            "objects": [
                    {
                        k: round(v, 1) if k in {"x", "y", "scale", "rotation"} else v
                        for k, v in obj.items()
                        if k in keep_fields
                    }
                    for obj in request.canvas.get("objects", [])
                    if isinstance(obj, dict)
                ],
                "background_key": request.canvas.get("background_key"),
            }

        ai_input["canvas"] = new_canvas
        ai_input["audio"] = {
            "tracks": [
                {
                    "id": track.get("id"),
                    "clips": [
                        {
                            key: clip.get(key)
                            for key in (
                                "object_instance_id",
                                "asset_key",
                                "audio_key",
                                "start_time",
                                "volume",
                                "pan",
                                "effects",
                            )
                            if key in clip
                        }
                        for clip in track.get("clips", [])
                        if isinstance(clip, dict)
                    ],
                }
                for track in request.audio.get("tracks", [])
                if isinstance(track, dict)
            ]
        }

    audio_clip_count = sum(
        len(track.get("clips", []))
        for track in ai_input["audio"].get("tracks", [])
    )
    logger.info(
        "AI request started | user_id=%s | story_id=%s | step_order=%s | "
        "language=%s | question_chars=%d | canvas_objects=%d | "
        "background=%s | audio_clips=%d | previous_steps=%d",
        current_user["id"],
        request.story_id,
        request.step_order,
        x_language,
        len(request.user_request),
        len(new_canvas["objects"]),
        new_canvas["background_key"],
        audio_clip_count,
        len(previous_steps),
    )

    try:
        state = await router_workflow.ainvoke({"input": ai_input})
    except Exception as error:
        logger.exception(
            "AI workflow failed | user_id=%s | story_id=%s | "
            "step_order=%s | language=%s | elapsed_ms=%.1f",
            current_user["id"],
            request.story_id,
            request.step_order,
            x_language,
            (time.perf_counter() - started_at) * 1000,
        )
        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable",
        ) from error

    if state["decision"] == "suggestion":
        audio_suggestions = state["output"].get(
            "audio_suggestions",
            [],
        )
        suggested_audio_keys = list(dict.fromkeys(
            suggestion["selected_audio_key"]
            for suggestion in audio_suggestions
            if suggestion.get("selected_audio_key")
        ))
        audio_by_key = {}
        if suggested_audio_keys:
            placeholders = ", ".join(
                "?" for _ in suggested_audio_keys
            )
            try:
                rows = db.execute(
                    f"""
                    SELECT
                        a.asset_key,
                        aao.audio_key,
                        aao.audio_url
                    FROM asset_audio_options AS aao
                    JOIN assets AS a
                        ON a.id = aao.asset_id
                    WHERE aao.audio_key IN ({placeholders})
                    """,
                    suggested_audio_keys,
                ).fetchall()
            except sqlite3.DatabaseError as error:
                logger.exception(
                    "Failed to resolve suggested audio options | "
                    "audio_keys=%s",
                    suggested_audio_keys,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get suggested audio information",
                ) from error
            audio_by_key = {
                row["audio_key"]: row
                for row in rows
            }

        for suggestion in audio_suggestions:
            audio_key = suggestion.get("selected_audio_key")
            audio = audio_by_key.get(audio_key)
            if (
                audio is None
                or audio["asset_key"] != suggestion.get("asset_key")
            ):
                logger.error(
                    "Suggested audio option does not belong to asset | "
                    "asset_key=%s | audio_key=%s",
                    suggestion.get("asset_key"),
                    audio_key,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Suggested audio data is invalid",
                )
            suggestion["audio_url"] = audio["audio_url"]

        logger.info(
            "AI suggestion ready | user_id=%s | icons=%d | "
            "audio_suggestions=%d | background=%s",
            current_user["id"],
            len(state["output"].get("icon_keys", [])),
            len(state["output"].get("audio_suggestions", [])),
            state["output"].get("background_key"),
        )

    elif state["decision"] == "generate":
        logger.info(
            "AI canvas ready | user_id=%s | objects=%d | background=%s | "
            "background_audio=%s",
            current_user["id"],
            len(state["output"].get("objects", [])),
            state["output"].get("background_key"),
            state["output"].get("background_audio_enabled"),
        )
        objects = state["output"]["objects"]
        asset_keys = list(dict.fromkeys(
            obj["asset_key"] for obj in objects
        ))

        if asset_keys:
            placeholders = ", ".join("?" for _ in asset_keys)

            try:
                rows = db.execute(
                    f"""
                    SELECT asset_key, image_url
                    FROM assets
                    WHERE asset_key IN ({placeholders})
                    """,
                    asset_keys,
                ).fetchall()
            except sqlite3.DatabaseError as error:
                logger.exception("Failed to get generated asset information")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get generated asset information",
                ) from error

            assets_by_key = {
                row["asset_key"]: row
                for row in rows
            }
            missing_keys = [
                asset_key
                for asset_key in asset_keys
                if asset_key not in assets_by_key
            ]

            if missing_keys:
                logger.error(
                    "Generated assets not found: asset_keys=%s",
                    missing_keys,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Generated asset data is invalid",
                )

            for obj in objects:
                asset = assets_by_key[obj["asset_key"]]
                obj["image_url"] = asset["image_url"]
                obj["flip_x"] = False

            selected_audio_keys = list(dict.fromkeys(
                obj["selected_audio_key"]
                for obj in objects
                if obj.get("selected_audio_key")
            ))
            audio_by_key = {}
            if selected_audio_keys:
                audio_placeholders = ", ".join(
                    "?" for _ in selected_audio_keys
                )
                try:
                    audio_rows = db.execute(
                        f"""
                        SELECT
                            a.asset_key,
                            aao.audio_key,
                            aao.audio_url
                        FROM asset_audio_options AS aao
                        JOIN assets AS a
                            ON a.id = aao.asset_id
                        WHERE aao.audio_key IN ({audio_placeholders})
                        """,
                        selected_audio_keys,
                    ).fetchall()
                except sqlite3.DatabaseError as error:
                    logger.exception(
                        "Failed to resolve generated audio options | "
                        "audio_keys=%s",
                        selected_audio_keys,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to get generated audio information",
                    ) from error
                audio_by_key = {
                    row["audio_key"]: row
                    for row in audio_rows
                }

            for obj in objects:
                selected_audio_key = obj.get("selected_audio_key")
                if selected_audio_key is None:
                    obj["audio_url"] = None
                    continue
                audio = audio_by_key.get(selected_audio_key)
                if audio is None or audio["asset_key"] != obj["asset_key"]:
                    logger.error(
                        "Generated audio option does not belong to asset | "
                        "asset_key=%s | audio_key=%s",
                        obj["asset_key"],
                        selected_audio_key,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Generated audio data is invalid",
                    )
                obj["audio_url"] = audio["audio_url"]

        background_key = state["output"]["background_key"]
        if background_key:
            selected_background_audio_key = state["output"].get(
                "selected_background_audio_key"
            )
            try:
                row = db.execute(
                    """
                    SELECT
                        a.image_url,
                        aao.audio_key,
                        aao.audio_url
                    FROM assets AS a
                    LEFT JOIN asset_audio_options AS aao
                        ON aao.asset_id = a.id
                       AND aao.audio_key = ?
                    WHERE a.asset_key = ?
                      AND a.category = 'background'
                    """,
                    (
                        selected_background_audio_key,
                        background_key,
                    ),
                ).fetchone()
            except sqlite3.DatabaseError as error:
                logger.exception("Failed to get generated background information")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get generated background information",
                ) from error
            
            if row is None:
                logger.error(
                    "Generated background not found: background_key=%s",
                    background_key,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Generated background data is invalid",
                )

            if (
                selected_background_audio_key is not None
                and row["audio_key"] is None
            ):
                logger.error(
                    "Generated background audio option is invalid | "
                    "background_key=%s | audio_key=%s",
                    background_key,
                    selected_background_audio_key,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Generated background audio data is invalid",
                )

            state["output"]["background"] = {
                "asset_key": background_key,
                "image_url": row["image_url"],
                "selected_audio_key": row["audio_key"],
                "audio_url": row["audio_url"],
                "audio_enabled": bool(
                    state["output"].get("background_audio_enabled")
                    and row["audio_key"]
                    and row["audio_url"]
                ),
                "start_offset_seconds": state["output"].get(
                    "background_start_offset_seconds"
                ),
                "effects": state["output"].get(
                    "background_effects",
                    {},
                ),
            }

    logger.info(
        "AI request completed | user_id=%s | story_id=%s | step_order=%s | "
        "mode=%s | elapsed_ms=%.1f",
        current_user["id"],
        request.story_id,
        request.step_order,
        state["decision"],
        (time.perf_counter() - started_at) * 1000,
    )

    return {
        "mode": state["decision"],  # 建议还是生成
        "output": state["output"],
    }
