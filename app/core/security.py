import sqlite3
from fastapi import Cookie, Depends, HTTPException

from app.db.database import get_db

def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    if session_token is None:
        raise HTTPException(
            status_code=401,
            detail="Not logged in",
        )

    user = db.execute(
        """
        SELECT users.id, users.username
        FROM sessions
        JOIN users
            ON users.id = sessions.user_id
        WHERE sessions.token = ?
          AND sessions.expires_at > CURRENT_TIMESTAMP
        """,
        (session_token,),
    ).fetchone()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    return user