import json
import asyncio
# from IPython.display import Image, display
from pydantic import BaseModel, Field, ConfigDict
from typing import TypedDict, NotRequired
from typing_extensions import Literal
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, SystemMessage

from app.services.langgraph.context_builder import llm, get_assets_list
from app.services.langgraph.prompts import ROUTER_PROMPT, canvas_design_prompt, sound_analysis_prompt
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
    reasoning: str = Field(..., description="Return a concise explanation of the icon_keys, background_key, spatial-depth suggestions, and suggested audio order in no more than ten sentences.", max_length=1000)


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
    reasoning: str = Field(..., description="Return a concise explanation of the objects, background_key, spatial-depth design, and main visual choices in no more than ten sentences.", max_length=2000)


# Augment the LLM with schema for structured output
router = llm.with_structured_output(Route)
sound_analyzer = llm.with_structured_output(SoundAnalysis)
canvas_designer = llm.with_structured_output(CanvasDesign)

# State 后端代码组织的格式，不会因为llm幻觉而改变
class AIInput(TypedDict):
    language: Literal["ja", "zh", "en"]
    question: str
    sentence: str
    canvas: dict[str, object]


class State(TypedDict):
    input: AIInput
    decision: NotRequired[Literal["suggestion", "generate"]]
    output: NotRequired[dict[str, object]]

# Nodes
async def llm_call_1(state: State):
    """Analyze sentence and return icon_keys, background_key, and reasoning."""
    icon_list, background_list, audio_icon_list = get_assets_list()
    # 创建set类型数据，集合查询通常比列表更快（1）自动去重（2）适合判断某个值是否存在
    allowed_icon_keys = set(icon_list)
    allowed_background_keys = set(background_list)


    analysis_input = {
        "language": state["input"]["language"],
        "question": state["input"]["question"],
        "sentence": state["input"]["sentence"],
        "current_canvas": state["input"]["canvas"],
        "available_icons": icon_list,
        "available_backgrounds": background_list,
        "available_audio_icons": audio_icon_list,
    }

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

    invalid_icon_keys = [
        icon_key
        for icon_key in result.icon_keys
        if icon_key not in allowed_icon_keys
    ]
    invalid_background_key = (
        result.background_key
        if (
            result.background_key is not None
            and result.background_key not in allowed_background_keys
        )
        else None
    )

    if invalid_icon_keys or invalid_background_key:
        raise ValueError(
            f"LLM returned invalid keys: {invalid_icon_keys, invalid_background_key}"
        )

    return {
        "output": {
            "icon_keys": list(dict.fromkeys(result.icon_keys)),
            "background_key": result.background_key,
            "reasoning": result.reasoning,
        }
    }


async def llm_call_2(state: State):
    """Generate objects, background_key, and reasoning for a complete canvas design."""
    icon_list, background_list, audio_icon_list = get_assets_list()
    allowed_icon_keys = set(icon_list)
    allowed_background_keys = set(background_list)
    allowed_audio_icon_keys = set(audio_icon_list)

    design_input = {
        "language": state["input"]["language"],
        "question": state["input"]["question"],
        "sentence": state["input"]["sentence"],
        "current_canvas": state["input"]["canvas"],
        "available_icons": icon_list,
        "available_backgrounds": background_list,
        "available_audio_icons": audio_icon_list,
        "canvas_rules": {
            "width": 1040,
            "height": 650,
            "base_object_size": 96,
            "min_scale": 0.35,
            "max_scale": 3,
            "max_objects": 12,
        },
    }

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
            and result.background_key not in allowed_background_keys
        )
        else None
    )

    invalid_audio_icon_keys = [
        obj.asset_key
        for obj in result.objects
        if (
            obj.start_offset_seconds is not None
            and obj.asset_key not in allowed_audio_icon_keys
        )
    ]

    if invalid_icon_keys or invalid_background_key or invalid_audio_icon_keys:
        raise ValueError(
            "LLM returned invalid asset keys: "
            f"icons={invalid_icon_keys}, "
            f"background={invalid_background_key}, "
            f"audio_icons={invalid_audio_icon_keys}"
        )

    canvas = result.model_dump()
    for obj in canvas["objects"]:
        half_size = 48 * obj["scale"]
        obj["x"] = round(
            min(max(obj["x"], half_size), 1040 - half_size),
            1,
        )
        obj["y"] = round(
            min(max(obj["y"], half_size), 650 - half_size),
            1,
        )

    return {
        "output": canvas
        
    }


async def llm_call_router(state: State):
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


async def main():
    state = await router_workflow.ainvoke({
        "input": {
            "language": "zh",
            "question": "帮我重新设计这个画面",
            "sentence": "小鸟轻轻唱着歌，清亮的声音随着微风飘荡。渐渐地，天空染上了朦胧的灰色，一滴、两滴细雨悄然落下。歌声没有停歇，反而与细碎的雨声交织在一起，像是一首只属于这个温柔时刻的歌。",
            "canvas": {
                "objects": [    {
                    "asset_key": "bird",
                    "x": 430,
                    "y": 405,
                    "scale": 1.55,
                    "rotation": 0
                    }],
                "background_key": None,
            },
        }
    })

    # print(state)
    print(state["decision"])
    print(state["output"])


if __name__ == "__main__":
    asyncio.run(main())
