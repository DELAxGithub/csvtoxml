#!/usr/bin/env python3
"""
036radio: ミックスCSVのタイムコードに対して、ワイヤレスA/BマイクCSVの
文字起こしテキストを合体させるスクリプト。

- ミックスCSVのタイムコード構造（行・話者・イン/アウト点）を維持
- 各行の時間範囲に重なるワイヤレスCSVセグメントのテキストを結合
- 話者に応じて適切なマイクを優先（大坪→Amic、D→Bmic、しんめい→両方比較）
- 個別マイクの1セグメントが複数ミックス行にまたがる場合、最も重なりが大きい行にのみ割り当て
"""

import csv
import re
from pathlib import Path

PARTS = [
    ("036_1.csv", "00084_Amic.wav.csv", "00101_Bmic.wav.csv"),
    ("036_2.csv", "00085_Amic.wav.csv", "00102_Bmic.wav.csv"),
    ("036_3.csv", "00086_Amic.wav.csv", "00103_Bmic.wav.csv"),
]

SPEAKER_MIC_PRIORITY = {
    "大坪": "amic",
    "D": "bmic",
    "しんめい": "both",
    "話者": "amic",
}

BASE = Path(__file__).parent


def parse_tc_mix(tc_str: str) -> int:
    """00;00;04;04 → フレーム数 (30fps)"""
    parts = tc_str.strip('"').replace(";", ":").split(":")
    h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return ((h * 3600 + m * 60 + s) * 30) + f


def parse_tc_abs(tc_str: str) -> int:
    """13:07:18:18 → フレーム数 (30fps)"""
    parts = tc_str.strip('"').split(":")
    h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return ((h * 3600 + m * 60 + s) * 30) + f


def read_csv(filepath: Path) -> list[dict]:
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def calc_offset(mix_rows, amic_rows, bmic_rows) -> int:
    mix_start = parse_tc_mix(mix_rows[0]["Start Time"])
    amic_start = parse_tc_abs(amic_rows[0]["Start Time"])
    bmic_start = parse_tc_abs(bmic_rows[0]["Start Time"])
    return min(amic_start, bmic_start) - mix_start


def get_speaker_base(speaker: str) -> str:
    return speaker.strip('"').rstrip("!").rstrip("0123456789")


def get_priority_mic(speaker_base: str) -> str:
    for key, mic in SPEAKER_MIC_PRIORITY.items():
        if speaker_base.startswith(key):
            return mic
    return "both"


def build_assignment(mix_frames, offset, ind_rows, parse_fn) -> dict[int, str]:
    """
    個別マイクの各セグメントを、最も重なりが大きいミックス行に割り当てる。
    戻り値: {mix_row_index: text}
    """
    assignments: dict[int, str] = {}

    for ind_row in ind_rows:
        text = ind_row["Text"].strip('"').strip()
        if not text or len(text) <= 1:
            continue

        seg_start = parse_fn(ind_row["Start Time"])
        seg_end = parse_fn(ind_row["End Time"])

        # このセグメントと重なる全ミックス行を探し、最大重なりの行に割り当て
        best_idx = -1
        best_overlap = 0

        for i, (mix_start, mix_end) in enumerate(mix_frames):
            abs_start = mix_start + offset
            abs_end = mix_end + offset

            overlap_start = max(abs_start, seg_start)
            overlap_end = min(abs_end, seg_end)
            overlap = overlap_end - overlap_start

            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i

        if best_idx >= 0 and best_overlap > 0:
            # 既に割り当て済みの場合、テキストを連結
            if best_idx in assignments:
                assignments[best_idx] += " " + text
            else:
                assignments[best_idx] = text

    return assignments


def process_part(mix_file, amic_file, bmic_file):
    mix_rows = read_csv(BASE / mix_file)
    amic_rows = read_csv(BASE / amic_file)
    bmic_rows = read_csv(BASE / bmic_file)

    offset = calc_offset(mix_rows, amic_rows, bmic_rows)
    print(f"  Offset: {offset} frames ({offset/30:.1f}s)")

    # ミックス行のフレーム範囲を事前計算
    mix_frames = []
    for row in mix_rows:
        mix_frames.append((parse_tc_mix(row["Start Time"]), parse_tc_mix(row["End Time"])))

    # 個別マイクの各セグメントをミックス行に割り当て
    amic_assignments = build_assignment(mix_frames, offset, amic_rows, parse_tc_abs)
    bmic_assignments = build_assignment(mix_frames, offset, bmic_rows, parse_tc_abs)

    print(f"  Amic assigned: {len(amic_assignments)}/{len(mix_rows)} rows")
    print(f"  Bmic assigned: {len(bmic_assignments)}/{len(mix_rows)} rows")

    output_rows = []
    for i, row in enumerate(mix_rows):
        speaker = row["Speaker Name"].strip('"')
        start_tc = row["Start Time"]
        end_tc = row["End Time"]
        mix_text = row["Text"].strip('"')

        speaker_base = get_speaker_base(speaker)
        priority = get_priority_mic(speaker_base)

        amic_text = amic_assignments.get(i, "")
        bmic_text = bmic_assignments.get(i, "")

        # 優先マイクに基づいてテキスト選択
        if priority == "amic":
            merged_text = amic_text or bmic_text or mix_text
        elif priority == "bmic":
            merged_text = bmic_text or amic_text or mix_text
        else:  # both → 長い方
            if amic_text and bmic_text:
                merged_text = amic_text if len(amic_text) >= len(bmic_text) else bmic_text
            else:
                merged_text = amic_text or bmic_text or mix_text

        # タイムコード形式統一
        start_out = start_tc.strip('"').replace(";", ":")
        end_out = end_tc.strip('"').replace(";", ":")

        # 話者名クリーンアップ
        clean_speaker = re.sub(r"\d+$", "", speaker)

        # 色選択
        if speaker_base.startswith("大坪"):
            color = "Lavender"
        elif speaker_base.startswith("D"):
            color = "Violet"
        elif speaker_base.startswith("しんめい"):
            color = "Rose"
        else:
            color = "Lavender"

        output_rows.append({
            "Speaker Name": clean_speaker,
            "イン点": start_out,
            "アウト点": end_out,
            "文字起こし": merged_text,
            "色選択": color,
        })

    return output_rows


def write_output(rows, filename):
    filepath = BASE / filename
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {filepath.name} ({len(rows)} rows)")


def main():
    for i, (mix_file, amic_file, bmic_file) in enumerate(PARTS, 1):
        print(f"\n=== Part {i}: {mix_file} ===")
        rows = process_part(mix_file, amic_file, bmic_file)
        out_name = mix_file.replace(".csv", "_.csv")
        write_output(rows, out_name)


if __name__ == "__main__":
    main()
