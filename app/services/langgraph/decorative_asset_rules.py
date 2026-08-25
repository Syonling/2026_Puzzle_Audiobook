"""Placement rules for symbols that must stay visually attached to a subject."""

from typing import Literal, TypedDict

PlacementRole = Literal[
    "independent",
    "above_head",
    "upper_left",
    "upper_right",
    "beside",
]


class DecorativeAssetRule(TypedDict):
    anchor: str
    default_placement: PlacementRole
    relative_scale: float


DECORATIVE_ASSET_RULES: dict[str, DecorativeAssetRule] = {
    "question_mark": {
        "anchor": "character",
        "default_placement": "above_head",
        "relative_scale": 0.4,
    },
    "exclamation_mark": {
        "anchor": "character",
        "default_placement": "above_head",
        "relative_scale": 0.4,
    },
    "sweat_drop": {
        "anchor": "character",
        "default_placement": "upper_right",
        "relative_scale": 0.3,
    },
    "heart": {
        "anchor": "character",
        "default_placement": "upper_right",
        "relative_scale": 0.35,
    },
    "music_note": {
        "anchor": "sound_source",
        "default_placement": "upper_right",
        "relative_scale": 0.35,
    },
    "speech_bubble": {
        "anchor": "character",
        "default_placement": "upper_right",
        "relative_scale": 0.55,
    },
    "thought_bubble": {
        "anchor": "character",
        "default_placement": "upper_right",
        "relative_scale": 0.55,
    },
}


def available_decorative_rules(
    available_icon_keys: set[str],
) -> dict[str, DecorativeAssetRule]:
    """Only expose rules for decorative assets that exist in the database."""
    return {
        asset_key: rule
        for asset_key, rule in DECORATIVE_ASSET_RULES.items()
        if asset_key in available_icon_keys
    }
