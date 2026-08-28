from app.seed_data.assets import ASSETS
from app.seed_data.questions import QUESTIONS
from app.seed_data.stories import STORIES


def _normalize_story_step(step: str | dict, step_type: str) -> dict:
    """Keep old string steps compatible while supporting narration metadata."""
    if isinstance(step, str):
        return {
            "sentence": step,
            "audio_url": None,
            "step_type": step_type,
        }
    return {
        "sentence": step["sentence"],
        "audio_url": step.get("audio_url"),
        "step_type": step_type,
    }


def _validate_story_steps() -> None:
    for story in STORIES:
        free_creation_orders = set(
            story.get("free_creation_step_orders", [])
        )
        available_step_orders = {
            step_order
            for content in story["contents"]
            for step_order, _ in enumerate(content["steps"], start=1)
        }
        invalid_free_creation_orders = (
            free_creation_orders - available_step_orders
        )
        if invalid_free_creation_orders:
            raise ValueError(
                "Free-creation step does not exist: "
                f"story={story['slug']}, "
                f"steps={sorted(invalid_free_creation_orders)}"
            )
        for content in story["contents"]:
            for step_order, raw_step in enumerate(content["steps"], start=1):
                step_type = (
                    "free_creation"
                    if step_order in free_creation_orders
                    else "story"
                )
                step = _normalize_story_step(raw_step, step_type)
                if step["step_type"] not in {"story", "free_creation"}:
                    raise ValueError(
                        "Invalid story step type: "
                        f"story={story['slug']}, step={step_order}"
                    )
                if step["step_type"] == "free_creation" and step["audio_url"]:
                    raise ValueError(
                        "Free-creation step cannot have narration audio: "
                        f"story={story['slug']}, step={step_order}"
                    )
                if (
                    content["language"] == "zh"
                    and step["step_type"] == "story"
                    and not step["audio_url"]
                ):
                    raise ValueError(
                        "Chinese story step is missing narration audio: "
                        f"story={story['slug']}, step={step_order}"
                    )


def _get_asset_audio_options(asset: dict) -> list[dict]:
    """读取音频选项；兼容尚未带 audio_options 的旧版生成数据。"""
    if "audio_options" in asset:
        return asset["audio_options"]

    if asset["category"] == "background" or not asset.get("audio_url"):
        return []

    return [
        {
            "audio_key": f"{asset['asset_key']}_default",
            "audio_url": asset["audio_url"],
            "is_default": True,
            "sort_order": 0,
            "contents": [],
        }
    ]


def _validate_asset_audio_options() -> None:
    """在写入数据库前检查 icon 和 background 的音频种子数据。"""
    used_audio_keys = set()

    for asset in ASSETS:
        audio_options = _get_asset_audio_options(asset)
        default_options = [
            option
            for option in audio_options
            if option["is_default"]
        ]

        if len(default_options) > 1:
            raise ValueError(
                f"Asset {asset['asset_key']} has more than one default audio"
            )

        if asset.get("audio_url"):
            if not default_options:
                raise ValueError(
                    f"Asset {asset['asset_key']} is missing its default audio option"
                )
            if default_options[0]["audio_url"] != asset["audio_url"]:
                raise ValueError(
                    f"Asset {asset['asset_key']} has inconsistent default audio_url"
                )
        elif default_options:
            raise ValueError(
                f"Asset {asset['asset_key']} has a default audio option "
                "but no default audio_url"
            )

        sort_orders = set()
        for option in audio_options:
            audio_key = option["audio_key"]
            if not audio_key:
                raise ValueError(
                    f"Asset {asset['asset_key']} has an empty audio_key"
                )
            if audio_key in used_audio_keys:
                raise ValueError(f"Duplicate audio_key: {audio_key}")
            used_audio_keys.add(audio_key)

            sort_order = option["sort_order"]
            if sort_order in sort_orders:
                raise ValueError(
                    f"Asset {asset['asset_key']} has duplicate audio sort_order"
                )
            sort_orders.add(sort_order)

            contents = option.get("contents", [])
            names_by_language = {
                content.get("language"): content.get("name")
                for content in contents
            }
            if set(names_by_language) != {"zh", "ja", "en"}:
                raise ValueError(
                    f"Audio option {audio_key} must have exactly zh, ja, en names"
                )
            if any(not name or not name.strip() for name in names_by_language.values()):
                raise ValueError(
                    f"Audio option {audio_key} has an empty translated name"
                )


def seed_database(connect) -> None:
    _validate_story_steps()
    _validate_asset_audio_options()

    for story in STORIES:
        free_creation_orders = set(
            story.get("free_creation_step_orders", [])
        )
        connect.execute("""
            insert or ignore into stories (
                        slug,
                        thumbnail_url)
            values (?,?)
        """,
        (
            story["slug"],
            story["thumbnail_url"]
         )
        )

        story_row = connect.execute("select id from stories where slug = ?",(story["slug"],)).fetchone()
        
        for content in story["contents"]:
            connect.execute("""
                insert or ignore into story_translations(
                            story_id,
                            language,
                            title,
                            description)
                values (?,?,?,?)
            """,
            (
                story_row["id"],
                content["language"],
                content["title"],
                content["description"]
            ))

            for step_order, raw_step in enumerate(content["steps"], start=1):
                step_type = (
                    "free_creation"
                    if step_order in free_creation_orders
                    else "story"
                )
                step = _normalize_story_step(raw_step, step_type)
                connect.execute("""
                    insert into story_steps(
                                story_id,
                                step_order,
                                step_type
                                )
                    values (?,?,?)
                    on conflict(story_id, step_order)
                    do update set step_type = excluded.step_type
                """,
                (
                    story_row["id"],
                    step_order,
                    step["step_type"],
                )
                )
                story_step_id = connect.execute("select id from story_steps where story_id = ? and step_order = ?",(story_row["id"], step_order)).fetchone()
                connect.execute("""
                    insert into story_step_translations(
                                story_step_id,
                                language,
                                sentence,
                                audio_url)
                    values (?,?,?,?)
                    on conflict(story_step_id, language)
                    do update set
                        sentence = excluded.sentence,
                        audio_url = excluded.audio_url
                """,
                (
                    story_step_id["id"],
                    content["language"],
                    step["sentence"],
                    step["audio_url"],
                )
                )

    for asset in ASSETS:
        connect.execute("""
                insert or ignore into assets(
                        asset_key,
                        category,
                        image_url,
                        audio_url
                        )
                values (?,?,?,?)       
        """,
        (
            asset["asset_key"],
            asset["category"],
            asset["image_url"],
            asset["audio_url"]
        )
        )

        asset_id = connect.execute("select id from assets where asset_key = ?",(asset["asset_key"],)).fetchone()

        for content in asset["contents"]:
            connect.execute("""
                insert or ignore into assets_translations(
                        asset_id,
                        language,
                        name,
                        category_translation
                        )
                values (?,?,?,?)
        """,
        (
            asset_id["id"],
            content["language"],
            content["name"],
            content["category_translation"]
        )
        )

        # 先取消数据库中这个素材的旧默认标记，再按当前种子数据设置默认项。
        # 从种子文件移除的旧备选音频不会被删除。
        connect.execute(
            """
            UPDATE asset_audio_options
            SET is_default = 0
            WHERE asset_id = ?
            """,
            (asset_id["id"],),
        )

        for option in _get_asset_audio_options(asset):
            connect.execute(
                """
                INSERT INTO asset_audio_options (
                    asset_id,
                    audio_key,
                    audio_url,
                    is_default,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(audio_key)
                DO UPDATE SET
                    asset_id = excluded.asset_id,
                    audio_url = excluded.audio_url,
                    is_default = excluded.is_default,
                    sort_order = excluded.sort_order
                """,
                (
                    asset_id["id"],
                    option["audio_key"],
                    option["audio_url"],
                    int(option["is_default"]),
                    option["sort_order"],
                ),
            )

            audio_option_id = connect.execute(
                """
                SELECT id
                FROM asset_audio_options
                WHERE audio_key = ?
                """,
                (option["audio_key"],),
            ).fetchone()

            for content in option.get("contents", []):
                connect.execute(
                    """
                    INSERT INTO asset_audio_option_translations (
                        audio_option_id,
                        language,
                        name
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(audio_option_id, language)
                    DO UPDATE SET name = excluded.name
                    """,
                    (
                        audio_option_id["id"],
                        content["language"],
                        content["name"],
                    ),
                )
            
    for question in QUESTIONS:
        connect.execute("""
                insert or ignore into questions(
                        question_key
                        )
                values (?)
        """,
        (
            question["question_key"],
        )
        )
        question_id = connect.execute("select id from questions where question_key = ?",(question["question_key"],)).fetchone()
        
        for content in question["contents"]:
            connect.execute("""
                insert or ignore into question_translations(
                        question_id,
                        language,
                        question
                        )
                values (?,?,?)
        """,
        (
            question_id["id"],
            content["language"],
            content["question"]
        )
        )
