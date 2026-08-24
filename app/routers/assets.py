import logging
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException

from app.db.database import get_db
from app.schemas.schemas import AssetsResponse


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
)


@router.get("", response_model=list[AssetsResponse])
def get_assets(
    category: str | None = None,
    keyword: str | None = None,
    x_language: Literal["ja", "zh", "en"] = Header(
        default="zh",
        alias="X-Language",
    ),
    db: sqlite3.Connection = Depends(get_db),
):
    # 将空字符串转成 None
    category = category.strip() if category else None
    keyword = keyword.strip() if keyword else None

    sql = """
        SELECT
            a.id,
            a.asset_key,
            at.name,
            a.category,
            at.category_translation,
            a.image_url,
            a.audio_url
        FROM assets AS a
        JOIN assets_translations AS at
            ON at.asset_id = a.id
           AND at.language = ?
    """

    conditions = []
    parameters = [x_language]

    # 只有 category
    if category:
        conditions.append("a.category = ?")
        parameters.append(category)

    # 只有 keyword，或者 category 和 keyword 同时存在
    if keyword:
        conditions.append(
            "(at.name LIKE ? OR a.asset_key LIKE ?)"
        )

        search_value = f"%{keyword}%"

        parameters.extend([
            search_value,
            search_value,
        ])

    # 有筛选条件时才添加 WHERE
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY a.id"

    try:
        rows = db.execute(
            sql,
            parameters,
        ).fetchall()

    except sqlite3.DatabaseError as error:
        logger.exception("Failed to get assets")

        raise HTTPException(
            status_code=500,
            detail="Failed to get assets",
        ) from error

    return [dict(row) for row in rows]
