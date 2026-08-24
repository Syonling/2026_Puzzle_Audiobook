from typing import Literal


Language = Literal["zh", "ja", "en"]


LANGUAGE_NAMES = {
    "zh": "Simplified Chinese",
    "ja": "Japanese",
    "en": "English",
}


ROUTER_PROMPT = """
1. Classify question into exactly one step: suggestion or generate.
2. Return suggestion when question asks for advice, explanation, evaluation, recommended icon_keys, or a recommended background_key without directly modifying current_canvas.
3. Return generate only when question explicitly asks to generate, create, design, arrange, replace, or modify current_canvas.
4. Return suggestion when the intent of question is ambiguous.
"""


def language_instruction(language: Language) -> str:
    # 从 LANGUAGE_NAMES 字典里根据 language 找对应值；如果找不到，就使用中文对应的值作为默认值。
    language_name = LANGUAGE_NAMES.get(
        language,
        LANGUAGE_NAMES["zh"],
    )

    return (
        "Language requirements:\n"
        f"- Write all user-facing natural-language text in {language_name}.\n"
        "- Keep internal identifiers such as icon_keys, asset_key, and background_key exactly unchanged."
    )


def sound_analysis_prompt(language: Language) -> str:
    return (
        "Task:\n"
        "Analyze question, sentence, current_canvas, and current_audio as a static collage project, then recommend additions, removals, replacements, background changes, spatial improvements, or audio changes when useful.\n"
        "\n"
        "Story-grounding rules:\n"
        "- Treat sentence as the primary source of truth and treat current_canvas only as the user's current draft; an object is not correct merely because it already exists on current_canvas.\n"
        "- First identify the characters, objects, environment, relationships, and explicit quantities required by sentence, then compare those requirements with current_canvas.\n"
        "- Check explicit quantities carefully: if sentence requires two cows and current_canvas contains one cow, recommend adding one more cow even though the cow asset_key is already present.\n"
        "- Existing use of an asset_key does not prohibit recommending the same asset_key again when another instance is needed to satisfy an explicit quantity or story relationship.\n"
        "- If current_canvas contains an object unsupported by sentence or question, identify it as unrelated in reasoning and recommend removing or replacing it; do not praise, retain, or create audio advice for it merely because it is already present.\n"
        "- Preserve an extra object only when it reasonably supports the setting or the user explicitly asks to keep it, and explain that judgment briefly.\n"
        "\n"
        "Structured-output rules:\n"
        "- Treat icon_keys and background_key only as recommendations; never return a redesigned canvas or numeric layout fields.\n"
        "- Each item in available_icons contains an asset_key and its audio_options; return zero or more icon_keys selected only from those asset_key values.\n"
        "- Icon_keys represent asset types to add, while reasoning must state the number of additional instances needed when quantity matters.\n"
        "- Each item in available_backgrounds contains background_key, scene_description, and has_audio; use scene_description to select a setting that actually matches sentence.\n"
        "- Return background_key as either null or exactly one supplied background_key, and return null when current_canvas already has a suitable background unless replacement is needed.\n"
        "- Never place a key from available_backgrounds in icon_keys, never use a key from available_icons as background_key, and never invent, translate, rewrite, or modify any key.\n"
        "- Return an empty icon_keys list only when no story-relevant icon needs to be added, and return null for background_key when no additional or replacement background is useful.\n"
        "\n"
        "Composition rules:\n"
        "- Infer foreground, middle-ground, background, relative size, and placement from explicit or implicit spatial cues such as nearby, at one's feet, across the river, beyond the mountain, or in the distance.\n"
        "- Treat the collage as a static composition and never suggest animation, object movement, performed actions, or visual changes over time.\n"
        "\n"
        "Audio suggestion rules:\n"
        "- Return audio_suggestions only when audio would materially improve the story experience; do not create an entry merely because an icon has audio_options.\n"
        "- Every audio_suggestions[*].asset_key must be a story-relevant retained or recommended icon, and selected_audio_key must belong to that icon's supplied audio_options.\n"
        "- Use current_audio to avoid recommending the same audio choice, timing, or effect when it is already configured appropriately.\n"
        "- Copy audio_name exactly from the selected option's supplied name; never invent or translate an audio name.\n"
        "- If option names do not clearly distinguish their sound, select the option marked is_default instead of guessing.\n"
        "- Use start_offset_seconds only to suggest sound order, and select at most two effect_keys only from available_audio_effects when an effect has a clear purpose.\n"
        "- Do not apply effects by habit; prefer no effect, avoid echo or reverb for ordinary close sounds, and never describe non-audio actions in reasoning.\n"
        "\n"
        "Reasoning requirements:\n"
        "- Return only actionable recommendations that tell the user what to add, remove, replace, resize, reposition, or configure.\n"
        "- Do not summarize all available assets, rejected candidates, absent assets, existing correct content, or checks that produced no recommended action.\n"
        "- Do not write statements such as no other icon is needed, an asset is available but not mentioned, no suitable audio exists, or no audio order is needed.\n"
        "- Mention selected audio, timing, and effects only when audio_suggestions is non-empty; do not list every candidate or repeat all checks.\n"
        "- When changes are needed, state the most important changes directly; when no change is needed at all, return only one brief sentence saying that current_canvas already satisfies sentence.\n"
        "- Keep reasoning within ten concise sentences, but prefer fewer sentences whenever the recommendation can be expressed clearly.\n"
        f"{language_instruction(language)}"
    )


def canvas_design_prompt(language: Language) -> str:
    return (
        "Task:\n"
        "Design a complete static collage and its useful audio arrangement from sentence and question, using current_canvas and current_audio as editable drafts rather than evidence that existing content is correct.\n"
        "\n"
        "Story and quantity rules:\n"
        "- Treat sentence as the primary source of truth and include the characters, objects, environment, and relationships needed to represent it clearly.\n"
        "- Respect explicit quantities by returning multiple objects with the same asset_key when needed; for example, a sentence containing two cows should produce two cow objects.\n"
        "- Do not retain an existing object merely because it appears in current_canvas; remove objects unsupported by sentence or question unless they reasonably support the setting or the user explicitly asks to keep them.\n"
        "\n"
        "Asset and canvas rules:\n"
        "- Each item in available_icons contains an asset_key and its audio_options; return every objects[*].asset_key only from those asset_key values.\n"
        "- Each item in available_backgrounds contains background_key, scene_description, and has_audio; select at most one supplied background_key by matching its scene_description to sentence.\n"
        "- Never place a key from available_backgrounds in objects, never use a key from available_icons as background_key, and never invent, translate, rewrite, or modify any key.\n"
        "- Follow canvas_rules exactly, keep every object fully visible, avoid excessive overlap, and respect max_objects.\n"
        "- Infer spatial depth creatively from explicit and implicit cues such as nearby, at one's feet, across the river, beyond the mountain, or in the distance, and express it through coherent x, y, and scale relationships rather than a rigid template.\n"
        "\n"
        "Icon audio rules:\n"
        "- For each object with useful audio, return selected_audio_key as one exact audio_key belonging to that object's asset_key; otherwise return null.\n"
        "- If option names do not clearly distinguish their sound, select the option marked is_default instead of guessing.\n"
        "- Return start_offset_seconds between 0 and 60 only when selected_audio_key is not null, and use offsets to express sound order without implying animation.\n"
        "- Return at most two effect_keys selected only from available_audio_effects, and use an empty list when no effect has a clear purpose.\n"
        "- Prefer no effect, avoid echo or reverb for ordinary close sounds, and do not use effects merely to make the result look more elaborate.\n"
        "\n"
        "Background audio rules:\n"
        "- Set background_audio_enabled to true only when the chosen background has has_audio=true and its environment sound helps the requested scene.\n"
        "- When background_audio_enabled is true, return a useful background_start_offset_seconds and at most two background_effect_keys; otherwise return null and an empty list.\n"
        "- Background audio supports only its existing single sound; never invent a background audio key or treat it as an icon audio option.\n"
        "\n"
        "Reasoning requirements:\n"
        "- Return only the most important design decisions, including necessary quantity corrections, removals, replacements, depth choices, and useful audio choices.\n"
        "- Do not summarize available assets, rejected candidates, missing audio, unchanged correct content, or checks that require no action.\n"
        "- Mention selected audio, timing, and effects only when they are actually returned; do not list every candidate or repeat all checks.\n"
        "- Keep reasoning within ten concise sentences, but prefer fewer sentences whenever the design can be explained clearly.\n"
        f"{language_instruction(language)}"
    )
