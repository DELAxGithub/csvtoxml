"""Preprocess raw Premiere Pro transcript CSVs for the csvtoxml pipeline.

Replaces the GAS (Google Apps Script) Step 1 workflow:
- Reads raw Premiere CSV(s) with columns: Speaker Name, Start Time, End Time, Text
- Identifies main speakers (A/B) by frequency
- Merges multiple CSVs and sorts by timecode
- Outputs a 7-column formatted CSV for manual color assignment
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from csvtoxml.core.timecode import timecode_to_frames, FPS_30

# Flexible header matching for raw Premiere CSVs
RAW_HEADER_CANDIDATES = {
    "speaker": ["Speaker Name", "Speaker", "スピーカー", "話者"],
    "start": ["Start Time", "Start", "Start Timestamp", "In", "イン点", "イン"],
    "end": ["End Time", "End", "End Timestamp", "アウト点", "アウト"],
    "text": ["Text", "Transcript", "Transcription", "文字起こし", "テキスト"],
}

# Output headers for the formatted (7-column) intermediate CSV
STEP1_HEADERS = [
    "色選択",
    "イン点",
    "アウト点",
    "スピーカーネーム",
    "スピーカーAの文字起こし",
    "スピーカーBの文字起こし",
    "AやB以外",
]

# Premiere Pro label colors
VALID_COLORS = [
    "Violet", "Rose", "Mango", "Yellow", "Lavender", "Caribbean",
    "Tan", "Forest", "Blue", "Purple", "Teal", "Brown", "Gray",
    "Iris", "Cerulean", "Magenta",
]

# Gap calculation constants (matching gas.js)
FPS = 30
GAP_DURATION_SECONDS = 20
PADDING_FRAMES = 149
GAP_CLIP_DURATION_FRAMES = (GAP_DURATION_SECONDS * FPS) - (PADDING_FRAMES * 2)  # 302


def _find_header_index(headers: List[str], candidates: List[str]) -> int:
    """Find column index by matching against candidate header names (case-insensitive)."""
    normalized = [h.strip().lower() if h else "" for h in headers]
    for cand in candidates:
        target = cand.strip().lower()
        if target in normalized:
            return normalized.index(target)
    return -1


def _detect_delimiter(csv_path: Path) -> str:
    """Auto-detect CSV delimiter (comma or semicolon) from the header line."""
    with csv_path.open(encoding="utf-8-sig") as f:
        first_line = f.readline()
    if ";" in first_line and "," not in first_line:
        return ";"
    return ","


def _read_raw_csv(csv_path: Path) -> Tuple[List[str], List[List[str]]]:
    """Read a raw CSV file and return (headers, data_rows).

    Auto-detects comma vs semicolon delimiter.
    """
    delimiter = _detect_delimiter(csv_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        headers = next(reader, [])
        data = list(reader)
    return headers, data


def _get_column_indices(headers: List[str]) -> Tuple[int, int, int, int]:
    """Find speaker, start, end, text column indices. Raises ValueError if missing."""
    speaker_col = _find_header_index(headers, RAW_HEADER_CANDIDATES["speaker"])
    start_col = _find_header_index(headers, RAW_HEADER_CANDIDATES["start"])
    end_col = _find_header_index(headers, RAW_HEADER_CANDIDATES["end"])
    text_col = _find_header_index(headers, RAW_HEADER_CANDIDATES["text"])

    if -1 in (speaker_col, start_col, end_col, text_col):
        missing = []
        for name, idx in [("Speaker", speaker_col), ("Start", start_col),
                          ("End", end_col), ("Text", text_col)]:
            if idx == -1:
                missing.append(name)
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}. "
            f"Expected headers like: Speaker Name, Start Time, End Time, Text"
        )
    return speaker_col, start_col, end_col, text_col


def _get_top_speakers(data: List[List[str]], speaker_col: int, limit: int) -> List[str]:
    """Return top N speakers by frequency."""
    counter = Counter()
    for row in data:
        if speaker_col < len(row):
            speaker = row[speaker_col].strip()
            if speaker:
                counter[speaker] += 1
    return [name for name, _ in counter.most_common(limit)]


def merge_two_transcripts(
    csv_a: Path, csv_b: Path, fps: float = FPS_30
) -> Tuple[List[List[str]], str, str]:
    """Merge 2 raw Premiere CSVs into STEP1_HEADERS format.

    Args:
        csv_a: Path to first transcript CSV
        csv_b: Path to second transcript CSV
        fps: Frame rate for timecode sorting (default: 30.0)

    Returns:
        (rows_with_headers, mainA_name, mainB_name)
        rows_with_headers includes STEP1_HEADERS as the first row.
    """
    headers_a, data_a = _read_raw_csv(csv_a)
    headers_b, data_b = _read_raw_csv(csv_b)

    sp_a, start_a, end_a, text_a = _get_column_indices(headers_a)
    sp_b, start_b, end_b, text_b = _get_column_indices(headers_b)

    main_a = (_get_top_speakers(data_a, sp_a, 1) or [""])[0]
    main_b = (_get_top_speakers(data_b, sp_b, 1) or [""])[0]

    # Build merged rows with origin tag
    merged = []
    for row in data_a:
        if start_a >= len(row):
            continue
        merged.append({
            "origin": "A",
            "in": row[start_a].replace(";", ":") if start_a < len(row) else "",
            "out": row[end_a].replace(";", ":") if end_a < len(row) else "",
            "sp": row[sp_a].strip() if sp_a < len(row) else "",
            "text": row[text_a].strip() if text_a < len(row) else "",
        })
    for row in data_b:
        if start_b >= len(row):
            continue
        merged.append({
            "origin": "B",
            "in": row[start_b].replace(";", ":") if start_b < len(row) else "",
            "out": row[end_b].replace(";", ":") if end_b < len(row) else "",
            "sp": row[sp_b].strip() if sp_b < len(row) else "",
            "text": row[text_b].strip() if text_b < len(row) else "",
        })

    # Sort by in-timecode
    merged.sort(key=lambda item: timecode_to_frames(item["in"], fps))

    # Build output rows
    result = [STEP1_HEADERS]
    for item in merged:
        row = [""] * len(STEP1_HEADERS)
        row[STEP1_HEADERS.index("イン点")] = item["in"]
        row[STEP1_HEADERS.index("アウト点")] = item["out"]
        row[STEP1_HEADERS.index("スピーカーネーム")] = item["sp"]

        if item["origin"] == "A":
            if main_a and item["sp"] == main_a:
                row[STEP1_HEADERS.index("スピーカーAの文字起こし")] = item["text"]
            else:
                row[STEP1_HEADERS.index("AやB以外")] = item["text"]
        else:
            if main_b and item["sp"] == main_b:
                row[STEP1_HEADERS.index("スピーカーBの文字起こし")] = item["text"]
            else:
                row[STEP1_HEADERS.index("AやB以外")] = item["text"]

        result.append(row)

    return result, main_a, main_b


def format_single_transcript(
    csv_path: Path, fps: float = FPS_30
) -> Tuple[List[List[str]], str, str]:
    """Format a single raw Premiere CSV into STEP1_HEADERS format.

    Args:
        csv_path: Path to transcript CSV
        fps: Frame rate for timecode sorting (default: 30.0)

    Returns:
        (rows_with_headers, mainA_name, mainB_name)
        rows_with_headers includes STEP1_HEADERS as the first row.
    """
    headers, data = _read_raw_csv(csv_path)
    sp_col, start_col, end_col, text_col = _get_column_indices(headers)

    top_speakers = _get_top_speakers(data, sp_col, 2)
    main_a = top_speakers[0] if len(top_speakers) > 0 else ""
    main_b = top_speakers[1] if len(top_speakers) > 1 else ""

    result = [STEP1_HEADERS]
    for row in data:
        if start_col >= len(row):
            continue
        out_row = [""] * len(STEP1_HEADERS)
        out_row[STEP1_HEADERS.index("イン点")] = row[start_col].replace(";", ":") if start_col < len(row) else ""
        out_row[STEP1_HEADERS.index("アウト点")] = row[end_col].replace(";", ":") if end_col < len(row) else ""
        speaker = row[sp_col].strip() if sp_col < len(row) else ""
        out_row[STEP1_HEADERS.index("スピーカーネーム")] = speaker
        text = row[text_col].strip() if text_col < len(row) else ""

        if main_a and speaker == main_a:
            out_row[STEP1_HEADERS.index("スピーカーAの文字起こし")] = text
        elif main_b and speaker == main_b:
            out_row[STEP1_HEADERS.index("スピーカーBの文字起こし")] = text
        else:
            out_row[STEP1_HEADERS.index("AやB以外")] = text

        result.append(out_row)

    return result, main_a, main_b


def _tc_to_seconds(tc: str) -> float:
    """Convert timecode string to seconds (approximate, for matching purposes).

    Handles:
      HH:MM:SS:FF  (Premiere, frame-accurate)
      MM:SS        (Whisper, second-level)
      HH:MM:SS     (rare)
    """
    if not tc:
        return 0.0
    parts = tc.replace(";", ":").split(":")
    parts = [int(p) for p in parts if p.strip().isdigit()]
    if len(parts) == 4:  # HH:MM:SS:FF
        return parts[0] * 3600 + parts[1] * 60 + parts[2] + parts[3] / 30.0
    elif len(parts) == 3:  # HH:MM:SS or MM:SS:FF — disambiguate
        if parts[0] >= 24:  # likely MM:SS:FF
            return parts[0] * 60 + parts[1] + parts[2] / 30.0
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:  # MM:SS
        return parts[0] * 60 + parts[1]
    return 0.0


def _collect_whisper_texts(
    whisper_rows: List[List[str]],
    start_col: int,
    end_col: int,
    text_col: int,
    start_sec: float,
    end_sec: float,
) -> str:
    """Collect and join Whisper texts whose midpoint falls within a time range.

    Uses midpoint matching: a Whisper segment is included if its midpoint
    falls within the Premiere segment's time range (with 0.5s tolerance).

    Args:
        whisper_rows: All data rows (no header)
        start_col, end_col, text_col: Column indices
        start_sec, end_sec: Time range to match (in seconds)

    Returns:
        Joined text from matching Whisper rows
    """
    tolerance = 0.5
    matched = []
    for row in whisper_rows:
        if text_col >= len(row):
            continue
        w_start = _tc_to_seconds(row[start_col]) if start_col < len(row) else 0.0
        w_end = _tc_to_seconds(row[end_col]) if end_col < len(row) else 0.0
        text = row[text_col].strip() if text_col < len(row) else ""
        if not text:
            continue

        # Midpoint matching: include if Whisper segment's midpoint
        # falls within the Premiere segment (+/- tolerance)
        w_mid = (w_start + w_end) / 2.0
        if (start_sec - tolerance) <= w_mid <= (end_sec + tolerance):
            matched.append(text)

    return " ".join(matched)


def merge_with_whisper(
    premiere_csv: Path,
    whisper_a_csv: Path,
    whisper_b_csv: Path,
    speaker_a: Optional[str] = None,
    speaker_b: Optional[str] = None,
    offset_seconds: float = 0.0,
    fps: float = FPS_30,
) -> Tuple[List[List[str]], str, str]:
    """Merge Premiere CSV with Whisper mic CSVs, replacing transcription text.

    Keeps Premiere's timecodes and speaker identification.
    Routes Whisper text to the correct column based on speaker-mic mapping:
      - Speaker A's rows → column E (スピーカーAの文字起こし) gets Whisper A text
      - Speaker B's rows → column F (スピーカーBの文字起こし) gets Whisper B text
      - Other speakers   → column G (AやB以外) gets Premiere original text

    Output uses STEP1_HEADERS format for compatibility with the GAS workflow.

    Args:
        premiere_csv: Premiere Pro transcript CSV (with speaker names + frame-accurate TC)
        whisper_a_csv: Whisper transcript from mic A
        whisper_b_csv: Whisper transcript from mic B
        speaker_a: Premiere speaker name who wears mic A (auto-detected if None)
        speaker_b: Premiere speaker name who wears mic B (auto-detected if None)
        offset_seconds: Time offset to add to Whisper TCs to align with Premiere
        fps: Frame rate (default: 30.0)

    Returns:
        (rows_with_headers, mainA_name, mainB_name) where A/B are Premiere speaker names
    """
    # Read Premiere CSV
    pr_headers, pr_data = _read_raw_csv(premiere_csv)
    pr_sp, pr_start, pr_end, pr_text = _get_column_indices(pr_headers)

    # Read Whisper CSVs
    wa_headers, wa_data = _read_raw_csv(whisper_a_csv)
    wb_headers, wb_data = _read_raw_csv(whisper_b_csv)
    _, wa_start, wa_end, wa_text = _get_column_indices(wa_headers)
    _, wb_start, wb_end, wb_text = _get_column_indices(wb_headers)

    # Identify main speakers from Premiere (top 2 by frequency)
    top_speakers = _get_top_speakers(pr_data, pr_sp, 2)
    main_a = speaker_a or (top_speakers[0] if len(top_speakers) > 0 else "")
    main_b = speaker_b or (top_speakers[1] if len(top_speakers) > 1 else "")

    result = [STEP1_HEADERS]
    for row in pr_data:
        if pr_start >= len(row):
            continue

        in_tc = row[pr_start].replace(";", ":") if pr_start < len(row) else ""
        out_tc = row[pr_end].replace(";", ":") if pr_end < len(row) else ""
        speaker = row[pr_sp].strip() if pr_sp < len(row) else ""
        pr_text_val = row[pr_text].strip() if pr_text < len(row) else ""

        start_sec = _tc_to_seconds(in_tc) - offset_seconds
        end_sec = _tc_to_seconds(out_tc) - offset_seconds

        out_row = [""] * len(STEP1_HEADERS)
        out_row[STEP1_HEADERS.index("イン点")] = in_tc
        out_row[STEP1_HEADERS.index("アウト点")] = out_tc
        out_row[STEP1_HEADERS.index("スピーカーネーム")] = speaker

        if main_a and speaker == main_a:
            # Speaker A's row → use Whisper A mic text
            whisper_text = _collect_whisper_texts(
                wa_data, wa_start, wa_end, wa_text, start_sec, end_sec
            )
            out_row[STEP1_HEADERS.index("スピーカーAの文字起こし")] = whisper_text or pr_text_val
        elif main_b and speaker == main_b:
            # Speaker B's row → use Whisper B mic text
            whisper_text = _collect_whisper_texts(
                wb_data, wb_start, wb_end, wb_text, start_sec, end_sec
            )
            out_row[STEP1_HEADERS.index("スピーカーBの文字起こし")] = whisper_text or pr_text_val
        else:
            # Other speaker (MC etc.) → keep Premiere text as fallback
            out_row[STEP1_HEADERS.index("AやB以外")] = pr_text_val

        result.append(out_row)

    return result, main_a, main_b


def write_formatted_csv(data: List[List[str]], output_path: Path) -> Path:
    """Write the 7-column formatted CSV.

    Args:
        data: Rows including header row (from merge/format functions)
        output_path: Where to write the CSV

    Returns:
        The output path
    """
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return output_path
