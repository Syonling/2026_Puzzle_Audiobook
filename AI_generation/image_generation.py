"""拼贴画素材批量生成 — OpenAI gpt-image-2 + Batch API(半价)。

流程(三步,分开执行,因为 Batch 是异步的,一般几分钟~几小时内完成):
    poetry run python -m AI_generation.image_generation submit [数量]  # 提交 batch,打印 batch_id
                                                            # 数量可选,如 submit 10 只
                                                            # 抽 10 个测画风(跨分类轮流取)
    poetry run python -m AI_generation.image_generation status <batch_id>   # 查询进度
    poetry run python -m AI_generation.image_generation fetch <batch_id>    # 完成后下载,按目录保存

审查后重跑坏图(仍走 batch 半价,fetch 会覆盖旧图):
    poetry run python -m AI_generation.image_generation redo cow horse peacock

LABELS 扩充后只生成新加入的标签(images/ 和 copy_finsh/ 里都没有的才算新):
    poetry run python -m AI_generation.image_generation submit new

API key 从 puzzle_audiobook/.env 的 OPENAI_API_IMAGE_KEY 读取(图像生成专用 key)。
图片保存到 ./images/<目录>/<标签>.png

单张测试
# 测背景(参数顺序: 标签 分类)
poetry run python -m AI_generation.image_generation test farm_background background

# 测图标
poetry run python -m AI_generation.image_generation test crow birds

# 不带参数默认测 crow
poetry run python -m AI_generation.image_generation test

"""

import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from app.core.config import settings
from AI_generation.labels import (   # 标签表单独维护在 labels.py
    BACKGROUND_SCENES,
    LABELS,
    SUBJECT_OVERRIDES,
)

# ---------------------------------------------------------------------------
# 基本配置
# ---------------------------------------------------------------------------

# 注意: gpt-image-2 不支持 background="transparent"(官方文档明确说明),
# 而拼贴素材必须透明底,所以用支持透明的 gpt-image-1.5(质量中等,符合需求)。
# 若以后 gpt-image-2 支持透明了,直接改回即可,下面有启动检查兜底。
MODEL = "gpt-image-1.5"
SIZE = "1024x1024"         # prompt 要求 1:1 方形画布,与此保持一致
QUALITY = "medium"         # 中等质量即可: low / medium / high
BACKGROUND = "transparent" # 拼贴素材需要透明底(由 API 参数保证,不依赖 prompt)
OUTPUT_FORMAT = "png"      # 透明背景要求 png 或 webp

# 已知不支持透明背景的模型,启动时拦截,避免提交 batch 后才批量报错
_NO_TRANSPARENT_MODELS = {"gpt-image-2"}
if BACKGROUND == "transparent" and MODEL in _NO_TRANSPARENT_MODELS:
    sys.exit(
        f"错误: {MODEL} 不支持透明背景。"
        "改用 gpt-image-1.5 / gpt-image-1,或把 BACKGROUND 设为 'opaque' 后自行抠图。"
    )

# --- 背景(background 分类)专用配置 ---------------------------------------
# 背景不需要透明底(整幅铺满 + 画内白边),所以可以用 gpt-image-2——
# 它支持任意分辨率(最长边 3840 内),能直接出 8:5 的 1600x1000;
# 图标用的 gpt-image-1.5 只支持固定尺寸,做不了这个比例。
BG_MODEL = "gpt-image-2"
# API 要求宽高都能被 16 整除,精确 8:5 只能取 1536x960 / 1664x1040 等档位;
# 取 1664x1040(不低于原定的 1600x1000)。
BG_SIZE = "1664x1040"      # 8:5 横向
BG_QUALITY = "medium"
BG_BACKGROUND = "opaque"

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
ARCHIVE_DIR = BASE_DIR / "copy_finsh"   # copy.py 发布后的归档目录
BATCH_INPUT_FILE = BASE_DIR / "batch_input.jsonl"

# ---------------------------------------------------------------------------
# Prompt 模板 —— 画风统一的关键,所有调整都在这里做
# ---------------------------------------------------------------------------
# {subject} 会被替换成标签名(下划线转空格)。
# 风格定位:欧美经典儿童绘本水彩 + 莫兰迪低饱和配色 + 白边剪纸拼贴效果。
# 透明背景由 API 参数 BACKGROUND 保证,模板里的背景条款是双保险。

PROMPT_TEMPLATE = """\
Create one isolated collage-style illustration of {subject} for a children's \
interactive picture-book asset collection.

SUBJECT REQUIREMENTS:
1. Show exactly one complete main subject.
2. The subject must have a simple, recognizable, child-friendly silhouette.
3. Use a front view or a gentle three-quarter view.
4. Center the subject and leave comfortable transparent padding on every side.
5. Keep the entire subject visible without cropping any part.
6. Do not add unrelated objects, scenery, plants, ground, decorative elements, \
or additional characters unless they are an essential physical part of the subject.
7. If the subject is a natural phenomenon or sound source without a fixed body \
(such as rain, wind, thunder, a stream, or ocean waves), depict it as one simple, \
iconic, child-friendly pictorial form (for example a soft cloud with falling \
raindrops for rain), still following every rule above.
8. If the subject is explicitly described as a group, flock, or herd, draw \
that group as ONE cohesive unit: members close together or slightly \
overlapping, treated as a single cutout with one shared outer silhouette — \
never as scattered separate pieces, and with exactly the number of members \
the description states.

ILLUSTRATION STYLE:
1. Use a hand-painted watercolor style inspired by classic European and North \
American children's picture-book illustrations.
2. The illustration should feel warm, gentle, imaginative, slightly whimsical, \
and suitable for young children.
3. Use softly imperfect hand-painted shapes rather than mechanically precise \
digital forms.
4. Include subtle watercolor pigment variation, delicate washes, lightly visible \
brush texture, and natural paper grain within the painted subject.
5. If the subject is a living creature (an animal, bird, insect, or person), \
keep its facial expression gentle and friendly.
6. Do not anthropomorphize subjects that do not naturally have faces: never add \
eyes, smiles, faces, or expressions to scenery, weather, plants, buildings, \
vehicles, instruments, or everyday objects. Depict them as charming but \
faceless illustrated forms.
7. Use rounded, approachable forms without excessive detail.
8. Avoid photorealism, anime styling, comic-book rendering, vector graphics, \
flat digital icons, glossy surfaces, and 3D rendering.

COLOR PALETTE:
1. Use a muted Morandi-inspired watercolor palette with low to medium saturation.
2. Prefer dusty blue, sage green, muted ochre, faded terracotta, warm gray, \
soft brown, pale cream, and restrained natural colors.
3. Avoid neon colors, highly saturated primary colors, harsh contrast, pure \
digital gradients, and large areas of pure black.
4. Use black only when necessary for very small facial details.
5. Keep the overall color temperature soft, balanced, calm, and consistent with \
the rest of the collection.

COLLAGE CUTOUT TREATMENT:
1. Surround the entire outer silhouette of the subject with a thick, clearly \
visible warm-white paper-cut outline.
2. Keep the white outline continuous, smooth, and approximately even around the \
whole subject.
3. The outline must follow the subject's silhouette and must not become a \
rectangular frame around the image.
4. Add a subtle soft cool-gray shadow immediately outside the white outline.
5. Offset the shadow mainly to the right and slightly downward.
6. Keep the shadow close to the cutout, softly blurred, light in opacity, and \
visually consistent.
7. The shadow should make the illustrated paper cutout appear slightly raised \
above a collage surface.
8. Do not add a large ground shadow, dramatic lighting shadow, shadow in \
multiple directions, or dark heavy drop shadow.
9. The watercolor subject, thick white outline, and subtle right-down shadow \
must form one complete draggable collage asset.

COMPOSITION AND OUTPUT:
1. Use a square 1:1 canvas.
2. Keep the subject's natural proportions. The cutout's longest dimension \
should span approximately 65-75 percent of the canvas; the other dimension \
follows the subject's real shape and may be much smaller.
3. A naturally wide subject (such as an ocean wave, a bridge, or a train) or a \
naturally tall subject (such as a lighthouse or a tree) should NOT be \
stretched, squashed, or padded to fill the square — leaving large transparent \
areas on the canvas is correct and expected.
4. Leave enough transparent space around the white outline and shadow so \
neither is clipped.
5. Use a genuinely transparent background with a clean alpha channel.
6. Do not draw a white background, colored background, landscape, room, sky, \
floor, horizon, or ground plane.
7. Do not draw a gray-and-white checkerboard pattern to imitate transparency.
8. Do not include text, letters, labels, captions, logos, signatures, borders, \
frames, or watermarks. Exception: when the subject itself IS a symbol or \
punctuation glyph (such as an exclamation mark or a comic sleep symbol), draw \
exactly that one symbol as the subject — but still add no other text anywhere.
9. Produce a clean, high-resolution asset suitable for placement, scaling, and \
dragging on a digital collage canvas.

COLLECTION CONSISTENCY:
1. Match every other asset in this collection exactly in watercolor technique, \
paper texture, color saturation, visual softness, outline thickness, shadow \
color, shadow direction, lighting, proportions, and level of detail.
2. Do not reinterpret the collection as a different artistic style.
3. Maintain the same visual language even when the subject changes.
4. The final asset should look as though it was painted, cut out, and assembled \
by the same children's-book illustrator as all other assets in the collection.

STRICTLY AVOID:
Photorealism, realistic photography, 3D render, glossy plastic, clay render, \
vector art, flat digital icon, anime, manga, comic-book style, pixel art, neon \
colors, highly saturated colors, harsh contrast, thick black outlines, colored \
outlines, thin or missing white outlines, rectangular borders, heavy shadows, \
large ground shadows, shadows cast to the left, multiple light sources, \
detailed scenery, opaque backgrounds, checkerboard transparency patterns, \
multiple unrelated subjects, duplicated subjects (except a group explicitly \
described as one cohesive cutout), duplicated limbs, malformed anatomy, \
anatomical features drawn in wrong positions, extra body parts, \
anthropomorphized objects or scenery, cartoon faces or eyes on non-living \
subjects, subjects stretched or distorted to fill the canvas, \
cropped subjects, floating disconnected body parts, and any text, labels, \
logos, signatures, or watermarks other than a symbol glyph that is itself \
the subject.
"""


def build_prompt(label: str) -> str:
    """组合图标的最终 prompt。

    主体描述默认是标签名(下划线转空格);某个标签出图有系统性问题时,
    在 labels.py 的 SUBJECT_OVERRIDES 里写更精确的描述覆盖它。
    """
    subject = SUBJECT_OVERRIDES.get(label, label.replace("_", " "))
    return PROMPT_TEMPLATE.format(subject=subject)


# ---------------------------------------------------------------------------
# 背景 Prompt 模板 —— background 分类专用
# ---------------------------------------------------------------------------
# {scene} 来自 labels.py 的 BACKGROUND_SCENES(只含环境要素的场景描述)。
# 核心思路: 背景是"舞台"不是"画作"——留白给用户放贴纸,画面焦点由贴纸决定;
# 水彩莫兰迪风格与图标一致,但饱和度/对比度/细节都必须更弱;画内白边、无阴影。

BACKGROUND_PROMPT_TEMPLATE = """\
Create one wide watercolor background scene of {scene} for a children's \
interactive picture-book collage app.

ROLE OF THIS BACKGROUND:
1. Users will drag separate white-outlined cutout stickers (animals, people, \
vehicles, objects) onto this background. The background only sets the stage; \
the visual focus must come from the stickers the user adds, never from the \
background itself.
2. Keep the composition calm, quiet, and deliberately under-filled rather \
than rich or complete.

SCENE CONTENT:
1. The scene description above is authoritative. Make its distinctive named \
elements clearly visible and prominent, and respect every exclusion it \
states. Do not add scenery types it does not mention.
2. Backgrounds in this collection must be clearly distinguishable from each \
other. Do NOT fall back to a generic composition of a grassy meadow with \
trees at the sides and mountains in the distance — build the composition \
from this scene's own distinctive elements instead.
3. Depict only the environment. Never include subjects that could look like \
draggable stickers: no animals, no birds, no insects, no people, no \
vehicles, no boats, and no prominent stand-alone props. For example, a farm \
background may contain grass, a fence, a distant barn and sky — but never a \
cow, a dog, or a farmer. However, if the scene description explicitly names \
such an element as part of the environment (for example moored fishing boats \
and hanging nets at a dock), include it as quiet background scenery — small, \
off-center, blended into the scene, never rendered like a draggable sticker.
4. Elements at the left and right edges may softly frame the picture, but \
only using elements that belong to the described scene.

COMPOSITION FOR STICKER PLACEMENT:
1. Keep the center and the main foreground area mostly open and empty — this \
is where users will place their stickers.
2. Do not fill the canvas with scene content; large calm and simple areas \
are required.
3. Keep complex detail away from the middle; fine detail belongs only near \
the edges.
4. Avoid strong or busy textures anywhere, so white-outlined stickers stay \
easy to recognize on top of the background.

SPATIAL LAYERS AND PERSPECTIVE:
1. Unless the scene description says otherwise (such as an indoor room, the \
inside of a forest, or an empty paper page), provide simple storybook depth: \
foreground ground along the bottom, an open main placement area in the \
middle, and sky or distant scenery at the top.
2. For open outdoor scenes with a visible horizon, place the horizon line at \
roughly 35-45 percent of the canvas height from the top, so open usable \
ground fills the lower part of the picture.
3. The foreground ground must stay usable for placing stickers: mostly level \
and open, not covered with rocks, flowers, or plants, no steep slopes, and \
no large objects already occupying it.
4. Use a gentle, nearly flat storybook perspective. Avoid wide-angle \
distortion and complex architectural perspective, so a sticker dropped \
anywhere on the ground still looks naturally placed.

STYLE AND COLOR:
1. Use the same hand-painted watercolor technique and muted Morandi-inspired \
palette as the sticker collection, with soft washes and natural paper grain.
2. But stay visually quieter than the stickers: noticeably lower saturation, \
weaker contrast, softer detail, and gently blurred edges throughout.
3. Avoid large areas of pure black and any vivid saturated color, so the \
white-outlined stickers always read as the visual subject.

BORDER AND OUTPUT:
1. Use the full 8:5 landscape canvas, fully painted edge to edge (no \
transparency anywhere).
2. Surround the whole scene with a clean, evenly wide, warm-white paper \
border on all four sides, like a page from a picture book. Do not add any \
shadow around or inside this border.
3. Do not include text, letters, labels, captions, logos, signatures, or \
watermarks.

STRICTLY AVOID:
Animals, birds, insects, people, vehicles, boats, prominent stand-alone \
props, a crowded or detailed center, a foreground already filled with \
objects, strong perspective distortion, wide-angle lens effects, high \
saturation, harsh contrast, heavy busy textures, large pure-black areas, \
drop shadows, vignette darkening, transparency, checkerboard patterns, \
text, labels, logos, signatures, and watermarks.
"""


def build_background_prompt(label: str) -> str:
    """组合背景的最终 prompt,场景描述来自 labels.py 的 BACKGROUND_SCENES。"""
    return BACKGROUND_PROMPT_TEMPLATE.format(scene=BACKGROUND_SCENES[label])


def image_request_body(category: str, label: str) -> dict:
    """按分类构造生成请求体: background 走背景配置,其余走图标配置。

    submit / submit new / redo / test 都经由这里,新增分类时只需改这一处。
    """
    if category == "background":
        return {
            "model": BG_MODEL,
            "prompt": build_background_prompt(label),
            "size": BG_SIZE,
            "quality": BG_QUALITY,
            "background": BG_BACKGROUND,
            "output_format": OUTPUT_FORMAT,
            "n": 1,
        }
    return {
        "model": MODEL,
        "prompt": build_prompt(label),
        "size": SIZE,
        "quality": QUALITY,
        "background": BACKGROUND,
        "output_format": OUTPUT_FORMAT,
        "n": 1,
    }




# ---------------------------------------------------------------------------
# Batch 三步流程
# ---------------------------------------------------------------------------

load_dotenv(BASE_DIR.parent / ".env")   # puzzle_audiobook/.env

_api_key = settings.openai_api_image_key.get_secret_value()
if not _api_key:
    sys.exit("错误: puzzle_audiobook/.env 中未找到 OPENAI_API_IMAGE_KEY")

client = OpenAI(api_key=_api_key)


def pick_labels(limit: int | None = None) -> list[tuple[str, str]]:
    """要生成的 (category, label) 列表。

    limit=None 生成全部;指定数量时在各分类间轮流抽取,
    让测试样本覆盖尽量多类型的主体(测画风稳定性用)。
    """
    if limit is None:
        return [(c, l) for c, labels in LABELS.items() for l in labels]

    queues = {c: list(labels) for c, labels in LABELS.items()}
    pairs: list[tuple[str, str]] = []
    while queues and len(pairs) < limit:
        for category in list(queues):
            if not queues[category]:
                del queues[category]
                continue
            pairs.append((category, queues[category].pop(0)))
            if len(pairs) >= limit:
                break
    return pairs


def pick_missing_labels() -> list[tuple[str, str]]:
    """只挑「还没生成过」的标签: images/ 和 copy_finsh/ 里都不存在对应 png。

    以文件系统为准,不维护清单——往 LABELS 里加新标签或新分类后,
    `submit new` 就只会生成缺的那些;想重出某张图,删掉它的 png 即可。
    """
    return [
        (category, label)
        for category, labels in LABELS.items()
        for label in labels
        if not (IMAGES_DIR / category / f"{label}.png").exists()
        and not (ARCHIVE_DIR / category / f"{label}.png").exists()
    ]


def pairs_for(labels_wanted: list[str]) -> list[tuple[str, str]]:
    """按标签名反查 (category, label) 列表,用于重跑指定标签。"""
    lookup = {label: c for c, labels in LABELS.items() for label in labels}
    missing = [l for l in labels_wanted if l not in lookup]
    if missing:
        sys.exit(f"错误: 未知标签 {missing}, 请检查 labels.py")
    return [(lookup[l], l) for l in labels_wanted]


def build_batch_input(pairs: list[tuple[str, str]], model: str) -> Path:
    """把选中的标签变成一行行 batch 请求,写入该模型专属的 JSONL 文件。"""
    lines = []
    for category, label in pairs:
        request = {
            # custom_id 编码了保存路径,fetch 时据此归档
            "custom_id": f"{category}/{label}",
            "method": "POST",
            "url": "/v1/images/generations",
            "body": image_request_body(category, label),
        }
        lines.append(json.dumps(request, ensure_ascii=False))
    input_file = BASE_DIR / f"batch_input_{model}.jsonl"
    input_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成 {len(lines)} 条请求 -> {input_file.name}")
    return input_file


def _submit_batch(pairs: list[tuple[str, str]]) -> None:
    """提交生成请求。OpenAI Batch 要求批内单一模型,所以按模型分组,
    每个模型单独提交一个 batch(如图标 gpt-image-1.5 和背景 gpt-image-2
    会拆成两个 batch,各自有独立的 batch_id,分别 status / fetch)。
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for category, label in pairs:
        model = image_request_body(category, label)["model"]
        groups.setdefault(model, []).append((category, label))

    for model, group in groups.items():
        input_path = build_batch_input(group, model)
        uploaded = client.files.create(file=input_path.open("rb"), purpose="batch")
        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/images/generations",
            completion_window="24h",
        )
        print(f"batch 已提交({model}, {len(group)} 张): {batch.id}")
        print(f"  查询: poetry run python -m AI_generation.image_generation status {batch.id}")


def submit(limit: int | None = None) -> None:
    """全量提交;limit 指定数量时跨分类轮流抽样(测画风用)。"""
    _submit_batch(pick_labels(limit))


def submit_new() -> None:
    """只提交尚未生成过的标签(LABELS 扩充后用这个,不会重跑已有图)。"""
    pairs = pick_missing_labels()
    if not pairs:
        print("没有待生成的新标签: LABELS 中的标签都已存在于 images/ 或 copy_finsh/")
        return
    print(f"待生成 {len(pairs)} 个新标签:")
    for category, label in pairs:
        print(f"  {category}/{label}")
    _submit_batch(pairs)


def redo(labels_wanted: list[str]) -> None:
    """只重跑指定标签(审查后修复坏图用),fetch 时会覆盖旧图。"""
    if not labels_wanted:
        sys.exit("用法: redo <标签> [标签...],如 redo cow horse peacock")
    _submit_batch(pairs_for(labels_wanted))


def status(batch_id: str) -> None:
    batch = client.batches.retrieve(batch_id)
    print(f"状态: {batch.status}")
    print(f"进度: {batch.request_counts}")
    if batch.status == "completed":
        print(f"下一步: poetry run python -m AI_generation.image_generation fetch {batch_id}")


def fetch(batch_id: str) -> None:
    batch = client.batches.retrieve(batch_id)
    if batch.status != "completed":
        print(f"batch 尚未完成,当前状态: {batch.status}")
        return

    content = client.files.content(batch.output_file_id).text
    saved, failed = 0, 0
    for line in content.splitlines():
        result = json.loads(line)
        custom_id = result["custom_id"]          # 形如 "biophony/crow"
        response = result.get("response")
        if not response or response.get("status_code") != 200:
            failed += 1
            print(f"失败: {custom_id} -> {result.get('error') or response}")
            continue

        b64 = response["body"]["data"][0]["b64_json"]
        out_path = IMAGES_DIR / f"{custom_id}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(b64))
        saved += 1
        print(f"保存: {out_path.relative_to(BASE_DIR)}")

    if batch.error_file_id:
        errors = client.files.content(batch.error_file_id).text
        print(f"--- 错误文件 ---\n{errors}")
    print(f"完成: 成功 {saved} 张, 失败 {failed} 张")


# ---------------------------------------------------------------------------
# 单张测试(不走 batch,立即返回)—— 调 prompt 风格时用这个快速迭代
# ---------------------------------------------------------------------------

def test_one(label: str = "crow", category: str = "birds") -> None:
    result = client.images.generate(**image_request_body(category, label))
    out_path = IMAGES_DIR / category / f"{label}_test.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(result.data[0].b64_json))
    print(f"保存: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    command = sys.argv[1]
    if command == "submit":
        arg = sys.argv[2] if len(sys.argv) > 2 else None
        if arg == "new":
            submit_new()
        else:
            submit(int(arg) if arg else None)
    elif command == "redo":
        redo(sys.argv[2:])
    elif command == "status":
        status(sys.argv[2])
    elif command == "fetch":
        fetch(sys.argv[2])
    elif command == "test":
        test_one(*sys.argv[2:])
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
