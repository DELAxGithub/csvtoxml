"""Extract colored rows and generate final CSV for the csvtoxml pipeline.

Replaces GAS Step 2 + Step 3:
- Step 2: Extract rows with 色選択 filled in, insert NA separators between color changes
- Step 3: Convert NA rows to GAP rows with computed timecodes
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List, Optional

from csvtoxml.core.timecode import frames_to_timecode
from csvtoxml.core.preprocessor import STEP1_HEADERS, FPS, GAP_CLIP_DURATION_FRAMES

# Final output headers (matches csvtoxml parser.py TARGET_HEADERS)
TARGET_HEADERS = ["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"]


def _read_csv(csv_path: Path) -> List[List[str]]:
    """Read CSV and return all rows including header."""
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        return list(reader)


def _find_col(headers: List[str], *candidates: str) -> int:
    """Find column index from candidate names."""
    for c in candidates:
        if c in headers:
            return headers.index(c)
    return -1


def _get_text_value(row: List[str], text_cols: List[int]) -> str:
    """Get first non-empty text value from candidate columns."""
    for idx in text_cols:
        if idx != -1 and idx < len(row):
            val = row[idx].strip()
            if val:
                return val
    return ""


def extract_colored_rows(formatted_csv: Path) -> List[List[str]]:
    """Read formatted CSV and extract rows with 色選択 filled in.

    Inserts NA separator rows between groups of different colors.

    Args:
        formatted_csv: Path to the 7-column formatted CSV (STEP1_HEADERS)

    Returns:
        Rows in TARGET_HEADERS format (including header row)
    """
    data = _read_csv(formatted_csv)
    if len(data) < 2:
        raise ValueError("CSV has no data rows")

    headers = data[0]
    color_col = _find_col(headers, "色選択")
    in_col = _find_col(headers, "イン点")
    out_col = _find_col(headers, "アウト点")
    speaker_col = _find_col(headers, "スピーカーネーム", "Speaker Name")

    # Text columns (priority order: A > B > Other > legacy)
    text_col_a = _find_col(headers, "スピーカーAの文字起こし")
    text_col_b = _find_col(headers, "スピーカーBの文字起こし")
    text_col_other = _find_col(headers, "AやB以外")
    text_col_legacy = _find_col(headers, "文字起こし")
    text_cols = [text_col_a, text_col_b, text_col_other, text_col_legacy]

    if color_col == -1:
        raise ValueError("色選択 column not found in CSV")

    # Filter to rows with color assigned
    colored_rows = []
    for row in data[1:]:
        if color_col < len(row) and row[color_col].strip():
            colored_rows.append(row)

    if not colored_rows:
        raise ValueError("No rows with 色選択 assigned")

    # Build output with NA separators
    result = [TARGET_HEADERS]
    na_counter = 1

    for i, current in enumerate(colored_rows):
        # Build output row
        out_row = [""] * len(TARGET_HEADERS)
        if speaker_col != -1 and speaker_col < len(current):
            out_row[TARGET_HEADERS.index("Speaker Name")] = current[speaker_col].strip()
        if in_col != -1 and in_col < len(current):
            out_row[TARGET_HEADERS.index("イン点")] = current[in_col].strip()
        if out_col != -1 and out_col < len(current):
            out_row[TARGET_HEADERS.index("アウト点")] = current[out_col].strip()
        out_row[TARGET_HEADERS.index("文字起こし")] = _get_text_value(current, text_cols)
        if color_col < len(current):
            out_row[TARGET_HEADERS.index("色選択")] = current[color_col].strip()

        result.append(out_row)

        # Insert NA separator if next row has a different color
        if i < len(colored_rows) - 1:
            current_color = current[color_col].strip() if color_col < len(current) else ""
            next_color = colored_rows[i + 1][color_col].strip() if color_col < len(colored_rows[i + 1]) else ""
            if current_color != next_color:
                na_row = [""] * len(TARGET_HEADERS)
                na_row[TARGET_HEADERS.index("Speaker Name")] = f"NA{na_counter}"
                result.append(na_row)
                na_counter += 1

    return result


def generate_final_csv(
    selected_data: List[List[str]],
    output_path: Path,
    gap_duration_seconds: int = 20,
    fps: int = 30,
) -> Path:
    """Convert NA/blank rows to GAP rows and write final CSV.

    Args:
        selected_data: Rows in TARGET_HEADERS format (including header)
        output_path: Where to write the final CSV
        gap_duration_seconds: Gap duration in seconds (default: 20)
        fps: Frame rate (default: 30)

    Returns:
        Path to the output CSV
    """
    if len(selected_data) < 2:
        raise ValueError("No data rows to process")

    headers = selected_data[0]
    speaker_idx = _find_col(headers, "Speaker Name", "スピーカーネーム")
    in_idx = _find_col(headers, "イン点")
    out_idx = _find_col(headers, "アウト点")
    text_idx = _find_col(headers, "文字起こし")
    color_idx = _find_col(headers, "色選択")

    # Text columns for formatted CSV input
    text_col_a = _find_col(headers, "スピーカーAの文字起こし")
    text_col_b = _find_col(headers, "スピーカーBの文字起こし")
    text_col_other = _find_col(headers, "AやB以外")
    extra_text_cols = [text_col_a, text_col_b, text_col_other]

    padding_frames = 149
    gap_clip_frames = (gap_duration_seconds * fps) - (padding_frames * 2)
    gap_out_tc = frames_to_timecode(gap_clip_frames, float(fps))

    final_rows = [TARGET_HEADERS]
    gap_counter = 0

    for row in selected_data[1:]:
        # Check if row is blank or NA
        all_blank = all(cell.strip() == "" for cell in row)
        speaker_val = row[speaker_idx].strip() if speaker_idx != -1 and speaker_idx < len(row) else ""
        is_na = bool(re.match(r"^NA\d+$", speaker_val, re.IGNORECASE))

        if all_blank or is_na:
            gap_counter += 1
            gap_row = [""] * len(TARGET_HEADERS)
            gap_row[TARGET_HEADERS.index("イン点")] = "00:00:00:00"
            gap_row[TARGET_HEADERS.index("アウト点")] = gap_out_tc

            # Try to preserve any text from the row
            telop = ""
            if text_idx != -1 and text_idx < len(row) and row[text_idx].strip():
                telop = row[text_idx].strip()
            else:
                telop = _get_text_value(row, extra_text_cols)
            gap_row[TARGET_HEADERS.index("文字起こし")] = telop or f"--- {gap_duration_seconds}s GAP ---"
            gap_row[TARGET_HEADERS.index("色選択")] = f"GAP_{gap_counter}"
            final_rows.append(gap_row)
            continue

        # Normal row
        in_tc = row[in_idx].strip().replace(";", ":") if in_idx != -1 and in_idx < len(row) else ""
        out_tc = row[out_idx].strip().replace(";", ":") if out_idx != -1 and out_idx < len(row) else ""
        if not in_tc or not out_tc:
            continue

        text_val = ""
        if text_idx != -1 and text_idx < len(row) and row[text_idx].strip():
            text_val = row[text_idx].strip()
        else:
            text_val = _get_text_value(row, extra_text_cols)

        out_row = [""] * len(TARGET_HEADERS)
        out_row[TARGET_HEADERS.index("Speaker Name")] = speaker_val
        out_row[TARGET_HEADERS.index("イン点")] = in_tc
        out_row[TARGET_HEADERS.index("アウト点")] = out_tc
        out_row[TARGET_HEADERS.index("文字起こし")] = text_val
        color_val = row[color_idx].strip() if color_idx != -1 and color_idx < len(row) else ""
        out_row[TARGET_HEADERS.index("色選択")] = color_val
        final_rows.append(out_row)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(final_rows)

    return output_path


def preprocess_to_final(formatted_csv: Path, output_path: Path) -> Path:
    """Run extract + generate in one call.

    Reads the formatted CSV (after manual color assignment),
    extracts colored rows, converts NA→GAP, writes final CSV.

    Args:
        formatted_csv: Path to the 7-column formatted CSV with colors assigned
        output_path: Where to write the final CSV

    Returns:
        Path to the output CSV
    """
    selected_data = extract_colored_rows(formatted_csv)
    return generate_final_csv(selected_data, output_path)
