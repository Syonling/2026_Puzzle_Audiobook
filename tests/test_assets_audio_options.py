import sqlite3
import unittest
from pathlib import Path

from app.routers.assets import get_assets
from app.schemas.schemas import AssetsResponse
from app.services.seed_data import seed_database


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "app/db/schema.sql"


class AssetsAudioOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        seed_database(self.db)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_assets_include_grouped_audio_options_without_duplicates(self) -> None:
        assets = get_assets(
            category=None,
            keyword=None,
            x_language="zh",
            db=self.db,
        )

        asset_keys = [asset["asset_key"] for asset in assets]
        self.assertEqual(len(asset_keys), len(set(asset_keys)))
        validated_assets = [
            AssetsResponse.model_validate(asset)
            for asset in assets
        ]
        self.assertEqual(len(validated_assets), len(assets))

        cow = next(asset for asset in assets if asset["asset_key"] == "cow")
        self.assertEqual(cow["default_audio_key"], "cow_default")
        self.assertEqual(len(cow["audio_options"]), 1)
        self.assertEqual(
            cow["audio_options"][0],
            {
                "audio_key": "cow_default",
                "name": "cow_default",
                "audio_url": "/static/audio/cow.wav",
                "is_default": True,
                "sort_order": 0,
            },
        )

        background = next(
            asset
            for asset in assets
            if asset["asset_key"] == "farm_background"
        )
        self.assertIsNone(background["default_audio_key"])
        self.assertEqual(background["audio_options"], [])


if __name__ == "__main__":
    unittest.main()
