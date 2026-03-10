"""
Pre-cleanup of raw dialogue merge: remove echoes, merge fragments, filter MC.
Outputs chunked files for Claude agent processing.
"""

import csv
import json
from pathlib import Path
from difflib import SequenceMatcher


def read_raw_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def tc_to_sec(tc: str) -> int:
    """HH:MM:SS:FF → seconds"""
    parts = tc.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def sec_to_tc(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}:00"


def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def is_short_interjection(text: str) -> bool:
    """Check if text is a short interjection/backchanneling."""
    clean = text.strip().replace("。", "").replace("、", "").replace("?", "").replace(" ", "")
    short_phrases = {
        "うん", "ん", "はい", "なるほど", "そうですね", "そうなんですか",
        "いいですね", "そうですよね", "ほんとだ", "へえ", "へぇ", "ねー",
        "そうですか", "面白い", "なるほどなるほど", "はいはい", "はいはいはい",
        "そうなんですね", "素晴らしい", "本当だ", "いいね",
    }
    return clean in short_phrases or len(clean) <= 4


def clean_dialogue(rows: list[dict]) -> list[dict]:
    """Remove echoes, MC misattributions, and handle overlaps."""
    cleaned = []

    # First pass: mark echoes for removal
    skip = set()
    for i in range(len(rows)):
        if i in skip:
            continue
        r = rows[i]
        start_i = tc_to_sec(r["イン点"])
        end_i = tc_to_sec(r["アウト点"])

        # Look ahead for echo/duplicate within 3 seconds
        for j in range(i + 1, min(i + 5, len(rows))):
            if j in skip:
                continue
            r2 = rows[j]
            start_j = tc_to_sec(r2["イン点"])

            # Only compare if overlapping or very close in time
            if start_j - end_i > 3:
                break

            # Different speakers saying the same thing → echo
            if r["Speaker Name"] != r2["Speaker Name"]:
                sim = text_similarity(r["文字起こし"], r2["文字起こし"])
                if sim > 0.6:
                    # Keep the longer/more detailed one
                    if len(r["文字起こし"]) >= len(r2["文字起こし"]):
                        skip.add(j)
                    else:
                        skip.add(i)
                        break

        # Check for short interjection overlapping with substantive speech
        if i not in skip and is_short_interjection(r["文字起こし"]):
            # Check if there's a longer overlapping line by the other speaker
            for j in range(max(0, i - 2), min(i + 3, len(rows))):
                if j == i or j in skip:
                    continue
                r2 = rows[j]
                if r2["Speaker Name"] == r["Speaker Name"]:
                    continue
                start_j = tc_to_sec(r2["イン点"])
                end_j = tc_to_sec(r2["アウト点"])
                # Overlapping time ranges
                if start_i < end_j and start_j < end_i:
                    if len(r2["文字起こし"]) > 20:
                        # Short interjection during long speech → remove
                        skip.add(i)
                        break

    # Build cleaned list
    for i, r in enumerate(rows):
        if i in skip:
            continue
        cleaned.append(r)

    # Second pass: merge consecutive same-speaker lines
    merged = []
    for r in cleaned:
        if merged and merged[-1]["Speaker Name"] == r["Speaker Name"]:
            prev = merged[-1]
            prev_end = tc_to_sec(prev["アウト点"])
            cur_start = tc_to_sec(r["イン点"])
            if cur_start - prev_end <= 3:
                prev["アウト点"] = r["アウト点"]
                prev["文字起こし"] += " " + r["文字起こし"]
                continue
        merged.append(dict(r))

    return merged


def split_chunks(rows: list[dict], chunk_minutes: int = 8) -> list[list[dict]]:
    """Split rows into time-based chunks."""
    chunks = []
    current = []
    chunk_start = 0

    for r in rows:
        start = tc_to_sec(r["イン点"])
        if start >= chunk_start + chunk_minutes * 60 and current:
            chunks.append(current)
            current = []
            chunk_start = start
        current.append(r)

    if current:
        chunks.append(current)
    return chunks


def write_chunk(chunk: list[dict], path: Path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"])
        writer.writeheader()
        writer.writerows(chunk)


def main():
    base = Path("031radio")
    out_dir = base / "chunks"
    out_dir.mkdir(exist_ok=True)

    for raw_file, prefix in [
        ("031_1_dialogue_raw.csv", "1"),
        ("031_2_dialogue_raw.csv", "2"),
    ]:
        rows = read_raw_csv(base / raw_file)
        print(f"\n{raw_file}: {len(rows)} rows")

        cleaned = clean_dialogue(rows)
        print(f"After cleanup: {len(cleaned)} rows (removed {len(rows) - len(cleaned)})")

        # Write full cleaned file
        write_chunk(cleaned, base / f"031_{prefix}_dialogue_clean.csv")

        # Split into chunks
        chunks = split_chunks(cleaned, chunk_minutes=8)
        for i, chunk in enumerate(chunks):
            chunk_path = out_dir / f"chunk_{prefix}_{i+1}.csv"
            write_chunk(chunk, chunk_path)
            start_tc = chunk[0]["イン点"]
            end_tc = chunk[-1]["アウト点"]
            print(f"  Chunk {i+1}: {len(chunk)} rows ({start_tc} - {end_tc})")

        # Also write as JSON for easy agent consumption
        chunk_data = []
        for i, chunk in enumerate(chunks):
            chunk_data.append({
                "chunk_id": i + 1,
                "start": chunk[0]["イン点"],
                "end": chunk[-1]["アウト点"],
                "rows": chunk,
            })
        with open(out_dir / f"chunks_{prefix}.json", "w", encoding="utf-8") as f:
            json.dump(chunk_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
