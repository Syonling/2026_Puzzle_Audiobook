"""音频统一规格化: AI_generation/Audio -> static/audio。

    poetry run python -m AI_generation.audio          # 只处理新增(输出已存在则跳过)
    poetry run python -m AI_generation.audio --force  # 全部重新处理

目标规格: 立体声 / 44.1 kHz / 平均响度 -23 LUFS / 无压缩 wav(16-bit PCM)。
时长不变: 响度归一用 ffmpeg loudnorm 两遍式 + linear=true——先测量、再施加
纯线性增益,不做动态压缩、不做时间伸缩;若线性增益会顶破真峰值上限,
loudnorm 会自动少给增益(此时实际响度略低于 -23,处理日志会体现)。

复用: 往 Audio/ 里放新文件后重跑即可,已处理过的自动跳过(按输出是否存在判断)。
输出文件名统一为小写 <名字>.wav(如 Seagull.wav -> seagull.wav),
与 assets 数据里 /static/audio/<label>.wav 的引用格式对齐。
处理极短或近无声文件时若响度无法测量,会退化为仅转换格式并给出警告。
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from AI_generation.labels import LABELS

BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "Audio"
DST_DIR = BASE_DIR.parent / "static" / "audio"
ASSETS_FILE = BASE_DIR / "assets.py"

TARGET_LUFS = -23.0
TRUE_PEAK = -1.5     # 真峰值上限 dBTP(EBU R128 惯例)
LRA = 11.0
SAMPLE_RATE = 44100

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif"}

# 输出规格: 立体声 + 44.1kHz + 16-bit PCM 无压缩 wav
_FORMAT_ARGS = ["-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le"]


def measure_loudness(src: Path) -> dict | None:
    """第一遍: 测量响度,返回 loudnorm 的 JSON 测量值;测不出返回 None。"""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(src),
            "-af", f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={LRA}:print_format=json",
            "-f", "null", "-",
        ],
        # errors="replace": 个别音频的元数据不是 UTF-8,避免解码崩溃
        capture_output=True, text=True, errors="replace",
    )
    matches = re.findall(r"\{[^{}]+\}", result.stderr)
    if not matches:
        return None
    stats = json.loads(matches[-1])
    if stats.get("input_i") in (None, "-inf"):
        return None
    return stats


def process_one(src: Path, force: bool = False) -> str:
    """处理单个文件,返回结果标记: done / skipped / fallback / failed。"""
    dst = DST_DIR / (src.stem.lower() + ".wav")
    if dst.exists() and not force:
        return "skipped"

    stats = measure_loudness(src)
    if stats is None:
        # 太短/近无声,响度测不出: 只转格式,不动响度
        print(f"警告: {src.name} 无法测量响度,仅转换格式(未做响度归一)")
        af_args = []
        tag = "fallback"
    else:
        af = (
            f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={LRA}"
            f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true"
        )
        af_args = ["-af", af]
        tag = "done"

    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
        + af_args + _FORMAT_ARGS + [str(dst)],
        capture_output=True, text=True, errors="replace",
    )
    if result.returncode != 0:
        print(f"失败: {src.name}\n{result.stderr.strip()}")
        return "failed"

    detail = f"(原响度 {stats['input_i']} LUFS)" if stats else ""
    print(f"完成: {src.name} -> {dst.name} {detail}")
    return tag


def is_playable(path: Path) -> bool:
    """ffprobe 能解码且时长 > 0 才算可正常播放。"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ],
        capture_output=True, text=True, errors="replace",
    )
    if result.returncode != 0:
        return False
    try:
        return float(result.stdout.strip()) > 0
    except ValueError:
        return False


def sync_assets_audio() -> None:
    """按 static/audio 的实际文件,同步 assets.py 里每条的 audio_url。

    - <asset_key>.wav 存在且可播放 -> audio_url = /static/audio/<asset_key>.wav
    - 不存在(或损坏无法播放)     -> audio_url = None
    只改 audio_url,不动其他字段;问题在最后统一汇总输出。
    """
    if not ASSETS_FILE.exists():
        print(f"跳过 assets 同步: {ASSETS_FILE} 不存在")
        return

    # 从文件动态加载,拿到最新的 ASSETS(不走 import 缓存)
    import importlib.util

    spec = importlib.util.spec_from_file_location("_assets_data", ASSETS_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assets = module.ASSETS

    fixed_urls, set_none, broken = [], [], []
    for asset in assets:
        key = asset["asset_key"]
        wav = DST_DIR / f"{key}.wav"
        if wav.exists():
            if is_playable(wav):
                expected = f"/static/audio/{key}.wav"
                if asset.get("audio_url") != expected:
                    fixed_urls.append((key, asset.get("audio_url"), expected))
                    asset["audio_url"] = expected
            else:
                # 文件在但坏了: 引用它只会播放失败,置 None 并单独报告
                broken.append(key)
                if asset.get("audio_url") is not None:
                    asset["audio_url"] = None
        else:
            if asset.get("audio_url") is not None:
                set_none.append(key)
                asset["audio_url"] = None

    # 孤儿音频: static/audio 里有文件,但没有任何 asset_key 对得上
    asset_keys = {a["asset_key"] for a in assets}
    orphans = sorted(
        p.name for p in DST_DIR.glob("*.wav") if p.stem not in asset_keys
    )

    # 写回(保持 copy.py 的生成格式; json 的 null 替换为 Python 的 None)
    header = (
        '"""资产数据 —— 由 copy.py 自动生成、audio.py 同步 audio_url,'
        '请勿手改。\n\n'
        f"基于 static/images 下的 {len(assets)} 个 png 生成;\n"
        '分类与翻译来自 labels.py;audio_url 与 static/audio 实际文件同步。\n"""\n\n'
    )
    body = "ASSETS = " + json.dumps(assets, ensure_ascii=False, indent=4)
    body = body.replace(": null", ": None") + "\n"
    ASSETS_FILE.write_text(header + body, encoding="utf-8")

    # --- 统一汇总 ---------------------------------------------------------
    with_audio = sum(1 for a in assets if a.get("audio_url"))
    print(f"\n===== assets.py 音频同步汇总 =====")
    print(f"共 {len(assets)} 条资产: 有音频 {with_audio}, 无音频(audio_url=None) "
          f"{len(assets) - with_audio}")
    if fixed_urls:
        print(f"修正了 {len(fixed_urls)} 条 audio_url:")
        for key, old, new in fixed_urls:
            print(f"  {key}: {old} -> {new}")
    if set_none:
        print(f"缺少音频、已置 None 的 {len(set_none)} 条:")
        print(f"  {', '.join(set_none)}")
    if broken:
        print(f"文件存在但无法播放(已置 None,请检查源音频并重新处理): {broken}")
    if orphans:
        print(f"孤儿音频(在 static/audio 中但无对应 asset_key,不会被引用):")
        print(f"  {', '.join(orphans)}")
    if not (fixed_urls or set_none or broken or orphans):
        print("无问题: 所有 audio_url 均与实际文件一致且可播放")


def main() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("错误: 未找到 ffmpeg,请先安装(brew install ffmpeg)")
    if not SRC_DIR.is_dir():
        sys.exit(f"错误: 源目录不存在: {SRC_DIR}")

    force = "--force" in sys.argv
    sources = sorted(
        p for p in SRC_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )
    if not sources:
        print(f"{SRC_DIR} 下没有音频文件")
        return

    DST_DIR.mkdir(parents=True, exist_ok=True)
    counts = {"done": 0, "skipped": 0, "fallback": 0, "failed": 0}
    for src in sources:
        counts[process_one(src, force)] += 1

    print(
        f"\n汇总: 归一完成 {counts['done']}, 跳过(已存在) {counts['skipped']}, "
        f"仅转格式 {counts['fallback']}, 失败 {counts['failed']}"
    )

    # 提示: 输出名和标签对不上的,前端会取不到音频(assets 按标签引用)
    all_labels = {label for labels in LABELS.values() for label in labels}
    unmatched = sorted(
        p.stem.lower() for p in sources if p.stem.lower() not in all_labels
    )
    if unmatched:
        print(f"注意: 以下音频名不在 labels.py 的标签中,assets 不会引用到它们:")
        for name in unmatched:
            print(f"  {name}")

    # 处理完后,把 assets.py 的 audio_url 与实际文件对齐
    sync_assets_audio()


if __name__ == "__main__":
    main()
