import json
import asyncio
import argparse
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
from app.services.langgraph.prompts import ROUTER_PROMPT, canvas_design_prompt, sound_analysis_prompt

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
            "Return optional audio choices only for story-relevant icon assets."
        ),
    )
    reasoning: str = Field(..., description="Return a concise explanation of the icon_keys, background_key, spatial-depth suggestions, and suggested audio order in no more than ten sentences.", max_length=1000)


class AudioSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_key: str = Field(
        description="Return one exact asset_key from available_icons."
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
        max_length=2,
        description="Return at most two exact keys from available_audio_effects.",
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
            "exists in available_audio_icons, otherwise return null."
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
        max_length=2,
        description=(
            "Return at most two exact effect keys, and return an empty list "
            "when selected_audio_key is null."
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
    background_start_offset_seconds: float | None = Field(
        default=None,
        ge=0,
        le=60,
    )
    background_effect_keys: list[AudioEffectKey] = Field(
        default_factory=list,
        max_length=2,
    )
    reasoning: str = Field(..., description="Return a concise explanation of the objects, background_key, spatial-depth design, and main visual choices in no more than ten sentences.", max_length=2000)


# Augment the LLM with schema for structured output
router = llm.with_structured_output(Route)
sound_analyzer = llm.with_structured_output(SoundAnalysis)
canvas_designer = llm.with_structured_output(CanvasDesign)

# State 后端代码组织的格式，不会因为llm幻觉而改变
class AIInput(TypedDict):
    language: Literal["ja", "zh", "en"]
    question: str
    story_context: "StoryContext"
    canvas: dict[str, object]
    audio: NotRequired[dict[str, object]]


class StoryStepContext(TypedDict):
    step_order: int
    sentence: str


class StoryContext(TypedDict):
    previous_steps: list[StoryStepContext]
    current_step: StoryStepContext


class State(TypedDict):
    input: AIInput
    decision: NotRequired[Literal["suggestion", "generate"]]
    output: NotRequired[dict[str, object]]


def _asset_rules(asset_context):
    icon_keys = {
        item["asset_key"]
        for item in asset_context["icons"]
    }
    background_by_key = {
        item["background_key"]: item
        for item in asset_context["backgrounds"]
    }
    audio_by_asset = {
        item["asset_key"]: {
            option["audio_key"]: option
            for option in item["audio_options"]
        }
        for item in asset_context["icons"]
    }
    default_audio_by_asset = {
        item["asset_key"]: next(
            (
                option["audio_key"]
                for option in item["audio_options"]
                if option["is_default"]
            ),
            None,
        )
        for item in asset_context["icons"]
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
        if suggestion.asset_key not in allowed_icon_keys:
            raise ValueError(
                "LLM returned an audio suggestion for invalid icon: "
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
        "available_backgrounds": asset_context["backgrounds"],
        "available_audio_effects": asset_context["audio_effects"],
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

    background = (
        background_by_key.get(canvas["background_key"])
        if canvas["background_key"] is not None
        else None
    )
    if not background or not background["has_audio"]:
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
router_builder.add_edge("llm_call_2", END)

# Compile workflow
router_workflow = router_builder.compile()

# Show the workflow
# display(Image(router_workflow.get_graph().draw_mermaid_png()))


async def main(
    question: str,
    sentence: str,
    language: Literal["zh", "ja", "en"],
    canvas: dict[str, object],
    audio: dict[str, object],
):
    state = await router_workflow.ainvoke({
        "input": {
            "language": language,
            "question": question,
            "story_context": {
                "previous_steps": [],
                "current_step": {
                    "step_order": 1,
                    "sentence": sentence,
                },
            },
            "canvas": canvas,
            "audio": audio,
        }
    })

    # print(state)
    print(state["decision"])
    print(state["output"])


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
        default="还需要添加什么？",
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
        "--canvas-json",
        default='{"objects": [], "background_key": null}',
    )
    parser.add_argument(
        "--audio-json",
        default='{"tracks": []}',
    )
    arguments = parser.parse_args()
    asyncio.run(
        main(
            question=arguments.question,
            sentence=arguments.sentence,
            language=arguments.language,
            canvas=json.loads(arguments.canvas_json),
            audio=json.loads(arguments.audio_json),
        )
    )
