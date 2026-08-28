import json
import asyncio
import argparse
import copy
import logging
import time
# from IPython.display import Image, display
from pydantic import BaseModel, Field, ConfigDict
from typing import TypedDict, NotRequired
from typing_extensions import Literal
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, SystemMessage

from app.services.langgraph.audio_effect_presets import (
    AudioEffectKey,
    expand_audio_effects,
)
from app.services.langgraph.context_builder import llm, get_asset_context
from app.services.langgraph.decorative_asset_rules import (
    DECORATIVE_ASSET_RULES,
    PlacementRole,
    available_decorative_rules,
)
from app.services.langgraph.narration_timing import load_narration_timing
from app.services.langgraph.prompts import (
    ROUTER_PROMPT,
    audio_timing_prompt,
    canvas_design_prompt,
    sound_analysis_prompt,
)

logger = logging.getLogger(__name__)
# Schema for structured output to use as routing logic
# 定义llm的输出格式。强制按格式输出
class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: Literal["suggestion", "generate"] = Field(
        description=(
            "Return step as suggestion for advice, explanation, evaluation, or recommendations. "
            "Return step as generate only for an explicit request to create or modify current_canvas."
        )
    )

class SoundAnalysis(BaseModel):
    # 除了模型明确声明的字段，其他字段全部禁止。
    model_config = ConfigDict(extra="forbid")
    # 只能保证列表元素是字符串，不能保证字符串一定存在于数据库
    icon_keys: list[str] = Field(
        default_factory=list, # 表示默认创建空列表[]
        description=(
            "Return icon_keys as zero or more exact keys selected only from available_icons. "
            "Return an empty icon_keys list when no icon matches."
        ),
    )
    background_key: str | None  = Field(
        default= None,
        description=(
            "Return background_key as either null or exactly one exact key selected only from available_backgrounds. "
            "Return null when no background matches."
        ),
    )
    audio_suggestions: list["AudioSuggestion"] = Field(
        default_factory=list,
        max_length=12,
        description=(
            "Return optional audio choices for story-relevant icons or the "
            "relevant background."
        ),
    )
    reasoning: str = Field(..., description="Return a concise explanation of the icon_keys, background_key, spatial-depth suggestions, and suggested audio order in no more than ten sentences.", max_length=1000)


class AudioSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_key: str = Field(
        description=(
            "Return one exact key belonging to an icon or background that "
            "has options in available_audio_options."
        )
    )
    selected_audio_key: str = Field(
        description=(
            "Return one exact audio_key belonging to this asset_key."
        )
    )
    audio_name: str = Field(
        description=(
            "Return the exact supplied name for selected_audio_key."
        )
    )
    start_offset_seconds: float = Field(default=0, ge=0, le=60)
    effect_keys: list[AudioEffectKey] = Field(
        default_factory=list,
        max_length=3,
        description="Return at most three exact keys from available_audio_effects.",
    )


class CanvasObjectDesign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_key: str = Field(
        description="Return asset_key as one exact key selected only from available_icons."
    )
    x: float = Field(
        ge=48,
        le=992,
        description="Return x as the horizontal center coordinate of this object within the 1040-pixel canvas width.",
    )
    y: float = Field(
        ge=48,
        le=602,
        description="Return y as the vertical center coordinate of this object within the 650-pixel canvas height.",
    )
    scale: float = Field(
        ge=0.35,
        le=3,
        description="Return scale as the size multiplier applied to the 96-pixel base icon size.",
    )
    rotation: float = Field(
        ge=-180,
        le=180,
        description="Return rotation as the clockwise rotation angle in degrees.",
    )
    start_offset_seconds: float | None = Field(
        default=None,
        ge=0,
        le=60,
        description=(
            "Return start_offset_seconds between 0 and 60 only when asset_key "
            "has options in available_audio_options, otherwise return null."
        ),
    )
    selected_audio_key: str | None = Field(
        default=None,
        description=(
            "Return one exact audio_key belonging to asset_key, or null when "
            "the icon has no audio option."
        ),
    )
    effect_keys: list[AudioEffectKey] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "Return at most three exact effect keys, and return an empty list "
            "when selected_audio_key is null."
        ),
    )
    anchor_object_index: int | None = Field(
        default=None,
        ge=0,
        le=11,
        description=(
            "For a decorative asset, return the zero-based objects index of "
            "its non-decorative subject; otherwise return null."
        ),
    )
    placement_role: PlacementRole = Field(
        default="independent",
        description=(
            "Return independent for normal scene objects. For decorative "
            "assets, describe placement relative to anchor_object_index."
        ),
    )


class CanvasDesign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objects: list[CanvasObjectDesign] = Field(
        default_factory=list,
        max_length=12,
        description="Return objects as no more than 12 positioned icon objects whose asset_key values come only from available_icons.",
    )
    background_key: str | None  = Field(
        default= None,
        description=(
            "Return background_key as either null or exactly one exact key selected only from available_backgrounds. "
            "Return null when no background matches."
        ),
    )
    background_audio_enabled: bool = Field(
        default=False,
        description=(
            "Return true only when the selected background has audio and its "
            "environment sound is useful to this scene."
        ),
    )
    selected_background_audio_key: str | None = Field(
        default=None,
        description=(
            "When background audio is enabled, return one exact audio_key "
            "belonging to background_key; otherwise return null."
        ),
    )
    background_start_offset_seconds: float | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    background_effect_keys: list[AudioEffectKey] = Field(
        default_factory=list,
        max_length=3,
    )
    reasoning: str = Field(..., description="Return a concise explanation of the objects, background_key, spatial-depth design, and main visual choices in no more than ten sentences.", max_length=2000)


class AudioTimingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_index: int = Field(ge=0, le=11)
    start_offset_seconds: float = Field(ge=0)


class AudioTimingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timings: list[AudioTimingItem] = Field(
        default_factory=list,
        max_length=12,
    )


# Augment the LLM with schema for structured output
router = llm.with_structured_output(Route)
sound_analyzer = llm.with_structured_output(SoundAnalysis)
canvas_designer = llm.with_structured_output(CanvasDesign)
audio_timing_designer = llm.with_structured_output(AudioTimingResult)

# State 后端代码组织的格式，不会因为llm幻觉而改变
class AIInput(TypedDict):
    story_id: NotRequired[int]
    language: Literal["ja", "zh", "en"]
    question: str
    story_context: "StoryContext"
    canvas: dict[str, object]
    audio: NotRequired[dict[str, object]]
    # Only the standalone CLI uses this optional override. Normal API calls
    # read precomputed timing data from app/seed_data/narration_timings.
    narration_timing_override: NotRequired[dict[str, object]]


class StoryStepContext(TypedDict):
    step_order: int
    step_type: Literal["story", "free_creation"]
    sentence: str


class StoryContext(TypedDict):
    previous_steps: list[StoryStepContext]
    current_step: StoryStepContext


class State(TypedDict):
    input: AIInput
    decision: NotRequired[Literal["suggestion", "generate"]]
    output: NotRequired[dict[str, object]]


def _asset_rules(asset_context):
    icon_keys = set(asset_context["icons"])
    background_by_key = {
        item["background_key"]: item
        for item in asset_context["backgrounds"]
    }
    audio_by_asset = {
        asset_key: {
            option["audio_key"]: option
            for option in options
        }
        for asset_key, options
        in asset_context["audio_options_by_asset"].items()
    }
    default_audio_by_asset = {
        asset_key: next(
            (
                option["audio_key"]
                for option in options
                if option["is_default"]
            ),
            None,
        )
        for asset_key, options
        in asset_context["audio_options_by_asset"].items()
    }
    return (
        icon_keys,
        background_by_key,
        audio_by_asset,
        default_audio_by_asset,
    )


def _validated_audio_key(
    asset_key: str,
    selected_audio_key: str | None,
    audio_by_asset,
    default_audio_by_asset,
) -> str | None:
    available = audio_by_asset.get(asset_key, {})
    if selected_audio_key in available:
        return selected_audio_key
    return default_audio_by_asset.get(asset_key)


def _apply_decorative_layout(canvas: dict[str, object]) -> None:
    """Attach decorative symbols to valid subjects and replace LLM coordinates."""
    objects = canvas["objects"]
    positioned_objects = []
    kept_indices = []

    for object_index, obj in enumerate(objects):
        rule = DECORATIVE_ASSET_RULES.get(obj["asset_key"])
        if rule is None:
            kept_indices.append(object_index)
            continue
        anchor_index = obj["anchor_object_index"]
        if (
            anchor_index is not None
            and anchor_index != object_index
            and 0 <= anchor_index < len(objects)
            and objects[anchor_index]["asset_key"]
            not in DECORATIVE_ASSET_RULES
        ):
            kept_indices.append(object_index)

    output_index_by_original = {
        original_index: output_index
        for output_index, original_index in enumerate(kept_indices)
    }

    for object_index, obj in enumerate(objects):
        rule = DECORATIVE_ASSET_RULES.get(obj["asset_key"])
        if rule is None:
            obj["anchor_object_index"] = None
            obj["placement_role"] = "independent"
            positioned_objects.append(obj)
            continue

        anchor_index = obj["anchor_object_index"]
        anchor_is_valid = (
            anchor_index is not None
            and anchor_index != object_index
            and 0 <= anchor_index < len(objects)
            and objects[anchor_index]["asset_key"]
            not in DECORATIVE_ASSET_RULES
        )
        if not anchor_is_valid:
            logger.warning(
                "Dropping unanchored decorative asset | asset_key=%s | "
                "object_index=%s | anchor_object_index=%s",
                obj["asset_key"],
                object_index,
                anchor_index,
            )
            continue

        anchor = objects[anchor_index]
        obj["anchor_object_index"] = output_index_by_original[anchor_index]
        placement_role = obj["placement_role"]
        if placement_role == "independent":
            placement_role = rule["default_placement"]

        obj["placement_role"] = placement_role
        obj["scale"] = round(
            min(max(anchor["scale"] * rule["relative_scale"], 0.35), 0.9),
            2,
        )
        anchor_half_size = 48 * anchor["scale"]
        object_half_size = 48 * obj["scale"]
        gap = 12

        if placement_role == "above_head":
            x = anchor["x"] + anchor_half_size * 0.25
            y = anchor["y"] - anchor_half_size - object_half_size - gap
        elif placement_role == "upper_left":
            x = anchor["x"] - anchor_half_size * 0.75
            y = anchor["y"] - anchor_half_size * 0.75 - object_half_size
        elif placement_role == "beside":
            direction = -1 if anchor["x"] > 720 else 1
            x = anchor["x"] + direction * (
                anchor_half_size + object_half_size + gap
            )
            y = anchor["y"]
        else:
            x = anchor["x"] + anchor_half_size * 0.75
            y = anchor["y"] - anchor_half_size * 0.75 - object_half_size

        obj["x"] = round(
            min(max(x, object_half_size), 1040 - object_half_size),
            1,
        )
        obj["y"] = round(
            min(max(y, object_half_size), 650 - object_half_size),
            1,
        )
        positioned_objects.append(obj)

    canvas["objects"] = positioned_objects

# Nodes
async def llm_call_1(state: State):
    """Analyze sentence and return icon_keys, background_key, and reasoning."""
    language = state["input"].get("language", "zh")
    asset_context = get_asset_context(language)
    (
        allowed_icon_keys,
        background_by_key,
        audio_by_asset,
        default_audio_by_asset,
    ) = _asset_rules(asset_context)

    analysis_input = {
        "language": language,
        "question": state["input"]["question"],
        "story_context": state["input"]["story_context"],
        "current_canvas": state["input"]["canvas"],
        "current_audio": state["input"].get("audio", {}),
        "available_icons": asset_context["icons"],
        "available_audio_options": asset_context["audio_options_by_asset"],
        "available_backgrounds": asset_context["backgrounds"],
        "available_audio_effects": asset_context["audio_effects"],
    }

    started_at = time.perf_counter()
    result = await sound_analyzer.ainvoke(
        [
            SystemMessage(
                content=sound_analysis_prompt(analysis_input["language"])
            ),
            HumanMessage(
                content=json.dumps(
                    analysis_input,
                    ensure_ascii=False,
                )
            ),
        ]
    )
    logger.info(
        "LangGraph suggestion completed | icons=%d | audio_suggestions=%d | "
        "background=%s | elapsed_ms=%.1f",
        len(result.icon_keys),
        len(result.audio_suggestions),
        result.background_key,
        (time.perf_counter() - started_at) * 1000,
    )

    invalid_icon_keys = [
        icon_key
        for icon_key in result.icon_keys
        if icon_key not in allowed_icon_keys
    ]
    invalid_background_key = (
        result.background_key
        if (
            result.background_key is not None
            and result.background_key not in background_by_key
        )
        else None
    )

    if invalid_icon_keys or invalid_background_key:
        raise ValueError(
            f"LLM returned invalid keys: {invalid_icon_keys, invalid_background_key}"
        )

    audio_suggestions = []
    for suggestion in result.audio_suggestions:
        allowed_audio_asset_keys = allowed_icon_keys | set(background_by_key)
        if suggestion.asset_key not in allowed_audio_asset_keys:
            raise ValueError(
                "LLM returned an audio suggestion for invalid asset: "
                f"{suggestion.asset_key}"
            )
        audio_key = _validated_audio_key(
            suggestion.asset_key,
            suggestion.selected_audio_key,
            audio_by_asset,
            default_audio_by_asset,
        )
        if audio_key is None:
            continue
        option = audio_by_asset[suggestion.asset_key][audio_key]
        effect_keys = list(dict.fromkeys(suggestion.effect_keys))
        audio_suggestions.append(
            {
                "asset_key": suggestion.asset_key,
                "asset_type": (
                    "background"
                    if suggestion.asset_key in background_by_key
                    else "icon"
                ),
                "selected_audio_key": audio_key,
                "audio_name": option["name"],
                "start_offset_seconds": suggestion.start_offset_seconds,
                "effect_keys": effect_keys,
                "effects": expand_audio_effects(effect_keys),
            }
        )

    return {
        "output": {
            "icon_keys": list(dict.fromkeys(result.icon_keys)),
            "background_key": result.background_key,
            "audio_suggestions": audio_suggestions,
            "reasoning": result.reasoning,
        }
    }


async def llm_call_2(state: State):
    """Generate objects, background_key, and reasoning for a complete canvas design."""
    language = state["input"].get("language", "zh")
    asset_context = get_asset_context(language)
    (
        allowed_icon_keys,
        background_by_key,
        audio_by_asset,
        default_audio_by_asset,
    ) = _asset_rules(asset_context)

    design_input = {
        "language": language,
        "question": state["input"]["question"],
        "story_context": state["input"]["story_context"],
        "current_canvas": state["input"]["canvas"],
        "current_audio": state["input"].get("audio", {}),
        "available_icons": asset_context["icons"],
        "available_audio_options": asset_context["audio_options_by_asset"],
        "available_backgrounds": asset_context["backgrounds"],
        "available_audio_effects": asset_context["audio_effects"],
        "decorative_asset_rules": available_decorative_rules(
            allowed_icon_keys
        ),
        "canvas_rules": {
            "width": 1040,
            "height": 650,
            "base_object_size": 96,
            "min_scale": 0.35,
            "max_scale": 3,
            "max_objects": 12,
        },
    }

    started_at = time.perf_counter()
    result = await canvas_designer.ainvoke(
        [
            SystemMessage(
                content=canvas_design_prompt(design_input["language"])
            ),
            HumanMessage(
                content=json.dumps(
                    design_input,
                    ensure_ascii=False,
                )
            ),
        ]
    )
    logger.info(
        "LangGraph canvas generation completed | objects=%d | background=%s | "
        "background_audio=%s | elapsed_ms=%.1f",
        len(result.objects),
        result.background_key,
        result.background_audio_enabled,
        (time.perf_counter() - started_at) * 1000,
    )

    returned_icon_keys = [
        obj.asset_key
        for obj in result.objects
    ]

    invalid_icon_keys = [
        icon_key
        for icon_key in returned_icon_keys
        if icon_key not in allowed_icon_keys
    ]

    invalid_background_key = (
        result.background_key
        if (
            result.background_key is not None
            and result.background_key not in background_by_key
        )
        else None
    )

    if invalid_icon_keys or invalid_background_key:
        raise ValueError(
            "LLM returned invalid asset keys: "
            f"icons={invalid_icon_keys}, "
            f"background={invalid_background_key}"
        )

    canvas = result.model_dump()
    for obj in canvas["objects"]:
        audio_key = _validated_audio_key(
            obj["asset_key"],
            obj["selected_audio_key"],
            audio_by_asset,
            default_audio_by_asset,
        )
        obj["selected_audio_key"] = audio_key
        if audio_key is None:
            obj["start_offset_seconds"] = None
            obj["effect_keys"] = []
        effect_keys = list(dict.fromkeys(obj["effect_keys"]))
        obj["effect_keys"] = effect_keys
        obj["effects"] = expand_audio_effects(effect_keys)
        half_size = 48 * obj["scale"]
        obj["x"] = round(
            min(max(obj["x"], half_size), 1040 - half_size),
            1,
        )
        obj["y"] = round(
            min(max(obj["y"], half_size), 650 - half_size),
            1,
        )

    _apply_decorative_layout(canvas)

    background = (
        background_by_key.get(canvas["background_key"])
        if canvas["background_key"] is not None
        else None
    )
    selected_background_audio_key = None
    if background and canvas["background_audio_enabled"]:
        selected_background_audio_key = _validated_audio_key(
            canvas["background_key"],
            canvas["selected_background_audio_key"],
            audio_by_asset,
            default_audio_by_asset,
        )
    canvas["selected_background_audio_key"] = (
        selected_background_audio_key
    )

    if not background or selected_background_audio_key is None:
        canvas["background_audio_enabled"] = False
        canvas["background_start_offset_seconds"] = None
        canvas["background_effect_keys"] = []
    elif not canvas["background_audio_enabled"]:
        canvas["background_start_offset_seconds"] = None
        canvas["background_effect_keys"] = []
    background_effect_keys = list(
        dict.fromkeys(canvas["background_effect_keys"])
    )
    canvas["background_effect_keys"] = background_effect_keys
    canvas["background_effects"] = expand_audio_effects(
        background_effect_keys
    )

    return {
        "output": canvas
        
    }


async def audio_timing_node(state: State):
    """Optionally align selected icon audio with precomputed narration cues."""
    current_step = state["input"]["story_context"]["current_step"]
    if current_step["step_type"] == "free_creation":
        logger.info(
            "Narration timing skipped: free-creation step | step_order=%s",
            current_step["step_order"],
        )
        return {}

    story_id = state["input"].get("story_id")
    if story_id is None:
        logger.info("Narration timing skipped: story_id unavailable")
        return {}

    language = state["input"].get("language", "zh")
    narration = state["input"].get("narration_timing_override")
    if narration is None:
        narration = load_narration_timing(
            story_id,
            language,
            current_step["step_order"],
        )
    if narration is None:
        return {}

    output = state.get("output")
    objects = output.get("objects", []) if output else []
    selected_audio = [
        {
            "object_index": object_index,
            "asset_key": obj["asset_key"],
            "selected_audio_key": obj["selected_audio_key"],
            "proposed_start_seconds": obj.get("start_offset_seconds", 0),
        }
        for object_index, obj in enumerate(objects)
        if obj.get("selected_audio_key") is not None
    ]
    if not selected_audio:
        logger.info(
            "Narration timing skipped: no selected icon audio | "
            "story_id=%s | step_order=%s",
            story_id,
            current_step["step_order"],
        )
        return {}

    timing_input = {
        "selected_audio": selected_audio,
        "narration": narration,
    }
    started_at = time.perf_counter()
    try:
        result = await audio_timing_designer.ainvoke(
            [
                SystemMessage(content=audio_timing_prompt()),
                HumanMessage(
                    content=json.dumps(timing_input, ensure_ascii=False)
                ),
            ]
        )

        expected_indices = {
            item["object_index"]
            for item in selected_audio
        }
        returned_indices = [
            item.object_index
            for item in result.timings
        ]
        if (
            len(returned_indices) != len(expected_indices)
            or set(returned_indices) != expected_indices
            or len(set(returned_indices)) != len(returned_indices)
            or any(
                item.start_offset_seconds
                > narration["duration_seconds"]
                for item in result.timings
            )
        ):
            raise ValueError("invalid narration timing result")

        adjusted_output = copy.deepcopy(output)
        for item in result.timings:
            adjusted_output["objects"][item.object_index][
                "start_offset_seconds"
            ] = round(item.start_offset_seconds, 2)

        logger.info(
            "Narration timing aligned | story_id=%s | step_order=%s | "
            "audio_objects=%d | cues=%d | elapsed_ms=%.1f",
            story_id,
            current_step["step_order"],
            len(selected_audio),
            len(narration["cues"]),
            (time.perf_counter() - started_at) * 1000,
        )
        return {"output": adjusted_output}
    except Exception:
        logger.exception(
            "Narration timing failed; keeping original AI timing | "
            "story_id=%s | step_order=%s | elapsed_ms=%.1f",
            story_id,
            current_step["step_order"],
            (time.perf_counter() - started_at) * 1000,
        )
        return {}


async def llm_call_router(state: State):
    started_at = time.perf_counter()
    decision = await router.ainvoke(
        [
            SystemMessage(
                content=ROUTER_PROMPT
            ),
            HumanMessage(
                content=state["input"]["question"]
            ),
        ]
    )

    logger.info(
        "LangGraph intent routed | decision=%s | elapsed_ms=%.1f",
        decision.step,
        (time.perf_counter() - started_at) * 1000,
    )

    return {
        "decision": decision.step,
    }


# Conditional edge function to route to the appropriate node
def route_decision(state: State):
    # Return the node name you want to visit next
    if state["decision"] == "suggestion":
        return "llm_call_1"
    elif state["decision"] == "generate":
        return "llm_call_2"


# Build workflow
router_builder = StateGraph(State)

# Add nodes
router_builder.add_node("llm_call_1", llm_call_1)
router_builder.add_node("llm_call_2", llm_call_2)
router_builder.add_node("audio_timing_node", audio_timing_node)
router_builder.add_node("llm_call_router", llm_call_router)

# Add edges to connect nodes
router_builder.add_edge(START, "llm_call_router")
router_builder.add_conditional_edges(
    "llm_call_router",
    route_decision,
    {  # Name returned by route_decision : Name of next node to visit
        "llm_call_1": "llm_call_1",
        "llm_call_2": "llm_call_2",
    },
)
router_builder.add_edge("llm_call_1", END)
router_builder.add_edge("llm_call_2", "audio_timing_node")
router_builder.add_edge("audio_timing_node", END)

# Compile workflow
router_workflow = router_builder.compile()

# Show the workflow
# display(Image(router_workflow.get_graph().draw_mermaid_png()))


async def main(
    story_id: int,
    step_order: int,
    step_type: Literal["story", "free_creation"],
    question: str,
    sentence: str,
    language: Literal["zh", "ja", "en"],
    canvas: dict[str, object],
    audio: dict[str, object],
    narration_timing: dict[str, object] | None,
):
    workflow_input: AIInput = {
        "story_id": story_id,
        "language": language,
        "question": question,
        "story_context": {
            "previous_steps": [],
            "current_step": {
                "step_order": step_order,
                "step_type": step_type,
                "sentence": sentence,
            },
        },
        "canvas": canvas,
        "audio": audio,
    }
    if narration_timing is not None:
        workflow_input["narration_timing_override"] = narration_timing

    async for update in router_workflow.astream(
        {"input": workflow_input},
        stream_mode="updates",
    ):
        for node_name, node_update in update.items():
            if node_name == "llm_call_router":
                print("\n=== 1. Router decision ===")
                print((node_update or {}).get("decision"))
            elif node_name == "llm_call_2":
                print("\n=== 2. llm_call_2 output (before narration timing) ===")
                print(json.dumps(
                    (node_update or {}).get("output", {}),
                    ensure_ascii=False,
                    indent=2,
                ))
            elif node_name == "audio_timing_node":
                print("\n=== 3. audio_timing_node output ===")
                if node_update and node_update.get("output"):
                    print(json.dumps(
                        node_update["output"],
                        ensure_ascii=False,
                        indent=2,
                    ))
                else:
                    print("{}")
                    print("Timing adjustment was skipped; llm_call_2 output was preserved.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Run the puzzle LangGraph without starting FastAPI.",
    )
    parser.add_argument(
        "--question",
        default="请生成完整画布，并为小鸟选择合适的音频和播放时间。",
    )
    parser.add_argument(
        "--sentence",
        default="小鸟每天在树上歌唱。",
    )
    parser.add_argument(
        "--language",
        choices=("zh", "ja", "en"),
        default="zh",
    )
    parser.add_argument(
        "--story-id",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--step-order",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--step-type",
        choices=("story", "free_creation"),
        default="story",
    )
    parser.add_argument(
        "--canvas-json",
        default='{"objects": [], "background_key": null}',
    )
    parser.add_argument(
        "--audio-json",
        default='{"tracks": []}',
    )
    parser.add_argument(
        "--narration-json",
        default=(
            '{"duration_seconds": 12.0, "cues": ['
            '{"text": "小鸟", "start_seconds": 2.0, "end_seconds": 3.0}, '
            '{"text": "在树上歌唱", "start_seconds": 3.1, "end_seconds": 6.0}'
            ']}'
        ),
        help=(
            "CLI-only narration timing JSON. Pass 'null' to use the "
            "precomputed story timing file instead."
        ),
    )
    arguments = parser.parse_args()
    asyncio.run(
        main(
            story_id=arguments.story_id,
            step_order=arguments.step_order,
            step_type=arguments.step_type,
            question=arguments.question,
            sentence=arguments.sentence,
            language=arguments.language,
            canvas=json.loads(arguments.canvas_json),
            audio=json.loads(arguments.audio_json),
            narration_timing=json.loads(arguments.narration_json),
        )
    )
