from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name : str = "Puzzle Audiobook"
    db_name : str = "puzzle_audiobook.db"
    log_name : str = "puzzle_audiobook.log"
    log_level : str
    openai_api_key : SecretStr
    llm_model : str
    openai_api_image_key: SecretStr
    deepseek_api_key: SecretStr

    model_config = SettingsConfigDict(
        env_file = BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
DB_DIR = BASE_DIR / settings.db_name
LOG_DIR = BASE_DIR / settings.log_name
STATIC_DIR = BASE_DIR / "static"
