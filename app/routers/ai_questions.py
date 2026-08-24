import sqlite3, logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Header
from app.db.database import get_db
from app.schemas.schemas import AILanguage, AIQuestion, AIAnswer, AIQuestionRequest
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
    ai_input = {}
    try:
        sentence = db.execute(
            """
            SELECT stpt.story_step_id, stpt.sentence
            FROM story_steps AS stp
            JOIN story_step_translations AS stpt
                ON stpt.story_step_id = stp.id
            WHERE stp.story_id = ?
            AND stp.step_order = ?
            AND stpt.language = ?
            """,
            (
                request.story_id,
                request.step_order,
                x_language,
            ),
        ).fetchone()
    except sqlite3.DatabaseError as e:
        logger.exception(
            "Failed to get story sentence: "
            "story_id=%s, step_order=%s, language=%s",
            request.story_id,
            request.step_order,
            x_language,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get story sentence"
        ) from e
    
    if sentence is None:
        raise HTTPException(
            status_code=404,
            detail="Story step not found"
        )
    else:
        ai_input["language"] = x_language
        ai_input["question"] = request.user_request
        ai_input["sentence"] = sentence["sentence"]

        KEEP_FIELDS = {
            "asset_key",
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
                        if k in KEEP_FIELDS
                    }
                    for obj in request.canvas["objects"]
                ],
                "background_key": request.canvas.get("background_key"),
            }
        
        ai_input["canvas"] = new_canvas
    
    logger.info(
        "AI request | question=%s | sentence=%s | canvas=%s",
        request.user_request,
        sentence["sentence"],
        new_canvas,
    )

    state = await router_workflow.ainvoke({"input": ai_input})
    if state["decision"] == "suggestion":
        logger.info(
            "AI suggestion | question=%s | sentence=%s | output=%s",
            request.user_request,
            sentence["sentence"],
            state["output"],
        )

    elif state["decision"] == "generate":
        logger.info(
            "AI generate | question=%s | sentence=%s | output=%s",
            request.user_request,
            sentence["sentence"],
            state["output"],
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
                    SELECT asset_key, image_url, audio_url
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
                obj["audio_url"] = asset["audio_url"]
                obj["flip_x"] = False

        background_key = state["output"]["background_key"]
        if background_key:
            try:
                row = db.execute(
                    """
                    SELECT image_url, audio_url
                    FROM assets
                    WHERE asset_key = ?
                    """,
                    (background_key,),
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

            state["output"]["background"] = {
                "image_url": row["image_url"],
                "audio_url": row["audio_url"],
            }            

    return {
        "mode": state["decision"],  # 建议还是生成
        "output": state["output"],
    }
