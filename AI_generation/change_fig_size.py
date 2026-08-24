"""手动等比缩放 static/images 下的指定 png,覆盖原图。

    poetry run python -m AI_generation.change_fig_size

用法: 在下面的 TASKS 里填「文件名 -> 缩放比例」,跑一次,处理完 TASKS 清空即可。
- 只处理列出来的图,不碰其他文件。
- 等比缩放,LANCZOS 重采样(高质量,缩小时清晰度损失最小),保留透明通道。
- 覆盖原图前不备份——归档在 AI_generation/copy_finsh 里有原始大图,
  改坏了从那里重新跑 copy.py 即可恢复。
- 注意: 放大(比例 > 1)必然损失清晰度,脚本会警告但仍会执行。
"""

from pathlib import Path

from PIL import Image

STATIC_IMAGES = Path(__file__).parent.parent / "static" / "images"

# ---------------------------------------------------------------------------
# 在这里填要缩放的图片: 文件名(相对 static/images) -> 缩放比例
# 例如 0.5 = 缩到一半, 0.8 = 缩到八成。处理完建议清空,避免下次误跑重复缩放。
# ---------------------------------------------------------------------------
TASKS: dict[str, float] = {
    "ant.png": 0.5,
    "bee.png": 0.7,
    # "cow.png": 0.8,
    # "farm_background.png": 0.5,
}


def resize_one(filename: str, scale: float) -> None:
    path = STATIC_IMAGES / filename
    if not path.exists():
        print(f"跳过(文件不存在): {filename}")
        return
    if scale <= 0:
        print(f"跳过(比例必须大于 0): {filename} -> {scale}")
        return
    if scale > 1:
        print(f"警告: {filename} 比例 {scale} 是放大,会损失清晰度")

    with Image.open(path) as img:
        old_size = img.size
        new_size = (
            max(1, round(old_size[0] * scale)),
            max(1, round(old_size[1] * scale)),
        )
        if new_size == old_size:
            print(f"跳过(尺寸无变化): {filename} {old_size}")
            return
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        resized.save(path, format="PNG", optimize=True)
    print(f"完成: {filename} {old_size[0]}x{old_size[1]} -> {new_size[0]}x{new_size[1]}")


def main() -> None:
    if not TASKS:
        print("TASKS 为空: 请先在 change_fig_size.py 顶部填入「文件名 -> 缩放比例」")
        return
    for filename, scale in TASKS.items():
        resize_one(filename, scale)


if __name__ == "__main__":
    main()
