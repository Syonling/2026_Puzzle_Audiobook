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

        assets = [dict(row) for row in rows]
        asset_ids = [asset["id"] for asset in assets]
        options_by_asset_id = {
            asset_id: []
            for asset_id in asset_ids
        }

        if asset_ids:
            placeholders = ", ".join("?" for _ in asset_ids)
            option_rows = db.execute(
                f"""
                SELECT
                    ao.asset_id,
                    ao.audio_key,
                    COALESCE(aot.name, ao.audio_key) AS name,
                    ao.audio_url,
                    ao.is_default,
                    ao.sort_order
                FROM asset_audio_options AS ao
                LEFT JOIN asset_audio_option_translations AS aot
                    ON aot.audio_option_id = ao.id
                   AND aot.language = ?
                WHERE ao.asset_id IN ({placeholders})
                ORDER BY
                    ao.asset_id,
                    ao.sort_order,
                    ao.id
                """,
                [x_language, *asset_ids],
            ).fetchall()

            for row in option_rows:
                options_by_asset_id[row["asset_id"]].append(
                    {
                        "audio_key": row["audio_key"],
                        # 当前没有音频名称时，使用 audio_key 作为稳定技术回退值。
                        "name": row["name"],
                        "audio_url": row["audio_url"],
                        "is_default": bool(row["is_default"]),
                        "sort_order": row["sort_order"],
                    }
                )

    except sqlite3.DatabaseError as error:
        logger.exception("Failed to get assets")

        raise HTTPException(
            status_code=500,
            detail="Failed to get assets",
        ) from error

    for asset in assets:
        audio_options = options_by_asset_id[asset["id"]]
        default_option = next(
            (
                option
                for option in audio_options
                if option["is_default"]
            ),
            None,
        )

        asset["default_audio_key"] = (
            default_option["audio_key"]
            if default_option is not None
            else None
        )
        asset["audio_options"] = audio_options

    return assets
