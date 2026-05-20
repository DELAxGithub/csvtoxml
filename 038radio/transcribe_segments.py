#!/usr/bin/env python3
"""
VADセグメントを mlx-whisper で書き起こし → Premiere互換CSV出力。

引数:
  --speaker 千葉|東島
  --limit N    (テスト用に先頭Nセグメントだけ)
  --model モデル名 (デフォルト: large-v3-turbo)
"""
import argparse
import csv
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import mlx_whisper


def is_hallucination(text: str) -> bool:
    """繰り返し・低エントロピー・短すぎるYouTube定型句などをフィルタ"""
    if not text:
        return False  # 空は別扱い

    # 既知の Whisper 定型句
    fixed = {
        "ご視聴ありがとうございました", "ご視聴ありがとうございました。",
        "次の動画でお会いしましょう", "次の動画でお会いしましょう。",
        "おやすみなさい", "おやすみなさい。",
        "ありがとうございました", "ありがとうございました。",
        "Thank you for watching", "Thanks for watching",
    }
    if text in fixed:
        return True

    # initial_prompt 由来の漏れ
    if "話者は千葉と東島" in text:
        return True

    # 同じ短いトークン (1〜3文字) が大量に連続するパターン
    # 例: "になにな..." "あああああ..." "Não Não Não..."
    n = len(text)
    if n < 8:
        return False
    # 文字頻度の偏り
    freq = Counter(text.replace(" ", ""))
    if not freq:
        return False
    top_char, top_count = freq.most_common(1)[0]
    if top_count / max(1, n) > 0.4 and n > 20:
        return True

    # 短い文字列 (2〜4文字) が3回以上連続するパターン
    for k in (2, 3, 4):
        for i in range(len(text) - k * 3):
            chunk = text[i : i + k]
            if chunk * 3 in text:
                return True
    return False

BASE = Path(__file__).parent
WAV_DIR = BASE / "wav"

# ===== エピソード固有設定 =====
WAV_PATHS = {
    "千葉": WAV_DIR / "260420_001_Tr1.WAV",  # ★038で書き換え
    "東島": WAV_DIR / "260420_001_Tr2.WAV",  # ★038で書き換え
}
# ===============================

FPS = 25  # プラット XMEML シーケンス基準


def seconds_to_tc(sec: float, fps: int = FPS) -> str:
    total_frames = int(round(sec * fps))
    h, rem = divmod(total_frames, fps * 3600)
    m, rem = divmod(rem, fps * 60)
    s, f = divmod(rem, fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def extract_segment(wav_path: Path, start_sec: float, end_sec: float, out_path: Path):
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y",
            "-ss", f"{start_sec}", "-to", f"{end_sec}",
            "-i", str(wav_path),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            str(out_path),
        ],
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", required=True, choices=["千葉", "東島"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    segs = json.loads((BASE / "vad_segments.json").read_text())[args.speaker]
    if args.limit > 0:
        segs = segs[: args.limit]
    print(f"{args.speaker}: {len(segs)} segments to transcribe")

    wav_path = WAV_PATHS[args.speaker]
    rows = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_wav = Path(tmpdir) / "seg.wav"
        for i, (s, e) in enumerate(segs):
            extract_segment(wav_path, s, e, tmp_wav)
            try:
                result = mlx_whisper.transcribe(
                    str(tmp_wav),
                    path_or_hf_repo=args.model,
                    language="ja",
                    fp16=True,
                    verbose=False,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                    logprob_threshold=-0.8,
                    compression_ratio_threshold=1.8,
                    hallucination_silence_threshold=2.0,
                )
                text = (result.get("text") or "").strip()
                if is_hallucination(text):
                    text = "[HALLUCINATION_FILTERED]"
            except Exception as ex:
                text = f"[ERROR: {ex}]"
            rows.append({
                "Speaker Name": args.speaker,
                "Start Time": seconds_to_tc(s),
                "End Time": seconds_to_tc(e),
                "Text": text,
            })
            if (i + 1) % 10 == 0 or i + 1 == len(segs):
                print(f"  [{i+1}/{len(segs)}] {seconds_to_tc(s)} {text[:40]}")

    out_path = Path(args.out) if args.out else BASE / f"{args.speaker}_whisper.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Speaker Name", "Start Time", "End Time", "Text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n→ {out_path.name} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
