from app.seed_data.assets import ASSETS
from app.seed_data.questions import QUESTIONS
from app.seed_data.stories import STORIES


def seed_database(connect) -> None:
    for story in STORIES:
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

            for step_order, sentence in enumerate(content["steps"], start=1):
                connect.execute("""
                    insert or ignore into story_steps(
                                story_id,
                                step_order
                                )
                    values (?,?)
                """,
                (
                    story_row["id"],
                    step_order,
                )
                )
                story_step_id = connect.execute("select id from story_steps where story_id = ? and step_order = ?",(story_row["id"], step_order)).fetchone()
                connect.execute("""
                    insert or ignore into story_step_translations(
                                story_step_id,
                                language,
                                sentence)
                    values (?,?,?)
                """,
                (
                    story_step_id["id"],
                    content["language"],
                    sentence
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
