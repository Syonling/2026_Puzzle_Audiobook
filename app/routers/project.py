import sqlite3, json, logging
from fastapi import APIRouter, Depends, HTTPException
from app.db.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import (
    ProjectCreate,
    ProjectResponse,
    CanvasResponse,
    CanvasSaveRequest,
)

router = APIRouter(prefix="/projects", tags=["project"])
logger = logging.getLogger(__name__)

@router.post("", status_code=201)
def create_project(
    project: ProjectCreate,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    step = db.execute(
        """
        SELECT id, step_order
        FROM story_steps
        WHERE id = ?
          AND story_id = ?
        """,
        (
            project.story_step_id,
            project.story_id,
        ),
    ).fetchone()

    if step is None:
        raise HTTPException(
            status_code=404,
            detail="Story or story step not found",
        )

    try:
        cursor = db.execute(
            """
            INSERT INTO projects (
                user_id,
                story_id,
                title,
                current_step
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                current_user["id"],
                project.story_id,
                project.title,
                step["step_order"],
            ),
        )

        project_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO project_canvases (
                project_id,
                story_step_id,
                canvas_json,
                audio_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                project.story_step_id,
                json.dumps(
                    project.canvas,
                    ensure_ascii=False,
                ),
                json.dumps(
                    project.audio,
                    ensure_ascii=False,
                ),
            ),
        )

        db.commit()

    except sqlite3.DatabaseError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save project",
        ) from error

    return {
        "id": project_id,
        "story_id": project.story_id,
        "story_step_id": project.story_step_id,
        "title": project.title,
        "current_step": step["step_order"],
        "canvas": project.canvas,
        "audio": project.audio,
    }

@router.get("/{story_id}", response_model=ProjectResponse)
def get_project_by_story(
    story_id: int,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        project = db.execute(
            """
            SELECT
                id,
                story_id,
                title,
                current_step,
                created_at,
                updated_at
            FROM projects
            WHERE user_id = ?
              AND story_id = ?
            """,
            (
                current_user["id"],
                story_id,
            ),
        ).fetchone()
    except sqlite3.DatabaseError as error:
        logger.exception("Failed to get project by story")
        raise HTTPException(
            status_code=500,
            detail="Failed to get project",
        ) from error

    if project is None:
        logger.info("Project not exists, waiting for new creation")
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return dict(project)

# 读取单个画布
@router.get("/{project_id}/steps/{step_id}/canvas",response_model=CanvasResponse,)
def get_step_canvas(
    project_id: int,
    step_id: int,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        relation = db.execute(
            """
            SELECT
                p.id AS project_id,
                ss.id AS story_step_id
            FROM projects AS p
            JOIN story_steps AS ss
                ON ss.story_id = p.story_id
            WHERE p.id = ?
              AND p.user_id = ?
              AND ss.id = ?
            """,
            (
                project_id,
                current_user["id"],
                step_id,
            ),
        ).fetchone()

        if relation is None:
            raise HTTPException(
                status_code=404,
                detail="Project or story step not found",
            )

        row = db.execute(
            """
            SELECT canvas_json, audio_json
            FROM project_canvases
            WHERE project_id = ?
              AND story_step_id = ?
            """,
            (project_id, step_id),
        ).fetchone()

        canvas = (
            json.loads(row["canvas_json"])
            if row is not None
            else {"objects": [], "background_key": None}
        )

        audio = (
            json.loads(row["audio_json"])
            if row is not None
            else {}
        )

    except sqlite3.DatabaseError as error:
        logger.exception("Failed to get step canvas")
        raise HTTPException(
            status_code=500,
            detail="Failed to get canvas",
        ) from error
    except json.JSONDecodeError as error:
        logger.exception("Invalid canvas JSON in database")
        raise HTTPException(
            status_code=500,
            detail="Invalid canvas data",
        ) from error

    return {
        "project_id": project_id,
        "story_step_id": step_id,
        "canvas": canvas,
        "audio": audio,
    }

@router.put(
    "/{project_id}/steps/{step_id}/canvas",
    response_model=CanvasResponse,
)
def save_step_canvas(
    project_id: int,
    step_id: int,
    request: CanvasSaveRequest,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        relation = db.execute(
            """
            SELECT p.id
            FROM projects AS p
            JOIN story_steps AS ss
                ON ss.story_id = p.story_id
            WHERE p.id = ?
              AND p.user_id = ?
              AND ss.id = ?
            """,
            (
                project_id,
                current_user["id"],
                step_id,
            ),
        ).fetchone()

        if relation is None:
            raise HTTPException(
                status_code=404,
                detail="Project or story step not found",
            )

        canvas_json = json.dumps(
            request.canvas,
            ensure_ascii=False,
        )
        audio_json = json.dumps(
            request.audio,
            ensure_ascii=False,
        )
        

        db.execute(
            """
            INSERT INTO project_canvases (
                project_id,
                story_step_id,
                canvas_json,
                audio_json
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(project_id, story_step_id)
            DO UPDATE SET
                canvas_json = excluded.canvas_json,
                audio_json = excluded.audio_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                project_id,
                step_id,
                canvas_json,
                audio_json,
            ),
        )
        db.execute(
            """
            UPDATE projects
            SET current_step = (
                    SELECT step_order
                    FROM story_steps
                    WHERE id = ?
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND user_id = ?
            """,
            (
                step_id,
                project_id,
                current_user["id"],
            ),
        )
        db.commit()

        KEEP_FIELDS = {
            "asset_key",
            "x",
            "y",
            "scale",
            "rotation",
        }
        cave_save_log = {
            "objects": [
                    {
                        k: round(v, 1) if k in {"x", "y", "scale", "rotation"} else v
                        for k, v in obj.items()
                        if k in KEEP_FIELDS
                    }
                    for obj in request.canvas["objects"]
                ],
                "background_key": request.canvas.get("background_key"),
            }
     
        KEEP_CLIP_FIELDS = {
            "asset_key",
            "start_time",
            # "source_duration",
            "trim_start",
            "trim_end",
            # "duration",
            "volume",
            "pan",
        }

        audio_save_log = {
            "duration": request.audio["duration"],
            "tracks": [
                {
                    "id": track["id"],
                    "clips": [
                        {
                            k: (
                                round(v, 1)
                                if k in {"start_time", "duration"}
                                else round(v, 2)
                                if k in {"volume", "pan"}
                                else v
                            )
                            for k, v in clip.items()
                            if k in KEEP_CLIP_FIELDS
                        }
                        for clip in track["clips"]
                    ],
                }
                for track in request.audio["tracks"]
            ],
        }
        
        logger.info(
            "Project Updated | project_id=%s | story_step_id=%s | canvas=%s | audio=%s",
            project_id,
            step_id,
            cave_save_log,
            audio_save_log,
        )
    except sqlite3.DatabaseError as error:
        db.rollback()
        logger.exception("Failed to save step canvas")
        raise HTTPException(
            status_code=500,
            detail="Failed to save canvas",
        ) from error

    return {
        "project_id": project_id,
        "story_step_id": step_id,
        "canvas": request.canvas,
        "audio": request.audio,
    }
