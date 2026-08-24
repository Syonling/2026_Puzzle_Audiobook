import sqlite3, logging, secrets
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone


from app.db.database import get_db
from app.schemas.schemas import UserCreate, UserFeedback
from app.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# @router.post("/register", response_model=UserFeedback, status_code=201)
# def register(user: UserCreate, db:sqlite3.Connection=Depends(get_db)):
#     hashed = pwd_context.hash(user.password)
#     try:
#         cursor = db.execute("insert into users (user_name, password_hash) values (?, ?)",
#                    (user.username, hashed))
#         db.commit()
#     except sqlite3.IntegrityError as e:
#         db.rollback()
#         logger.exception("用户名已存在")
#         raise HTTPException(status_code=409, detail="用户名已存在") from e
    
#     row = db.execute("select * from users where id = ?", (cursor.lastrowid,)).fetchone()
#     return dict(row)

@router.post("/register", status_code=201) # response_model=UserFeedback,
def register(user:UserCreate, db:sqlite3.Connection=Depends(get_db)):
    try:
        cursor = db.execute("insert into users (username, password_hash) values (?,?)", (user.username, user.password))
        db.commit()

    except sqlite3.IntegrityError as e:
        db.rollback()
        logger.exception("Username already exist")
        raise HTTPException(status_code=409, detail="Username already exist") from e
    
    # row = db.execute("select * form users where id = ?", (cursor.lastrowid,)).fetchone()
    return {
        "message": "Register success",
        "user": {
            "id": cursor.lastrowid,
            "username": user.username,
        },
    }
@router.post("/login")
def login(user:UserCreate, response:Response, db:sqlite3.Connection=Depends(get_db)):
    row = db.execute("select * from users where username = ?",(user.username,)).fetchone()
    if (row is None) or (user.password != row["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    # 清除所有已经过期的 Session
    db.execute(
        """
        DELETE FROM sessions
        WHERE expires_at <= CURRENT_TIMESTAMP
        """
    )

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO sessions (user_id, token, expires_at)
        VALUES (?, ?, ?)
        """,
        (row["id"], token, expires_at),
    )
    db.commit()
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 60 * 60,
    )

    return {
        "message": "Login success",
        "user": {
            "id": row["id"],
            "username": row["username"],
        },
    }

@router.get("/me")
def get_me(
    current_user=Depends(get_current_user),
):
    return {
        "user": {
            "id": current_user["id"],
            "username": current_user["username"],
        }
    }

@router.post("/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    if session_token is not None:
        db.execute(
            "DELETE FROM sessions WHERE token = ?",
            (session_token,),
        )
        db.commit()

    response.delete_cookie(
        key="session_token",
        httponly=True,
        samesite="lax",
    )

    return {"message": "Logout success"}

