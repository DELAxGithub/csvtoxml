#!/usr/bin/env python3
"""
荒編済み CSV (__S.csv) → DaVinci タイムライン用 SRT を生成する self-contained CLI。

DaVinci の自動文字起こしの代替として、Whisper 由来の高精度文字起こし
（既に CSV の「文字起こし」列に入っている）を、`csv_to_resolve_timeline.py`
が組むタイムライン TC に**射影**して SRT 化する。

数学的には csv_to_resolve_timeline.py の build_blocks() と同じ写像を使う:
  - 同色の連続行を 1 ブロックに集約（block.in = first.in, block.out = last.out）
  - GAP_N 行はギャップとして TC 累積
  - rec_pos += block.dur あるいは gap.dur で累積
  - 各行の SRT TC = rec_offset + block_rec_start + (row.in - block.first_in)

build_blocks() を直したらこちらも合わせる必要がある。

Usage:
    python srt_from_csv.py <csv_path> [-o OUT] [--fps 25] [--start-tc 01:00:00:00]
                                      [--no-speaker] [--source-tc]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def tc_to_seconds(tc: str, fps: int) -> float:
    """HH:MM:SS:FF → 秒。csv_to_resolve_timeline.py:28-31 と同形。"""
    parts = tc.strip().replace(";", ":").split(":")
    h, m, s, f = map(int, parts)
    return h * 3600 + m * 60 + s + f / fps


def seconds_to_srt_tc(sec: float) -> str:
    """秒 → HH:MM:SS,mmm（SRT 標準形式）。"""
    if sec < 0:
        sec = 0.0
    total_ms = int(round(sec * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_text(row: dict, *, with_speaker: bool) -> str:
    text = (row.get("文字起こし") or "").strip()
    speaker = (row.get("Speaker Name") or "").strip()
    if with_speaker and speaker:
        return f"[{speaker}] {text}"
    return text


def project_to_timeline(
    rows: list[dict], *, fps: int, start_tc: str
) -> list[tuple[float, float, dict]]:
    """各行を (srt_in_sec, srt_out_sec, row) に射影する。

    GAP 行は出力しない（ただし rec_pos には加算される）。
    色変化点を新ブロック先頭として扱う。
    """
    rec_offset = tc_to_seconds(start_tc, fps)
    rec_pos = 0.0
    block_first_in: float | None = None
    block_rec_start: float | None = None
    prev_color: str | None = None

    out: list[tuple[float, float, dict]] = []
    for row in rows:
        color = (row.get("色選択") or "").strip()
        try:
            in_sec = tc_to_seconds(row["イン点"], fps)
            out_sec = tc_to_seconds(row["アウト点"], fps)
        except (KeyError, ValueError):
            continue

        if color.startswith("GAP"):
            rec_pos += out_sec - in_sec
            prev_color = None
            block_first_in = None
            block_rec_start = None
            continue

        if color != prev_color or block_first_in is None:
            block_first_in = in_sec
            block_rec_start = rec_pos
            prev_color = color

        row_offset = in_sec - block_first_in
        srt_in = rec_offset + block_rec_start + row_offset
        srt_out = srt_in + (out_sec - in_sec)
        out.append((srt_in, srt_out, row))

        rec_pos = block_rec_start + (out_sec - block_first_in)

    return out


def project_source_tc(
    rows: list[dict], *, fps: int, start_tc: str
) -> list[tuple[float, float, dict]]:
    """--source-tc モード: 元 TC をそのまま start_tc 起点で SRT 化（歯抜け XML 配置向け）。"""
    rec_offset = tc_to_seconds(start_tc, fps)
    out: list[tuple[float, float, dict]] = []
    for row in rows:
        color = (row.get("色選択") or "").strip()
        if color.startswith("GAP"):
            continue
        try:
            in_sec = tc_to_seconds(row["イン点"], fps)
            out_sec = tc_to_seconds(row["アウト点"], fps)
        except (KeyError, ValueError):
            continue
        out.append((rec_offset + in_sec, rec_offset + out_sec, row))
    return out


def write_srt(
    entries: list[tuple[float, float, dict]],
    *,
    output_path: Path,
    with_speaker: bool,
) -> int:
    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for srt_in, srt_out, row in entries:
            text = format_text(row, with_speaker=with_speaker)
            if not text:
                continue
            if srt_out <= srt_in:
                srt_out = srt_in + 0.5
            written += 1
            f.write(f"{written}\n")
            f.write(f"{seconds_to_srt_tc(srt_in)} --> {seconds_to_srt_tc(srt_out)}\n")
            f.write(f"{text}\n\n")
    return written


def main() -> int:
    p = argparse.ArgumentParser(
        prog="srt_from_csv",
        description="荒編済み CSV を DaVinci タイムライン用 SRT に変換する",
    )
    p.add_argument("csv_path", type=Path, help="入力 __S.csv")
    p.add_argument("-o", "--output", type=Path, default=None, help="出力 SRT パス（既定: <stem>.srt）")
    p.add_argument("--fps", type=int, default=25, help="CSV の TC fps（既定: 25）")
    p.add_argument(
        "--start-tc",
        default="01:00:00:00",
        help="タイムライン起点 TC（既定: 01:00:00:00）",
    )
    p.add_argument("--no-speaker", action="store_true", help="話者名を字幕に前置しない")
    p.add_argument(
        "--source-tc",
        action="store_true",
        help="ブロック詰めをせず、ソース TC をそのまま起点 TC からの相対で書き出す（歯抜け XML 配置用）",
    )
    args = p.parse_args()

    if not args.csv_path.exists():
        print(f"ERROR: CSV not found: {args.csv_path}", file=sys.stderr)
        return 1

    with args.csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"ERROR: empty CSV: {args.csv_path}", file=sys.stderr)
        return 1

    required = {"Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"ERROR: CSV missing columns: {sorted(missing)}", file=sys.stderr)
        return 1

    if args.source_tc:
        entries = project_source_tc(rows, fps=args.fps, start_tc=args.start_tc)
    else:
        entries = project_to_timeline(rows, fps=args.fps, start_tc=args.start_tc)

    output = args.output or args.csv_path.with_suffix(".srt")
    written = write_srt(entries, output_path=output, with_speaker=not args.no_speaker)
    mode = "source-tc" if args.source_tc else "timeline-tc"
    print(f"wrote {written} entries → {output}  (mode: {mode}, fps: {args.fps}, start: {args.start_tc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
