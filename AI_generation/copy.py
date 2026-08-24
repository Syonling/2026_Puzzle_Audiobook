"""把生成好的拼贴画素材发布到 static,并生成 assets 数据。

    poetry run python -m AI_generation.copy

做三件事(可重复运行,每批新图审查完后跑一次):
1. AI_generation/images/<分类>/<标签>.png 拷贝(拍平)到 static/images/<标签>.png
2. 拷贝完成后,把 AI_generation/images 下的内容移动到 AI_generation/copy_finsh
   归档(保留分类子目录结构,重名覆盖)
3. 扫描 static/images 下的全部 png,按 assets.py 的示例格式重新生成资产数据,
   覆盖写入 AI_generation/assets.py(所以每次运行都反映 static/images 的全量现状)

分类和翻译都来自 labels.py(LABELS / CATEGORY_NAMES / CATEGORY_NAMES_JA /
LABEL_TRANSLATIONS);en 名由标签名自动生成(下划线转空格 + 首字母大写)。
遇到不认识的标签(不在 LABELS 中)会直接报错退出,不猜。

边界约定: 除「拷贝到 static/images」外,所有写动作都发生在 AI_generation 目录内。
"""

import json
import shutil
import sys
from pathlib import Path

from AI_generation.labels import (
    CATEGORY_NAMES,
    CATEGORY_NAMES_JA,
    LABEL_TRANSLATIONS,
    LABELS,
)

BASE_DIR = Path(__file__).parent
SRC_IMAGES = BASE_DIR / "images"                       # 生成脚本的输出目录
ARCHIVE_DIR = BASE_DIR / "copy_finsh"                  # 已发布图片的归档目录
STATIC_IMAGES = BASE_DIR.parent / "static" / "images"  # 发布目标(唯一的对外写动作)
STATIC_AUDIO = BASE_DIR.parent / "static" / "audio"    # audio.py 的输出目录(只读)
ASSETS_FILE = BASE_DIR / "assets.py"                   # 资产数据输出(覆盖)

# 标签 -> 所属分类 的反查表
_LABEL_TO_CATEGORY = {
    label: category for category, labels in LABELS.items() for label in labels
}


def copy_to_static() -> int:
    """步骤 1: images 下所有 png 拍平拷贝到 static/images。返回拷贝张数。"""
    pngs = sorted(SRC_IMAGES.glob("*/*.png"))
    STATIC_IMAGES.mkdir(parents=True, exist_ok=True)
    for png in pngs:
        shutil.copy2(png, STATIC_IMAGES / png.name)
        print(f"拷贝: {png.relative_to(BASE_DIR)} -> static/images/{png.name}")
    return len(pngs)


def archive_images() -> None:
    """步骤 2: 把 images 下的内容移动到 copy_finsh 归档(保留子目录,重名覆盖)。"""
    for png in sorted(SRC_IMAGES.glob("*/*.png")):
        target = ARCHIVE_DIR / png.relative_to(SRC_IMAGES)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        shutil.move(str(png), str(target))
    # 清掉搬空的分类子目录,保留 images 本身
    for sub in sorted(SRC_IMAGES.iterdir()):
        if sub.is_dir() and not any(sub.iterdir()):
            sub.rmdir()
    print(f"归档完成: images/ 下的内容已移动到 {ARCHIVE_DIR.name}/")


def build_asset(label: str) -> dict:
    """按 assets.py 示例格式为一个标签生成资产数据。"""
    category = _LABEL_TO_CATEGORY[label]
    translation = LABEL_TRANSLATIONS[label]
    en_name = label.replace("_", " ").title()
    return {
        "asset_key": label,
        "category": category,
        "image_url": f"/static/images/{label}.png",
        # 音频由 audio.py 统一输出 wav;文件不存在则为 None
        # (可播放性校验在 audio.py 的 sync_assets_audio,那边会进一步置 None)
        "audio_url": (
            f"/static/audio/{label}.wav"
            if (STATIC_AUDIO / f"{label}.wav").exists()
            else None
        ),
        "contents": [
            {
                "language": "ja",
                "name": translation["ja"],
                "category_translation": CATEGORY_NAMES_JA[category],
            },
            {
                "language": "zh",
                "name": translation["zh"],
                "category_translation": CATEGORY_NAMES[category],
            },
            {
                "language": "en",
                "name": en_name,
                "category_translation": category,
            },
        ],
    }


def generate_assets() -> int:
    """步骤 3: 扫描 static/images 全部 png,生成资产数据覆盖写入 assets.py。

    返回生成条数。遇到 labels.py 里不存在的标签直接报错退出。
    """
    stems = sorted(p.stem for p in STATIC_IMAGES.glob("*.png"))
    unknown = [s for s in stems if s not in _LABEL_TO_CATEGORY]
    if unknown:
        sys.exit(
            f"错误: static/images 下有 {len(unknown)} 个 png 不在 labels.py 的"
            f" LABELS 中: {unknown}\n请先处理这些文件或补充标签表,再重新运行。"
        )

    # 按 labels.py 的分类顺序输出,同分类内按标签表顺序
    ordered = [
        label for labels in LABELS.values() for label in labels if label in set(stems)
    ]
    assets = [build_asset(label) for label in ordered]

    header = (
        '"""资产数据 —— 由 copy.py 自动生成,请勿手改(重跑 copy.py 会覆盖)。\n\n'
        f"基于 static/images 下的 {len(assets)} 个 png 生成;\n"
        '分类与翻译来自 labels.py。\n"""\n\n'
    )
    body = "ASSETS = " + json.dumps(assets, ensure_ascii=False, indent=4)
    body = body.replace(": null", ": None") + "\n"   # audio_url 可能为 None
    ASSETS_FILE.write_text(header + body, encoding="utf-8")
    print(f"资产数据已生成: {ASSETS_FILE.name} ({len(assets)} 条)")
    return len(assets)


def main() -> None:
    if not any(SRC_IMAGES.glob("*/*.png")):
        print("images/ 下没有 png,跳过拷贝与归档,仅按 static/images 现状重新生成 assets。")
    else:
        copied = copy_to_static()
        print(f"共拷贝 {copied} 张")
        archive_images()
    generate_assets()


if __name__ == "__main__":
    main()
