#!/usr/bin/env python3
"""
ピンマイク2本のWhisperCSVをTC順にマージし、csvtoxml 入力フォーマットで出力。

入力:
  石塚_whisper.csv (Speaker Name, Start Time, End Time, Text)
  重田_whisper.csv (同上)

出力:
  38_whisper_merged.csv (Speaker Name, イン点, アウト点, 文字起こし, 色選択)
    - 両ピンマイクの発話を時間順にソート
    - HALLUCINATION_FILTERED 行は除外
    - 色: 石塚=Lavender, 重田=Violet
"""
import csv
from pathlib import Path

BASE = Path(__file__).parent

# ===== エピソード固有設定 =====
EPISODE = "38"
INPUTS = [
    (BASE / "石塚_whisper.csv", "石塚", "Lavender"),  # Tr1
    (BASE / "重田_whisper.csv", "重田", "Violet"),    # Tr2
]
# ===============================
OUTPUT = BASE / f"{EPISODE}_whisper_merged.csv"


def parse_tc(tc: str) -> int:
    """TC文字列 → 25fps基準のフレーム数（ソート用）"""
    parts = tc.strip().replace(";", ":").split(":")
    h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return ((h * 3600 + m * 60 + s) * 25) + f


def main():
    rows = []
    skipped = 0
    for path, speaker, color in INPUTS:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                text = r["Text"].strip()
                if "[HALLUCINATION_FILTERED]" in text or "[ERROR" in text:
                    skipped += 1
                    continue
                if not text:
                    skipped += 1
                    continue
                rows.append({
                    "Speaker Name": speaker,
                    "イン点": r["Start Time"],
                    "アウト点": r["End Time"],
                    "文字起こし": text,
                    "色選択": color,
                    "_sort": parse_tc(r["Start Time"]),
                })

    rows.sort(key=lambda r: r["_sort"])
    for r in rows:
        del r["_sort"]

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"],
        )
        writer.writeheader()
        writer.writerows(rows)

    speaker_count = {}
    for r in rows:
        speaker_count[r["Speaker Name"]] = speaker_count.get(r["Speaker Name"], 0) + 1

    print(f"出力: {OUTPUT.name}")
    print(f"  total: {len(rows)} rows  (skipped: {skipped})")
    for sp, n in speaker_count.items():
        print(f"  {sp}: {n}")


if __name__ == "__main__":
    main()
