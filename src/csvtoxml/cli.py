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
            # DaVinci Resolve support (to be implemented)
            print("DaVinci Resolve format not yet implemented", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
