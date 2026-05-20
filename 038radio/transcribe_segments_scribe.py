#!/usr/bin/env python3
"""
VADセグメントを ElevenLabs Scribe で書き起こし → 既存パイプラインと同じCSV出力。

Whisper版 (transcribe_segments.py) の置換ではなく並列のオプション。
出力CSV列は同一なので merge_pinmics.py 以降は無改修で動く。

使い方:
  export ELEVENLABS_API_KEY=$(op read "op://Private/elevenlabs/api_key")
  ~/.venvs/whisper-asr/bin/python transcribe_segments_scribe.py --speaker 千葉 --limit 3   # 接続テスト
  ~/.venvs/whisper-asr/bin/python transcribe_segments_scribe.py --speaker 千葉 --out 千葉_whisper.csv   # 本番

引数:
  --speaker 千葉|東島
  --limit N         先頭Nセグメントだけ（API疎通テスト用）
  --model           デフォルト "scribe_v1"
  --out             デフォルト {speaker}_scribe.csv
  --rate            時間単価USD（コスト試算用、デフォルト 0.40）
"""
import argparse
import csv
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from transcribe_segments import (
    WAV_PATHS,
    extract_segment,
    is_hallucination,
    seconds_to_tc,
)

API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MAX_RETRIES = 4
RETRY_BASE_SEC = 2.0


def call_scribe(api_key: str, audio_path: Path, model_id: str) -> dict:
    """Scribe API を1回叩く。一時的なエラーは指数バックオフで再試行。"""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with audio_path.open("rb") as fp:
                resp = requests.post(
                    API_URL,
                    headers={"xi-api-key": api_key},
                    files={"file": (audio_path.name, fp, "audio/wav")},
                    data={
                        "model_id": model_id,
                        "language_code": "ja",
                        "diarize": "false",
                        "tag_audio_events": "false",
                    },
                    timeout=180,
                )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except (requests.ConnectionError, requests.Timeout) as ex:
            last_exc = ex
        wait = RETRY_BASE_SEC * (2 ** attempt)
        print(f"  retry in {wait:.0f}s ({last_exc})")
        time.sleep(wait)
    raise RuntimeError(f"Scribe API failed after {MAX_RETRIES} retries: {last_exc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", required=True, choices=["千葉", "東島"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="scribe_v1")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rate", type=float, default=0.40, help="USD/hour for cost estimate")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit(
            "ELEVENLABS_API_KEY 未設定。\n"
            "  source .env  または  export ELEVENLABS_API_KEY=$(op read ...)"
        )

    base = Path(__file__).parent
    segs = json.loads((base / "vad_segments.json").read_text())[args.speaker]
    if args.limit > 0:
        segs = segs[: args.limit]
    print(f"{args.speaker}: {len(segs)} segments → Scribe ({args.model})")

    wav_path = WAV_PATHS[args.speaker]
    rows = []
    total_audio_sec = 0.0
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_wav = Path(tmpdir) / "seg.wav"
        for i, (s, e) in enumerate(segs):
            extract_segment(wav_path, s, e, tmp_wav)
            try:
                result = call_scribe(api_key, tmp_wav, args.model)
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
            total_audio_sec += (e - s)
            if (i + 1) % 10 == 0 or i + 1 == len(segs):
                print(f"  [{i+1}/{len(segs)}] {seconds_to_tc(s)} {text[:40]}")

    out_path = Path(args.out) if args.out else base / f"{args.speaker}_scribe.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Speaker Name", "Start Time", "End Time", "Text"])
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.time() - t0
    cost = (total_audio_sec / 3600.0) * args.rate
    print(f"\n→ {out_path.name} ({len(rows)} rows)")
    print(f"  audio: {total_audio_sec/60:.1f} min  wall: {elapsed:.0f} s  est cost: ${cost:.3f}")


if __name__ == "__main__":
    main()
