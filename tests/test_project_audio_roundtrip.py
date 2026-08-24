import sqlite3
import unittest
from pathlib import Path

from app.routers.project import (
    create_project,
    get_step_canvas,
    save_step_canvas,
)
from app.schemas.schemas import CanvasSaveRequest, ProjectCreate


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "app/db/schema.sql"


class ProjectAudioRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        user_cursor = self.db.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            """,
            ("test-user", "test-password"),
        )
        story_cursor = self.db.execute(
            "INSERT INTO stories (slug) VALUES (?)",
            ("test-story",),
        )
        step_cursor = self.db.execute(
            """
            INSERT INTO story_steps (story_id, step_order)
            VALUES (?, ?)
            """,
            (story_cursor.lastrowid, 1),
        )
        self.db.commit()

        self.current_user = {
            "id": user_cursor.lastrowid,
            "username": "test-user",
        }
        self.story_id = story_cursor.lastrowid
        self.step_id = step_cursor.lastrowid

    def tearDown(self) -> None:
        self.db.close()

    def test_canvas_and_audio_fields_are_saved_without_removal(self) -> None:
        initial_canvas = {
            "objects": [],
            "background_key": None,
        }
        initial_audio = {
            "duration": 0,
            "tracks": [],
        }
        project = create_project(
            ProjectCreate(
                story_id=self.story_id,
                story_step_id=self.step_id,
                title="Audio test",
                canvas=initial_canvas,
                audio=initial_audio,
            ),
            current_user=self.current_user,
            db=self.db,
        )

        canvas = {
            "objects": [
                {
                    "instance_id": "object-123",
                    "asset_key": "bird",
                    "selected_audio_key": "bird_short",
                    "x": 300,
                    "y": 200,
                    "scale": 1,
                    "rotation": 0,
                }
            ],
            "background_key": None,
        }
        audio = {
            "duration": 10,
            "tracks": [
                {
                    "id": "track-1",
                    "clips": [
                        {
                            "clip_id": "clip-456",
                            "object_instance_id": "object-123",
                            "asset_key": "bird",
                            "audio_key": "bird_short",
                            "audio_url": "/static/audio/bird_short.wav",
                            "start_time": 4.5,
                            "trim_start": 0,
                            "trim_end": 5.5,
                            "volume": 1,
                            "pan": 0,
                        }
                    ],
                }
            ],
        }

        saved = save_step_canvas(
            project["id"],
            self.step_id,
            CanvasSaveRequest(canvas=canvas, audio=audio),
            current_user=self.current_user,
            db=self.db,
        )
        loaded = get_step_canvas(
            project["id"],
            self.step_id,
            current_user=self.current_user,
            db=self.db,
        )

        self.assertEqual(saved["canvas"], canvas)
        self.assertEqual(saved["audio"], audio)
        self.assertEqual(loaded["canvas"], canvas)
        self.assertEqual(loaded["audio"], audio)


if __name__ == "__main__":
    unittest.main()
