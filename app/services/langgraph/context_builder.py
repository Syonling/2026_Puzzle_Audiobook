import sqlite3
from fastapi import Depends, HTTPException

from app.core.config import BASE_DIR, DB_DIR
from app.db.database import create_connection
from app.core.config import settings
# from app.schemas.schemas import AssetsList
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.llm_model, 
    api_key=settings.openai_api_key.get_secret_value(),
    timeout=30, # 单次请求最多等待约 30 秒
    max_retries=1, # 遇到临时网络故障或可重试错误时，最多重试两次
    )


def get_assets_list() -> tuple[list[str], list[str], list[str]]:
    db = create_connection(DB_DIR)

    try:
        rows = db.execute(
            "SELECT asset_key, category, audio_url FROM assets"
        ).fetchall()

        icon_list = [row["asset_key"] for row in rows if row["category"] != "background"]
        background_list = [row["asset_key"] for row in rows if row["category"] == "background"]
        audio_icon_list = [
            row["asset_key"]
            for row in rows
            if row["category"] != "background" and row["audio_url"]
        ]

        return icon_list, background_list, audio_icon_list

    except sqlite3.DatabaseError as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to get assets"
        ) from e

    finally:
        db.close()






# if __name__ == "__main__":
#     assets_list = get_assets_list()
#     print(assets_list)
