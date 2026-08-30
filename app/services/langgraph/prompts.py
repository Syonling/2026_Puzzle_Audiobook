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
        "Analyze question, story_context, current_canvas, and current_audio as a static collage project, then recommend additions, removals, replacements, background changes, spatial improvements, or audio changes when useful.\n"
        "\n"
        "Story-context rules:\n"
        "- story_context.current_step is the primary source for deciding what belongs on the current canvas; current_canvas is only the user's editable draft.\n"
        "- story_context.previous_steps are contextual reference only; use them to resolve pronouns, recurring characters, locations, relationships, and continuity.\n"
        "- Do not add every character, object, place, or sound mentioned in previous_steps to the current canvas.\n"
        "- Include content from previous_steps only when it remains present, is required for continuity, or is referenced by current_step or question.\n"
        "- When previous_steps is empty, treat current_step as the beginning of the story and do not assume earlier events.\n"
        "- Read previous_steps in chronological order and preserve the most recently established time of day, weather, season, and overall lighting unless current_step explicitly changes them.\n"
        "- Missing time or weather information in current_step does not reset the scene to daytime, clear weather, or another default environment.\n"
        "- When current_step.step_type is free_creation, use previous_steps only as narrative setup and recommend an imaginative, story-consistent next development instead of repeating or reconstructing scenes that already happened.\n"
        "- For a free_creation step, prioritize the user's question when deciding the new development, while still using only available assets.\n"
        "- First identify the characters, objects, environment, relationships, and explicit quantities required by current_step, then compare those requirements with current_canvas.\n"
        "- Check explicit quantities carefully: if current_step requires two cows and current_canvas contains one cow, recommend adding one more cow even though the cow asset_key is already present.\n"
        "- Existing use of an asset_key does not prohibit recommending the same asset_key again when another instance is needed to satisfy an explicit quantity or story relationship.\n"
        "- If current_canvas contains an object unsupported by current_step, necessary continuity, or question, identify it as unrelated and recommend removing or replacing it.\n"
        "- Preserve an extra object only when it reasonably supports the setting or the user explicitly asks to keep it, and explain that judgment briefly.\n"
        "\n"
        "Structured-output rules:\n"
        "- Treat icon_keys and background_key only as recommendations; never return a redesigned canvas or numeric layout fields.\n"
        "- available_icons is the complete list of allowed visual asset keys; return zero or more icon_keys selected only from that list.\n"
        "- Icon_keys represent asset types to add, while reasoning must state the number of additional instances needed when quantity matters.\n"
        "- Each item in available_backgrounds contains background_key, scene_description, and has_audio; use scene_description to select a setting that matches current_step and necessary continuity.\n"
        "- An exact venue name match is not required; when no specialized background exists, recommend the closest adaptable background with a compatible viewpoint, interior or exterior structure, time of day, and overall environment.\n"
        "- Use icons to express venue-specific details such as a post office's desk, letters, parcels, or workers instead of rejecting an otherwise suitable generic interior background.\n"
        "- Return background_key as either null or exactly one supplied background_key, and return null when current_canvas already has a suitable background unless replacement is needed.\n"
        "- Never place a key from available_backgrounds in icon_keys, never use a key from available_icons as background_key, and never invent, translate, rewrite, or modify any key.\n"
        "- Return an empty icon_keys list only when no story-relevant icon needs to be added, and return null for background_key when no additional or replacement background is useful.\n"
        "\n"
        "Visual selection and composition rules:\n"
        "- Before recommending icon_keys, determine the effective background: use the recommended background when background_key is not null; otherwise use current_canvas.background_key when present. Find its scene_description in available_backgrounds and treat every clearly depicted scene element there as already visually present.\n"
        "- Do not recommend an icon merely to duplicate scenery or structural elements already depicted by the effective background, including houses, buildings, roads, fences, trees, mountains, shelves, windows, sea, or similar setting details. For example, a background whose scene_description says it contains a farmhouse or rows of houses already satisfies a non-specific request to show a house.\n"
        "- Recommend a separate icon matching a background element only when current_step or question clearly requires an independently manipulable foreground subject, a specific state or action, an explicit count beyond the background scenery, or a story interaction that cannot be represented by the background image alone. Briefly state that reason.\n"
        "- Background scenery is contextual and uncounted: do not treat decorative houses, trees, or other repeated scenery described in a background as story-object instances unless the text explicitly identifies them as such.\n"
        "- Select visual assets before considering audio, using the state, action, pose, direction, and quantity expressed by each asset_key.\n"
        "- Prefer the most specific matching asset_key over a generic variant; for flying seagulls, prefer seagulls_flying over seagull.\n"
        "- Never replace a visually accurate asset with a less accurate one because the latter has audio options.\n"
        "- Infer foreground, middle-ground, background, relative size, and placement from explicit or implicit spatial cues such as nearby, at one's feet, across the river, beyond the mountain, or in the distance.\n"
        "- Treat the collage as a static composition and never suggest animation, object movement, performed actions, or visual changes over time.\n"
        "\n"
        "Audio suggestion rules:\n"
        "- Only after visual icon_keys are finalized, consult available_audio_options; an icon without audio remains a valid visual choice.\n"
        "- Return audio_suggestions only when audio would materially improve the story experience.\n"
        "- Visual relevance does not imply audible relevance; select audio only for a physically present sound source whose sound is explicitly heard or strongly implied as occurring in the current scene.\n"
        "- An object shown only as a picture, pattern, symbol, sign, map, photograph, memory, thought, destination, or distant visual reference is not an active sound source; never assign it audio unless current_step explicitly states that its sound is heard.\n"
        "- Every audio_suggestions[*].asset_key must be a story-relevant retained or recommended icon or the relevant current/recommended background, and selected_audio_key must belong to available_audio_options for that asset_key.\n"
        "- Use current_audio to avoid recommending the same audio choice, timing, or effect when it is already configured appropriately.\n"
        "- Copy audio_name exactly from the selected option's supplied name; never invent or translate an audio name.\n"
        "- If option names do not clearly distinguish their sound, select the option marked is_default instead of guessing.\n"
        "- Use start_offset_seconds only to suggest sound order, and select at most three effect_keys only from available_audio_effects when each effect has a clear purpose.\n"
        "- Infer acoustic meaning from both explicit wording and implicit setting, distance, enclosure, direction, and change over time; the text does not need to name an effect directly.\n"
        "- Use echo for clearly repeated reflections suggested by a valley, canyon, cliff, cave, or wording such as echoing or calling back; use reverb for a blended spacious tail suggested by a large resonant space, distant sound, or strong sense of surrounding space.\n"
        "- Use fade_in when a sound gradually begins, approaches, or emerges, and fade_out when it recedes, weakens, or disappears.\n"
        "- Apply inferred effects only to the sound that carries the relevant spatial or temporal cue, not automatically to every sound in the same scene.\n"
        "- Do not apply effects by habit; prefer no effect for ordinary close sounds, and combine echo with reverb only when the description clearly supports both distinct repetition and a spacious tail.\n"
        "- Never describe non-audio actions in reasoning.\n"
        "\n"
        "Reasoning requirements:\n"
        "- Return only actionable recommendations that tell the user what to add, remove, replace, resize, reposition, or configure.\n"
        "- Do not summarize all available assets, rejected candidates, absent assets, existing correct content, or checks that produced no recommended action.\n"
        "- Do not write statements such as no other icon is needed, an asset is available but not mentioned, no suitable audio exists, or no audio order is needed.\n"
        "- Mention selected audio, relative playback order, and effects only when audio_suggestions is non-empty; do not list every candidate or repeat all checks.\n"
        "- Describe timing only as narrative order, such as first, afterward, when the related subject is introduced, or after the relevant narration; never include exact seconds or repeat start_offset_seconds in reasoning.\n"
        "- When changes are needed, state the most important changes directly; when no change is needed at all, return only one brief sentence saying that current_canvas already satisfies sentence.\n"
        "- Keep reasoning within ten concise sentences, but prefer fewer sentences whenever the recommendation can be expressed clearly.\n"
        f"{language_instruction(language)}"
    )


def canvas_design_prompt(language: Language) -> str:
    return (
        "Task:\n"
        "Design a complete static collage and its useful audio arrangement from question and story_context, using current_canvas and current_audio as editable drafts rather than evidence that existing content is correct.\n"
        "\n"
        "Story-context and quantity rules:\n"
        "- Treat story_context.current_step as the primary source for the current canvas.\n"
        "- Use story_context.previous_steps only to resolve pronouns, recurring characters, locations, relationships, and necessary continuity.\n"
        "- Do not copy every character, object, place, or sound from previous_steps into the current canvas.\n"
        "- Include earlier content only when it remains present, is required for continuity, or is referenced by current_step or question.\n"
        "- When previous_steps is empty, treat current_step as the beginning of the story and do not assume earlier events.\n"
        "- Read previous_steps in chronological order and preserve the most recently established time of day, weather, season, and overall lighting unless current_step explicitly changes them.\n"
        "- Missing time or weather information in current_step does not reset the scene to daytime, clear weather, or another default environment.\n"
        "- When current_step.step_type is free_creation, invent a plausible and imaginative next scene that develops the story beyond previous_steps; do not merely repeat, summarize, or reconstruct an earlier scene.\n"
        "- For a free_creation step, prioritize the user's question when choosing the new event, setting, characters, and mood, while keeping the continuation coherent with previous_steps and available assets.\n"
        "- Respect explicit quantities by returning multiple objects with the same asset_key when needed; for example, a current_step containing two cows should produce two cow objects.\n"
        "- Do not retain an existing object merely because it appears in current_canvas; remove objects unsupported by current_step, necessary continuity, or question.\n"
        "\n"
        "Asset and canvas rules:\n"
        "- available_icons is the complete list of allowed visual asset keys; return every objects[*].asset_key only from that list.\n"
        "- Each item in available_backgrounds contains background_key, scene_description, and has_audio; select at most one supplied background_key by matching its scene_description to current_step and necessary continuity.\n"
        "- An exact venue name match is not required; when no specialized background exists, choose the closest adaptable background with a compatible viewpoint, interior or exterior structure, time of day, and overall environment.\n"
        "- Use scene objects to convey venue-specific details such as a post office's desk, letters, parcels, or workers while the background supplies the compatible general space.\n"
        "- Select the background from the location where the current action takes place, not from a distant object, landmark, or destination merely mentioned in the story.\n"
        "- Distinguish interior and exterior scenes strictly; never select an interior background unless the current character is explicitly inside that place.\n"
        "- Reject backgrounds that contradict the current viewpoint or environment, especially interior versus exterior, land versus sea, and day versus night.\n"
        "- Never place a key from available_backgrounds in objects, never use a key from available_icons as background_key, and never invent, translate, rewrite, or modify any key.\n"
        "- Choose the background before finalizing objects. Read the chosen background's scene_description and treat every clearly depicted scene element as already visually present in the composition.\n"
        "- Do not add an object merely to duplicate scenery or structural elements already depicted by the chosen background, including houses, buildings, roads, fences, trees, mountains, shelves, windows, sea, or similar setting details. For example, a background whose scene_description contains a farmhouse or rows of houses already supplies a non-specific house mentioned by the story.\n"
        "- Add a separate object matching a background element only when current_step or question clearly requires an independently manipulable foreground subject, a specific state or action, an explicit count beyond the background scenery, or a story interaction that the static background cannot express.\n"
        "- Background scenery is contextual and uncounted: do not count decorative houses, trees, or other repeated scenery toward explicit story-object quantities unless current_step identifies them as distinct story subjects.\n"
        "- Follow canvas_rules exactly, keep every object fully visible, avoid excessive overlap, and respect max_objects.\n"
        "- Infer spatial depth creatively from explicit and implicit cues such as nearby, at one's feet, across the river, beyond the mountain, or in the distance, and express it through coherent x, y, and scale relationships rather than a rigid template.\n"
        "- Select all visual objects before considering audio, using the state, action, pose, direction, and quantity expressed by each asset_key.\n"
        "- Prefer the most specific matching asset_key over a generic variant; for flying seagulls, prefer seagulls_flying over seagull.\n"
        "- Never replace a visually accurate asset with a less accurate one because the latter has audio options.\n"
        "\n"
        "Semantic attachment rules:\n"
        "- decorative_asset_rules identifies symbols that cannot be treated as independent distant scene objects.\n"
        "- Every object whose asset_key appears in decorative_asset_rules must set anchor_object_index to the zero-based index of the non-decorative character or sound source it belongs to.\n"
        "- Never anchor a decorative object to itself or to another decorative object; omit the decorative object when no suitable subject exists.\n"
        "- Use above_head for question_mark and exclamation_mark unless another supplied placement better avoids overlap.\n"
        "- Place music_note close to and above the character or object producing the sound.\n"
        "- Place heart, sweat_drop, speech_bubble, and thought_bubble close to their relevant character, not in unrelated empty space.\n"
        "- Keep decorative symbols visually grouped with their anchor without covering the anchor's face or body.\n"
        "- Return anchor_object_index=null and placement_role=independent for every normal scene object.\n"
        "- Decorative coordinates and scale are approximate because the backend will replace them using the selected anchor and placement_role.\n"
        "\n"
        "Icon audio rules:\n"
        "- Only after every visual object is finalized, consult available_audio_options; an object without audio remains a valid visual choice.\n"
        "- Visual presence does not imply audible presence; select audio only for a physically present sound source whose sound is explicitly heard or strongly implied as occurring in the current scene.\n"
        "- An object represented only by a picture, pattern, symbol, sign, map, photograph, memory, thought, destination, or distant visual reference is not an active sound source; set selected_audio_key=null unless current_step explicitly states that its sound is heard.\n"
        "- For each object with useful audio, return selected_audio_key as one exact audio_key listed for that object's asset_key in available_audio_options; otherwise return null.\n"
        "- If option names do not clearly distinguish their sound, select the option marked is_default instead of guessing.\n"
        "- Return start_offset_seconds between 0 and 60 only when selected_audio_key is not null, and use offsets to express sound order without implying animation.\n"
        "- Return at most three effect_keys selected only from available_audio_effects, and use an empty list when no effect has a clear purpose.\n"
        "- Infer acoustic meaning from explicit wording and from implicit setting, distance, enclosure, direction, and change over time; the story does not need to name an effect directly.\n"
        "- Use echo for clearly repeated reflections suggested by a valley, canyon, cliff, cave, or wording such as echoing or calling back; use reverb for a blended spacious tail suggested by a large resonant space, distant sound, or strong sense of surrounding space.\n"
        "- Use fade_in when a sound gradually begins, approaches, or emerges, and fade_out when it recedes, weakens, or disappears.\n"
        "- Apply inferred effects only to the object whose sound carries the relevant cue, not automatically to every object in the same scene.\n"
        "- Prefer no effect for ordinary close sounds, do not add effects merely for complexity, and combine echo with reverb only when both distinct repetition and a spacious tail are clearly supported.\n"
        "\n"
        "Background audio rules:\n"
        "- Set background_audio_enabled to true only when the chosen background has has_audio=true and its environment sound helps the requested scene.\n"
        "- When background_audio_enabled is true, select selected_background_audio_key as one exact audio_key belonging to background_key in available_audio_options, and return a useful background_start_offset_seconds and at most three background_effect_keys.\n"
        "- Apply background effects only when the environmental sound itself carries the acoustic cue; a valley background does not require echo unless its selected background audio is meant to be heard as reflecting through that space.\n"
        "- When background audio is unnecessary or unavailable, return selected_background_audio_key=null, background_start_offset_seconds=null, and an empty background_effect_keys list.\n"
        "- Choose among background audio options by their supplied names and scene meaning; never invent, translate, or modify an audio_key.\n"
        "\n"
        "Reasoning requirements:\n"
        "- Return only the most important design decisions, including necessary quantity corrections, removals, replacements, depth choices, and useful audio choices.\n"
        "- Do not summarize available assets, rejected candidates, missing audio, unchanged correct content, or checks that require no action.\n"
        "- Mention selected audio, relative playback order, and effects only when they are actually returned; do not list every candidate or repeat all checks.\n"
        "- Describe timing only as narrative order, such as first, afterward, when the related subject is introduced, or after the relevant narration; never include exact seconds or repeat start_offset_seconds in reasoning because narration alignment may adjust the numeric values later.\n"
        "- Keep reasoning within ten concise sentences, but prefer fewer sentences whenever the design can be explained clearly.\n"
        f"{language_instruction(language)}"
    )


def audio_timing_prompt() -> str:
    return (
        "Task:\n"
        "Adjust only the playback start time of the supplied selected icon audio by comparing its intended order with the narration cues.\n"
        "\n"
        "Rules:\n"
        "- Return exactly one timing item for every supplied object_index, and never invent or omit an object_index.\n"
        "- Do not add, remove, replace, or reorder icons, audio choices, effects, backgrounds, or any other canvas data.\n"
        "- Narration cues only indicate when pieces of text are spoken; a cue does not imply that the described object, action, thought, dialogue, or environment produces or requires a sound effect.\n"
        "- Use cues only to position audio already selected in selected_audio, and never infer, add, or force a sound merely because a matching word or sentence appears in a cue.\n"
        "- Place a character or event sound near or shortly after the narration cue that introduces or describes it.\n"
        "- Ambient sounds may begin before their exact wording or near the beginning when that better supports the scene.\n"
        "- Avoid starting a prominent sound directly over an important spoken phrase when placing it shortly afterward is more natural.\n"
        "- Preserve the proposed relative sound order unless narration timing clearly supports a more accurate placement.\n"
        "- A narration cue is timing evidence only and must not change which sounds were selected.\n"
        "- Keep every start_offset_seconds between zero and narration.duration_seconds.\n"
    )
