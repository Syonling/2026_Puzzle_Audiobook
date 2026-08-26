import sqlite3
import logging
import time
from typing import Literal, TypedDict

from fastapi import HTTPException
from langchain_openai import ChatOpenAI

from app.core.config import DB_DIR, settings
from app.db.database import create_connection
from app.services.langgraph.audio_effect_presets import (
    AUDIO_EFFECT_DESCRIPTIONS,
)
from app.services.langgraph.background_descriptions import (
    BACKGROUND_DESCRIPTIONS,
)

logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    model=settings.llm_model, 
    api_key=settings.openai_api_key.get_secret_value(),
    timeout=30, # 单次请求最多等待约 30 秒
    max_retries=1, # 遇到临时网络故障或可重试错误时，最多重试两次
    )


Language = Literal["zh", "ja", "en"]


class AudioOptionContext(TypedDict):
    audio_key: str
    name: str
    is_default: bool


class BackgroundContext(TypedDict):
    background_key: str
    scene_description: str
    has_audio: bool


class AssetContext(TypedDict):
    icons: list[str]
    audio_options_by_asset: dict[str, list[AudioOptionContext]]
    backgrounds: list[BackgroundContext]
    audio_effects: list[dict[str, str]]


def get_asset_context(language: Language = "zh") -> AssetContext:
    """Return the exact asset, audio-option, background, and effect choices."""
    started_at = time.perf_counter()
    db = create_connection(DB_DIR)

    try:
        asset_rows = db.execute(
            "SELECT asset_key, category, audio_url FROM assets"
        ).fetchall()
        audio_rows = db.execute(
            """
            SELECT
                a.asset_key,
                aao.audio_key,
                COALESCE(aaot.name, aao.audio_key) AS name,
                aao.is_default,
                aao.sort_order
            FROM assets AS a
            JOIN asset_audio_options AS aao
                ON aao.asset_id = a.id
            LEFT JOIN asset_audio_option_translations AS aaot
                ON aaot.audio_option_id = aao.id
                AND aaot.language = ?
            ORDER BY a.id, aao.sort_order, aao.id
            """,
            (language,),
        ).fetchall()

        audio_options_by_asset: dict[str, list[AudioOptionContext]] = {}
        for row in audio_rows:
            audio_options_by_asset.setdefault(row["asset_key"], []).append(
                {
                    "audio_key": row["audio_key"],
                    "name": row["name"],
                    "is_default": bool(row["is_default"]),
                }
            )

        icons = [
            row["asset_key"]
            for row in asset_rows
            if row["category"] != "background"
        ]
        backgrounds: list[BackgroundContext] = [
            {
                "background_key": row["asset_key"],
                "scene_description": BACKGROUND_DESCRIPTIONS.get(
                    row["asset_key"],
                    "",
                ),
                "has_audio": (
                    row["asset_key"] in audio_options_by_asset
                ),
            }
            for row in asset_rows
            if row["category"] == "background"
        ]

        missing_descriptions = [
            item["background_key"]
            for item in backgrounds
            if not item["scene_description"]
        ]
        if missing_descriptions:
            logger.warning(
                "Background descriptions missing | background_keys=%s",
                missing_descriptions,
            )

        context: AssetContext = {
            "icons": icons,
            "audio_options_by_asset": audio_options_by_asset,
            "backgrounds": backgrounds,
            "audio_effects": [
                {
                    "effect_key": effect_key,
                    "description": description,
                }
                for effect_key, description
                in AUDIO_EFFECT_DESCRIPTIONS.items()
            ],
        }
        logger.info(
            "AI asset context loaded | language=%s | icons=%d | "
            "audio_assets=%d | backgrounds=%d | elapsed_ms=%.1f",
            language,
            len(icons),
            len(audio_options_by_asset),
            len(backgrounds),
            (time.perf_counter() - started_at) * 1000,
        )
        return context

    except sqlite3.DatabaseError as e:
        logger.exception(
            "Failed to load AI asset context | language=%s",
            language,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get assets"
        ) from e

    finally:
        db.close()


def get_assets_list() -> tuple[list[str], list[str], list[str]]:
    """Compatibility helper for code that still expects the old three lists."""
    context = get_asset_context()
    icon_list = list(context["icons"])
    background_list = [
        item["background_key"]
        for item in context["backgrounds"]
    ]
    audio_icon_list = [
        asset_key
        for asset_key in context["icons"]
        if asset_key in context["audio_options_by_asset"]
    ]
    return icon_list, background_list, audio_icon_list






# if __name__ == "__main__":
#     assets_list = get_assets_list()
#     print(assets_list)
