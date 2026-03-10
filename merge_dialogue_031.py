"""
Merge separate wireless mic Whisper transcriptions into dialogue CSV.

Mic A = ライラ wearing → take ライラ's lines from A
Mic B = 石川 wearing → take 石川's lines from B
Discard crosstalk (other speaker on each mic) and MC.
B timestamps are +4 seconds behind A.
"""

import csv
import re
from pathlib import Path


OFFSET_B_SECONDS = 4

# Speaker label → real name mapping per file
# Only the primary speaker (mic wearer) is kept from each file
KEEP_MAP = {
    "A_00002_Wireless_PRO.csv": {"Speaker 2": "ライラ"},
    "B_00002_Wireless_PRO.csv": {"Speaker 1": "石川"},
    "A_00003_Wireless_PRO.csv": {"Speaker 1": "ライラ"},
    "B_00003_Wireless_PRO.csv": {"Speaker 2": "石川"},
}

PAIRS = [
    {
        "a_file": "A_00002_Wireless_PRO.csv",
        "b_file": "B_00002_Wireless_PRO.csv",
        "output": "031_1_dialogue_raw.csv",
    },
    {
        "a_file": "A_00003_Wireless_PRO.csv",
        "b_file": "B_00003_Wireless_PRO.csv",
        "output": "031_2_dialogue_raw.csv",
    },
]


def parse_ts(ts: str) -> int:
    """Parse MM:SS or HH:MM:SS to total seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def fmt_tc(secs: int) -> str:
    """Seconds → HH:MM:SS:00 timecode."""
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}:00"


def read_and_filter(csv_path: Path, keep_map: dict, offset: int = 0) -> list:
    """Read CSV, keep only primary speaker, apply time offset."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)  # skip header
        for row in reader:
            if len(row) < 5:
                continue
            speaker_label = row[1]
            if speaker_label not in keep_map:
                continue
            real_name = keep_map[speaker_label]
            start_sec = parse_ts(row[2]) + offset
            end_sec = parse_ts(row[3]) + offset
            if end_sec <= start_sec:
                end_sec = start_sec + 1
            text = row[4].strip().strip('"')
            if not text:
                continue
            rows.append({
                "speaker": real_name,
                "start": start_sec,
                "end": end_sec,
                "text": text,
            })
    return rows


def merge_consecutive(rows: list, gap_threshold: int = 2) -> list:
    """Merge consecutive entries by same speaker within gap_threshold seconds."""
    if not rows:
        return []
    merged = [rows[0].copy()]
    for r in rows[1:]:
        prev = merged[-1]
        if (r["speaker"] == prev["speaker"]
                and r["start"] - prev["end"] <= gap_threshold):
            prev["end"] = max(prev["end"], r["end"])
            prev["text"] += " " + r["text"]
        else:
            merged.append(r.copy())
    return merged


def process_pair(pair: dict, base_dir: Path):
    a_path = base_dir / pair["a_file"]
    b_path = base_dir / pair["b_file"]

    a_keep = KEEP_MAP[pair["a_file"]]
    b_keep = KEEP_MAP[pair["b_file"]]

    rows_a = read_and_filter(a_path, a_keep, offset=0)
    rows_b = read_and_filter(b_path, b_keep, offset=OFFSET_B_SECONDS)

    print(f"{pair['a_file']}: {len(rows_a)} rows (ライラ from A)")
    print(f"{pair['b_file']}: {len(rows_b)} rows (石川 from B)")

    # Merge and sort by start time
    all_rows = rows_a + rows_b
    all_rows.sort(key=lambda r: (r["start"], r["speaker"]))

    # Merge consecutive same-speaker entries
    merged = merge_consecutive(all_rows, gap_threshold=2)
    print(f"After merge: {merged[0]['speaker']}...{merged[-1]['speaker']} ({len(merged)} rows)")

    # Write CSV
    output_path = base_dir / pair["output"]
    color_map = {"石川": "Violet", "ライラ": "Rose"}
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"])
        for r in merged:
            writer.writerow([
                r["speaker"],
                fmt_tc(r["start"]),
                fmt_tc(r["end"]),
                r["text"],
                color_map.get(r["speaker"], "Lavender"),
            ])
    print(f"Output: {output_path} ({len(merged)} rows)\n")


def main():
    base = Path("031radio/separatetranscript")
    out_base = Path("031radio")

    for pair in PAIRS:
        pair_with_outdir = pair.copy()
        # Read from separatetranscript, write to 031radio
        a_path = base / pair["a_file"]
        b_path = base / pair["b_file"]

        a_keep = KEEP_MAP[pair["a_file"]]
        b_keep = KEEP_MAP[pair["b_file"]]

        rows_a = read_and_filter(a_path, a_keep, offset=0)
        rows_b = read_and_filter(b_path, b_keep, offset=OFFSET_B_SECONDS)

        print(f"{pair['a_file']}: {len(rows_a)} rows (from A mic)")
        print(f"{pair['b_file']}: {len(rows_b)} rows (from B mic)")

        all_rows = rows_a + rows_b
        all_rows.sort(key=lambda r: (r["start"], r["speaker"]))

        merged = merge_consecutive(all_rows, gap_threshold=2)

        output_path = out_base / pair["output"]
        color_map = {"石川": "Violet", "ライラ": "Rose"}
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"])
            for r in merged:
                writer.writerow([
                    r["speaker"],
                    fmt_tc(r["start"]),
                    fmt_tc(r["end"]),
                    r["text"],
                    color_map.get(r["speaker"], "Lavender"),
                ])
        print(f"Output: {output_path} ({len(merged)} rows)\n")


if __name__ == "__main__":
    main()
