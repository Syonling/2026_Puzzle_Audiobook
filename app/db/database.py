import sqlite3
from collections.abc import Iterator

from app.core.config import BASE_DIR, DB_DIR
from app.services.seed_data import seed_database

SCHEMA_PATH = BASE_DIR / "app/db/schema.sql"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA_SQL = f.read()  # string

def create_connection(db_dir) -> sqlite3.Connection:
    connect = sqlite3.connect(db_dir, check_same_thread=False)
    # 以下两条默认开启
    connect.row_factory = sqlite3.Row
    connect.execute("PRAGMA foreign_keys = ON")
    # Logging writes are short, but may overlap an AI response update.
    connect.execute("PRAGMA busy_timeout = 5000")
    return connect

def get_db() -> Iterator[sqlite3.Connection] :
    connect = create_connection(DB_DIR)
    try:
        yield connect
    finally:
        connect.close()


def _migrate_story_narration_columns(
    connect: sqlite3.Connection,
) -> None:
    """Add narration columns to an existing database without deleting data."""
    story_step_columns = {
        row["name"]
        for row in connect.execute(
            "PRAGMA table_info(story_steps)"
        ).fetchall()
    }
    if "step_type" not in story_step_columns:
        connect.execute(
            """
            ALTER TABLE story_steps
            ADD COLUMN step_type TEXT NOT NULL DEFAULT 'story'
                CHECK (step_type IN ('story', 'free_creation'))
            """
        )

    translation_columns = {
        row["name"]
        for row in connect.execute(
            "PRAGMA table_info(story_step_translations)"
        ).fetchall()
    }
    if "audio_url" not in translation_columns:
        connect.execute(
            """
            ALTER TABLE story_step_translations
            ADD COLUMN audio_url TEXT
            """
        )

def init_db() -> None :
    connect = create_connection(DB_DIR)

    try:
        connect.executescript(SCHEMA_SQL)
        _migrate_story_narration_columns(connect)
        seed_database(connect)
        connect.commit()
    except sqlite3.DatabaseError:
        connect.rollback()
        raise
    finally:
        connect.close()
