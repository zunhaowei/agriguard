"""生成旁白语音（edge-tts 中文神经语音），输出每句时长 JSON。"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

from narration import NARRATION

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
AUDIO = MEDIA / "audio"
AUDIO.mkdir(parents=True, exist_ok=True)

VOICE = "zh-CN-XiaoxiaoNeural"


def mp3_duration_seconds(path: Path) -> float:
    ff = str(Path(__import__("imageio_ffmpeg").get_ffmpeg_exe()))
    p = subprocess.run(
        [ff, "-i", str(path)],
        capture_output=True, text=True,
    )
    # 从 stderr 解析 Duration
    for line in p.stderr.splitlines():
        if "Duration:" in line:
            dur = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


async def synth(text: str, out: Path):
    tts = edge_tts.Communicate(text, VOICE)
    await tts.save(str(out))


async def main():
    meta = []
    for sid, text in NARRATION:
        mp3 = AUDIO / f"{sid}.mp3"
        wav = AUDIO / f"{sid}.wav"
        await synth(text, mp3)
        # mp3 -> wav（统一采样率，便于精确对齐与后续合成）
        ff = str(Path(__import__("imageio_ffmpeg").get_ffmpeg_exe()))
        subprocess.run(
            [ff, "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(wav)],
            capture_output=True,
        )
        dur = mp3_duration_seconds(wav)
        meta.append({"id": sid, "dur": dur, "text": text})
        print(f"{sid}  {dur:.2f}s  {text}")

    (MEDIA / "narration.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(m["dur"] for m in meta)
    print(f"TOTAL narration: {total:.2f}s")


asyncio.run(main())