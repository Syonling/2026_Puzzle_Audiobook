# - 实现 `GET /stories`，返回书架卡片列表。
# - 实现 `GET /stories/{id}`，返回全文和有序步骤。
# - 不存在的故事返回 404。

import logging, sqlite3
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Literal

from app.db.database import get_db
from app.schemas.schemas import StoryStepResponse, StorySummary, StoryDetail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stories", tags=['stories'])

# SELECT st.title, st.description
# FROM story_translations AS st
# WHERE st.story_id = ?
#   AND st.language = ?

@router.get("", response_model=list[StorySummary])
def bookshelf(x_language: Literal["ja", "zh", "en"] = Header(
        default="zh",
        alias="X-Language",
    ),db:sqlite3.Connection=Depends(get_db)):
    try:
        # rows = db.execute("select * from stories order by id ").fetchall()
        rows = db.execute(
            """
            SELECT
                s.id,
                s.slug,
                s.thumbnail_url,
                st.title,
                st.description
            FROM stories AS s
            JOIN story_translations AS st
                ON st.story_id = s.id
            WHERE st.language = ?
            ORDER BY s.id
            """,
            (x_language,),
        ).fetchall()
    except sqlite3.DatabaseError as error:
        logger.exception("Failed to get stories")

        raise HTTPException(
            status_code=500,
            detail="Failed to check db/stories",
        ) from error
    return [dict(row) for row in rows]


@router.get(
    "/{story_id}/steps",
    response_model=list[StoryStepResponse],
)
def get_story_steps(
    story_id: int,
    x_language: Literal["ja", "zh", "en"] = Header(
        default="zh",
        alias="X-Language",
    ),
    db: sqlite3.Connection = Depends(get_db),
):
    story = db.execute(
        """
        SELECT id
        FROM stories
        WHERE id = ?
        """,
        (story_id,),
    ).fetchone()

    if story is None:
        raise HTTPException(
            status_code=404,
            detail="Story id not found",
        )

    rows = db.execute(
        """
        SELECT
            stp.id,
            stp.story_id,
            stp.step_order,
            stpt.sentence
        FROM story_steps AS stp
        JOIN story_step_translations AS stpt
            ON stpt.story_step_id = stp.id
        WHERE stp.story_id = ?
            AND stpt.language = ?
        ORDER BY stp.step_order
        """,
        (story_id, x_language),
    ).fetchall()

    return [dict(row) for row in rows]