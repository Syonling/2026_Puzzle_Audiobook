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
    return connect

def get_db() -> Iterator[sqlite3.Connection] :
    connect = create_connection(DB_DIR)
    try:
        yield connect
    finally:
        connect.close()

def init_db() -> None :
    connect = create_connection(DB_DIR)

    try:
        connect.executescript(SCHEMA_SQL)
        seed_database(connect)
        connect.commit()
    except sqlite3.DatabaseError:
        connect.rollback()
        raise
    finally:
        connect.close()
