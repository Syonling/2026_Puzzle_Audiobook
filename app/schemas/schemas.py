from pydantic import BaseModel, Field
from typing import Literal


# User
class UserCreate(BaseModel):
    username : str = Field(...,min_length=1,max_length=100)
    password : str = Field(...,min_length=1)

class UserFeedback(BaseModel):
    id : int
    username : str

# Stories
class StorySummary(BaseModel):
    id : int
    slug : str
    title : str
    description : str
    thumbnail_url : str | None

class StoryStepResponse(BaseModel):
    id : int
    story_id : int
    step_order : int
    step_type: Literal["story", "free_creation"]
    sentence : str
    audio_url: str | None

class StoryDetail(StorySummary):
    story_text: str
    steps: list[StoryStepResponse]

# Projects
class ProjectCreate(BaseModel):
    story_id: int
    story_step_id: int
    title: str = Field(
        default="未命名作品",
        min_length=1,
        max_length=100,
    )
    canvas: dict
    audio: dict

class ProjectResponse(BaseModel):
    id: int
    story_id: int
    title: str
    current_step: int
    created_at: str
    updated_at: str

class CanvasSaveRequest(BaseModel):
    canvas: dict
    audio: dict

class CanvasResponse(BaseModel):
    project_id: int
    story_step_id: int
    canvas: dict
    audio: dict

# AI
class AILanguage(BaseModel):
    x_language: Literal["ja", "zh", "en"]

class AIQuestion(BaseModel):
    question_id: int
    # x_language: Literal["ja", "zh", "en"]
    # question_key: str
    question: str

class AIQuestionRequest(BaseModel):
    # x_language: Literal["ja", "zh", "en"]
    user_request: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )
    story_id: int
    step_order: int
    canvas: dict
    audio: dict = Field(default_factory=dict)


class AIAnswer(BaseModel):
    mode: Literal["suggestion", "generate"]
    output: dict[str, object]


# from typing import Annotated, Literal
# from pydantic import BaseModel, Field

# class SuggestionOutput(BaseModel):
#     asset_keys: list[str]


# class GenerateOutput(BaseModel):
#     canvas: dict[str, object]

# class SuggestionAnswer(BaseModel):
#     mode: Literal["suggestion"]
#     output: SuggestionOutput


# class GenerateAnswer(BaseModel):
#     mode: Literal["generate"]
#     output: GenerateOutput


# AIAnswer = Annotated[
#     SuggestionAnswer | GenerateAnswer,
#     Field(discriminator="mode"),
# ]


# assets
class AudioOptionResponse(BaseModel):
    audio_key: str
    name: str
    audio_url: str
    is_default: bool
    sort_order: int


class AssetsResponse(BaseModel):
    id: int
    asset_key: str
    name: str
    category: str
    category_translation: str
    image_url: str
    audio_url: str | None
    default_audio_key: str | None
    audio_options: list[AudioOptionResponse] = Field(
        default_factory=list
    )

# class AssetsList(BaseModel):
#     asset_key: str
#     name: str
