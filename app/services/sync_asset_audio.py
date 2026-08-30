"""Safely synchronize asset audio seed data into an existing database.

Preview is the default. Pass ``--apply`` to write changes after creating a
consistent SQLite backup. Existing options missing from seed data are kept.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.core.config import BASE_DIR, DB_DIR, STATIC_DIR
from app.db.database import create_connection
from app.seed_data.assets import ASSETS
from app.services.seed_data import (
    _get_asset_audio_options,
    _validate_asset_audio_options,
)


def _static_file(audio_url: str) -> Path:
    prefix = "/static/"
    if not audio_url.startswith(prefix):
        raise ValueError(
            f"Audio URL must start with {prefix}: {audio_url}"
        )
    relative_path = Path(audio_url.removeprefix(prefix))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Unsafe audio URL: {audio_url}")
    return STATIC_DIR / relative_path


def _desired_assets() -> dict[str, dict]:
    _validate_asset_audio_options()
    desired = {}
    missing_files = []

    for asset in ASSETS:
        options = _get_asset_audio_options(asset)
        for option in options:
            audio_path = _static_file(option["audio_url"])
            if not audio_path.is_file():
                missing_files.append(
                    f"{option['audio_key']}: {audio_path}"
                )
        desired[asset["asset_key"]] = {
            "default_audio_url": asset.get("audio_url"),
            "options": options,
        }

    if missing_files:
        raise ValueError(
            "Audio files do not exist:\n- " + "\n- ".join(missing_files)
        )
    return desired


def _load_database_state(connect: sqlite3.Connection) -> tuple[dict, dict, dict]:
    assets = {
        row["asset_key"]: dict(row)
        for row in connect.execute(
            "SELECT id, asset_key, audio_url FROM assets"
        ).fetchall()
    }
    options = {
        row["audio_key"]: dict(row)
        for row in connect.execute(
            """
            SELECT id, asset_id, audio_key, audio_url, is_default, sort_order
            FROM asset_audio_options
            """
        ).fetchall()
    }
    translations = {
        (row["audio_option_id"], row["language"]): row["name"]
        for row in connect.execute(
            """
            SELECT audio_option_id, language, name
            FROM asset_audio_option_translations
            """
        ).fetchall()
    }
    return assets, options, translations


def build_plan(connect: sqlite3.Connection) -> list[dict]:
    desired = _desired_assets()
    assets, options, translations = _load_database_state(connect)
    actions = []

    for asset_key, config in desired.items():
        asset = assets.get(asset_key)
        if asset is None:
            if config["default_audio_url"] or config["options"]:
                raise ValueError(
                    "Audio seed data references an asset that is not in the "
                    f"database: {asset_key}. Add the icon separately first."
                )
            continue

        default_url = config["default_audio_url"]
        if default_url and asset["audio_url"] != default_url:
            actions.append({
                "kind": "update_asset_default_url",
                "asset_id": asset["id"],
                "asset_key": asset_key,
                "old": asset["audio_url"],
                "new": default_url,
            })

        desired_default = next(
            (
                option["audio_key"]
                for option in config["options"]
                if option["is_default"]
            ),
            None,
        )
        if desired_default is not None:
            current_defaults = {
                key
                for key, option in options.items()
                if option["asset_id"] == asset["id"]
                and option["is_default"]
            }
            if current_defaults != {desired_default}:
                actions.append({
                    "kind": "set_default",
                    "asset_id": asset["id"],
                    "asset_key": asset_key,
                    "old": sorted(current_defaults),
                    "new": desired_default,
                })

        for option in config["options"]:
            audio_key = option["audio_key"]
            existing = options.get(audio_key)
            if existing is not None and existing["asset_id"] != asset["id"]:
                raise ValueError(
                    "audio_key already belongs to another asset: "
                    f"{audio_key}"
                )

            desired_values = {
                "audio_url": option["audio_url"],
                "is_default": int(option["is_default"]),
                "sort_order": option["sort_order"],
            }
            if existing is None:
                actions.append({
                    "kind": "insert_option",
                    "asset_id": asset["id"],
                    "asset_key": asset_key,
                    "audio_key": audio_key,
                    **desired_values,
                })
                option_id = None
            else:
                changed = {
                    field: (existing[field], value)
                    for field, value in desired_values.items()
                    if existing[field] != value
                }
                if changed:
                    actions.append({
                        "kind": "update_option",
                        "option_id": existing["id"],
                        "asset_key": asset_key,
                        "audio_key": audio_key,
                        "changes": changed,
                        **desired_values,
                    })
                option_id = existing["id"]

            for content in option.get("contents", []):
                language = content["language"]
                name = content["name"]
                old_name = (
                    translations.get((option_id, language))
                    if option_id is not None
                    else None
                )
                if old_name != name:
                    actions.append({
                        "kind": "upsert_translation",
                        "audio_key": audio_key,
                        "language": language,
                        "old": old_name,
                        "new": name,
                    })

    return actions


def _create_backup(connect: sqlite3.Connection) -> Path:
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"puzzle_audiobook_before_audio_{timestamp}.db"
    with sqlite3.connect(backup_path) as backup:
        connect.backup(backup)
    return backup_path


def apply_plan(connect: sqlite3.Connection, actions: list[dict]) -> None:
    connect.execute("BEGIN IMMEDIATE")
    try:
        # Clear old defaults before inserting/updating new defaults so the
        # database's one-default-per-asset unique index is never violated.
        for action in actions:
            if action["kind"] == "set_default":
                connect.execute(
                    "UPDATE asset_audio_options SET is_default = 0 WHERE asset_id = ?",
                    (action["asset_id"],),
                )

        for action in actions:
            kind = action["kind"]
            if kind == "update_asset_default_url":
                connect.execute(
                    "UPDATE assets SET audio_url = ? WHERE id = ?",
                    (action["new"], action["asset_id"]),
                )
            elif kind == "insert_option":
                connect.execute(
                    """
                    INSERT INTO asset_audio_options (
                        asset_id, audio_key, audio_url, is_default, sort_order
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        action["asset_id"],
                        action["audio_key"],
                        action["audio_url"],
                        action["is_default"],
                        action["sort_order"],
                    ),
                )
            elif kind == "update_option":
                connect.execute(
                    """
                    UPDATE asset_audio_options
                    SET audio_url = ?, is_default = ?, sort_order = ?
                    WHERE id = ?
                    """,
                    (
                        action["audio_url"],
                        action["is_default"],
                        action["sort_order"],
                        action["option_id"],
                    ),
                )
            elif kind == "upsert_translation":
                option_row = connect.execute(
                    "SELECT id FROM asset_audio_options WHERE audio_key = ?",
                    (action["audio_key"],),
                ).fetchone()
                if option_row is None:
                    raise RuntimeError(
                        f"Audio option was not created: {action['audio_key']}"
                    )
                connect.execute(
                    """
                    INSERT INTO asset_audio_option_translations (
                        audio_option_id, language, name
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(audio_option_id, language)
                    DO UPDATE SET name = excluded.name
                    """,
                    (option_row["id"], action["language"], action["new"]),
                )
        connect.commit()
    except Exception:
        connect.rollback()
        raise


def _print_plan(actions: list[dict]) -> None:
    if not actions:
        print("No audio changes are required.")
        return
    counts = Counter(action["kind"] for action in actions)
    print("Planned audio changes:")
    for kind, count in sorted(counts.items()):
        print(f"- {kind}: {count}")
    print("\nDetails:")
    for action in actions:
        print(f"- {action}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or apply asset audio seed-data changes safely."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create a backup and write the displayed changes.",
    )
    args = parser.parse_args()

    if not DB_DIR.is_file():
        raise FileNotFoundError(f"Database does not exist: {DB_DIR}")

    connect = create_connection(DB_DIR)
    try:
        actions = build_plan(connect)
        _print_plan(actions)
        if not args.apply:
            print("\nPreview only. Run again with --apply to write changes.")
            return
        if not actions:
            return
        backup_path = _create_backup(connect)
        print(f"\nBackup created: {backup_path}")
        apply_plan(connect, actions)
        print("Audio synchronization completed.")
    finally:
        connect.close()


if __name__ == "__main__":
    main()
