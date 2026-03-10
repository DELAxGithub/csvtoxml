"""Command-line interface for csvtoxml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="csvtoxml",
        description="Convert CSV timeline to NLE XML (Premiere Pro / DaVinci Resolve)",
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to timeline CSV file",
    )

    parser.add_argument(
        "template_xml",
        type=Path,
        help="Path to template XML file",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output XML path (auto-generated if not specified)",
    )

    parser.add_argument(
        "-f", "--format",
        choices=["premiere", "davinci"],
        default="premiere",
        help="Output format (default: premiere)",
    )

    parser.add_argument(
        "-g", "--gap",
        type=float,
        default=5.0,
        help="Gap duration between blocks in seconds (default: 5.0)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args()

    # Validate input files
    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}", file=sys.stderr)
        return 1

    if not args.template_xml.exists():
        print(f"Error: Template XML not found: {args.template_xml}", file=sys.stderr)
        return 1

    try:
        if args.format == "premiere":
            from csvtoxml.writers.premiere import generate_premiere_xml

            generate_premiere_xml(
                csv_path=args.csv_file,
                template_xml_path=args.template_xml,
                output_path=args.output,
                gap_seconds=args.gap,
            )
        else:
            from csvtoxml.writers.davinci import generate_davinci_xml

            generate_davinci_xml(
                csv_path=args.csv_file,
                template_xml_path=args.template_xml,
                output_path=args.output,
                gap_seconds=args.gap,
            )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def prep_main() -> int:
    """CLI entry point for CSV preprocessing (replaces GAS workflow)."""
    parser = argparse.ArgumentParser(
        prog="csvtoxml-prep",
        description="Preprocess raw Premiere Pro transcript CSVs for csvtoxml",
    )

    subparsers = parser.add_subparsers(dest="command", help="Preprocessing commands")

    # --- merge: Step 1A (two CSVs) ---
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge 2 raw transcript CSVs into formatted CSV (Step 1A)",
    )
    merge_parser.add_argument("csv_a", type=Path, help="First transcript CSV")
    merge_parser.add_argument("csv_b", type=Path, help="Second transcript CSV")
    merge_parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output formatted CSV path (auto-generated if not specified)",
    )

    # --- single: Step 1B (one CSV) ---
    single_parser = subparsers.add_parser(
        "single",
        help="Format a single raw transcript CSV (Step 1B)",
    )
    single_parser.add_argument("csv_file", type=Path, help="Transcript CSV")
    single_parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output formatted CSV path (auto-generated if not specified)",
    )

    # --- extract: Step 2+3 (colored rows -> final CSV) ---
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract colored rows and generate final CSV (Step 2+3)",
    )
    extract_parser.add_argument(
        "formatted_csv", type=Path,
        help="Formatted CSV with 色選択 column filled in",
    )
    extract_parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output final CSV path (auto-generated if not specified)",
    )

    # --- whisper-merge: Premiere + Whisper A/B mic merge ---
    wm_parser = subparsers.add_parser(
        "whisper-merge",
        help="Merge Premiere CSV with Whisper A/B mic CSVs (replace text with Whisper)",
    )
    wm_parser.add_argument("premiere_csv", type=Path, help="Premiere transcript CSV (with speaker names + frame TC)")
    wm_parser.add_argument("whisper_a", type=Path, help="Whisper transcript from mic A")
    wm_parser.add_argument("whisper_b", type=Path, help="Whisper transcript from mic B")
    wm_parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output formatted CSV path (auto-generated if not specified)",
    )
    wm_parser.add_argument(
        "--offset", type=float, default=0.0,
        help="Time offset in seconds to add to Whisper TCs (default: 0.0)",
    )
    wm_parser.add_argument(
        "--speaker-a", type=str, default=None,
        help="Premiere speaker name who wears mic A (auto-detected if not specified)",
    )
    wm_parser.add_argument(
        "--speaker-b", type=str, default=None,
        help="Premiere speaker name who wears mic B (auto-detected if not specified)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "merge":
            _cmd_merge(args)
        elif args.command == "single":
            _cmd_single(args)
        elif args.command == "extract":
            _cmd_extract(args)
        elif args.command == "whisper-merge":
            _cmd_whisper_merge(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def _cmd_merge(args: argparse.Namespace) -> None:
    from csvtoxml.core.preprocessor import merge_two_transcripts, write_formatted_csv

    for p in [args.csv_a, args.csv_b]:
        if not p.exists():
            raise FileNotFoundError(f"CSV file not found: {p}")

    data, main_a, main_b = merge_two_transcripts(args.csv_a, args.csv_b)

    output = args.output
    if output is None:
        stem_a = args.csv_a.stem
        stem_b = args.csv_b.stem
        output = args.csv_a.parent / f"{stem_a}_AND_{stem_b}_formatted.csv"

    write_formatted_csv(data, output)
    print(f"Formatted CSV: {output}")
    print(f"  Speaker A: {main_a or '(none)'}")
    print(f"  Speaker B: {main_b or '(none)'}")
    print(f"  Rows: {len(data) - 1}")
    print(f"\nNext: edit 色選択 column in the CSV, then run:")
    print(f"  csvtoxml-prep extract {output}")


def _cmd_single(args: argparse.Namespace) -> None:
    from csvtoxml.core.preprocessor import format_single_transcript, write_formatted_csv

    if not args.csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {args.csv_file}")

    data, main_a, main_b = format_single_transcript(args.csv_file)

    output = args.output
    if output is None:
        output = args.csv_file.parent / f"{args.csv_file.stem}_formatted.csv"

    write_formatted_csv(data, output)
    print(f"Formatted CSV: {output}")
    print(f"  Speaker A: {main_a or '(none)'}")
    print(f"  Speaker B: {main_b or '(none)'}")
    print(f"  Rows: {len(data) - 1}")
    print(f"\nNext: edit 色選択 column in the CSV, then run:")
    print(f"  csvtoxml-prep extract {output}")


def _cmd_extract(args: argparse.Namespace) -> None:
    from csvtoxml.core.extractor import preprocess_to_final

    if not args.formatted_csv.exists():
        raise FileNotFoundError(f"CSV file not found: {args.formatted_csv}")

    output = args.output
    if output is None:
        output = args.formatted_csv.parent / f"{args.formatted_csv.stem}_final.csv"

    result = preprocess_to_final(args.formatted_csv, output)
    print(f"Final CSV: {result}")
    print(f"\nReady for XML generation:")
    print(f"  csvtoxml {result} <template.xml>")


def _cmd_whisper_merge(args: argparse.Namespace) -> None:
    from csvtoxml.core.preprocessor import merge_with_whisper, write_formatted_csv

    for p in [args.premiere_csv, args.whisper_a, args.whisper_b]:
        if not p.exists():
            raise FileNotFoundError(f"CSV file not found: {p}")

    data, main_a, main_b = merge_with_whisper(
        args.premiere_csv, args.whisper_a, args.whisper_b,
        speaker_a=args.speaker_a,
        speaker_b=args.speaker_b,
        offset_seconds=args.offset,
    )

    output = args.output
    if output is None:
        output = args.premiere_csv.parent / f"{args.premiere_csv.stem}_whisper_merged.csv"

    write_formatted_csv(data, output)
    print(f"Whisper-merged CSV: {output}")
    print(f"  Speaker A (mic A): {main_a or '(none)'}")
    print(f"  Speaker B (mic B): {main_b or '(none)'}")
    print(f"  Rows: {len(data) - 1}")
    print(f"\nColumns: 色選択, イン点, アウト点, スピーカーネーム, スピーカーAの文字起こし, スピーカーBの文字起こし, AやB以外")
    print(f"Next: edit 色選択 column in the CSV, then run:")
    print(f"  csvtoxml-prep extract {output}")


if __name__ == "__main__":
    sys.exit(main())
