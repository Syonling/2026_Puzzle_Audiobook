import logging
from logging.handlers import RotatingFileHandler

from app.core.config import settings, LOG_DIR


def setup_logging() -> None:
    file_handler = RotatingFileHandler(
        LOG_DIR,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    ) 

    console_handler = logging.StreamHandler()

    logging.basicConfig(
        level= settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[file_handler, console_handler]
        )