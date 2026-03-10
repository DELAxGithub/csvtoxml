"""
Convert Whisper JSON transcriptions to csvtoxml-compatible CSV format.

031radio speaker mapping:
  A_00002 (前半): Speaker 1=石川, Speaker 2=ライラ
  A_00003 (後半): Speaker 1=ライラ, Speaker 2=石川
"""

import csv
import json
import re
from pathlib import Path


def parse_timestamp(ts: str) -> int:
    """Parse MM:SS or HH:MM:SS to total seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def seconds_to_timecode(secs: int, fps: int = 25) -> str:
    """Convert seconds to HH:MM:SS:FF timecode (frames=00)."""
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}:00"


def convert_whisper_json_to_csv(
    json_path: Path,
    output_path: Path,
    speaker_map: dict[str, str],
    color_map: dict[str, str],
):
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)

    rows = []
    for entry in entries:
        speaker_raw = entry["speaker"]
        speaker_name = speaker_map.get(speaker_raw, speaker_raw)
        color = color_map.get(speaker_name, "Lavender")

        ts = entry["timestamp"]
        match = re.match(r"(.+?)-(.+)", ts)
        if not match:
            continue
        in_sec = parse_timestamp(match.group(1))
        out_sec = parse_timestamp(match.group(2))
        # If out == in, add 1 second minimum duration
        if out_sec <= in_sec:
            out_sec = in_sec + 1

        rows.append({
            "Speaker Name": speaker_name,
            "イン点": seconds_to_timecode(in_sec),
            "アウト点": seconds_to_timecode(out_sec),
            "文字起こし": entry["text"],
            "色選択": color,
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated: {output_path} ({len(rows)} rows)")


def main():
    base = Path("031radio")

    color_map = {
        "石川": "Violet",
        "ライラ": "Rose",
    }

    # A_00002 (前半): Speaker 1=石川, Speaker 2=ライラ
    convert_whisper_json_to_csv(
        json_path=base / "A_00002_Wireless_PRO.json",
        output_path=base / "031_1_whisper.csv",
        speaker_map={
            "Speaker 1": "石川",
            "Speaker 2": "ライラ",
            "Speaker 3": "話者3",
        },
        color_map=color_map,
    )

    # A_00003 (後半): Speaker 1=ライラ, Speaker 2=石川
    convert_whisper_json_to_csv(
        json_path=base / "A_00003_Wireless_PRO.json",
        output_path=base / "031_2_whisper.csv",
        speaker_map={
            "Speaker 1": "ライラ",
            "Speaker 2": "石川",
            "Speaker 3": "話者3",
            "Speaker 4": "話者4",
            "Speaker 5": "話者5",
        },
        color_map=color_map,
    )


if __name__ == "__main__":
    main()
