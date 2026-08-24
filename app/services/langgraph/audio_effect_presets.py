"""The fixed audio effects currently supported by the frontend."""

from typing import Literal

AudioEffectKey = Literal["fade_in", "fade_out", "reverb", "echo"]

AUDIO_EFFECT_PRESETS: dict[AudioEffectKey, dict[str, float | bool]] = {
    "fade_in": {"enabled": True, "duration": 4.0},
    "fade_out": {"enabled": True, "duration": 4.0},
    "reverb": {"enabled": True, "wet": 0.62, "decay": 2.4},
    "echo": {"enabled": True, "wet": 0.38, "delay": 0.36, "feedback": 0.32},
}

AUDIO_EFFECT_DESCRIPTIONS: dict[AudioEffectKey, str] = {
    "fade_in": "make the sound begin gradually",
    "fade_out": "make the sound end gradually",
    "reverb": "add a spacious environmental tail",
    "echo": "add clearly repeated reflections",
}


def expand_audio_effects(
    effect_keys: list[AudioEffectKey],
) -> dict[str, dict[str, float | bool]]:
    """Convert validated effect keys into the frontend's fixed parameters."""
    return {
        effect_key: dict(AUDIO_EFFECT_PRESETS[effect_key])
        for effect_key in dict.fromkeys(effect_keys)
    }
