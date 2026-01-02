"""CSV parsing utilities."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# Expected CSV headers
TARGET_HEADERS = [
    "Speaker Name",
    "イン点",
    "アウト点",
    "文字起こし",
    "色選択",
]


class CsvFormatError(ValueError):
    """Raised when CSV format is invalid."""
    pass


@dataclass
class CsvRow:
    """Represents a single row from the timeline CSV."""

    speaker: str
    in_timecode: str
    out_timecode: str
    transcript: str
    color: str

    @property
    def is_gap(self) -> bool:
        """Check if this row represents a gap."""
        return self.color.upper().startswith("GAP") if self.color else False

    @property
    def gap_label(self) -> Optional[str]:
        """Extract gap label (e.g., '1' from 'GAP_1')."""
        if not self.is_gap:
            return None
        if "_" in self.color:
            return self.color.split("_", 1)[1]
        return self.color


def parse_csv(csv_path: Path | str) -> List[CsvRow]:
    """Parse timeline CSV file into CsvRow objects.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of CsvRow objects

    Raises:
        CsvFormatError: If required headers are missing
        FileNotFoundError: If CSV file doesn't exist
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows: List[CsvRow] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Validate headers
        if reader.fieldnames is None:
            raise CsvFormatError("CSV file is empty or has no headers")

        missing = [h for h in TARGET_HEADERS if h not in reader.fieldnames]
        if missing:
            raise CsvFormatError(f"Missing required headers: {missing}")

        for raw in reader:
            if not raw:
                continue

            speaker = (raw.get("Speaker Name") or "").strip()
            in_tc = (raw.get("イン点") or "").strip()
            out_tc = (raw.get("アウト点") or "").strip()
            text = (raw.get("文字起こし") or "").strip()
            color = (raw.get("色選択") or "").strip()

            # Skip completely empty rows
            if not in_tc and not out_tc and not color:
                continue

            rows.append(
                CsvRow(
                    speaker=speaker,
                    in_timecode=in_tc,
                    out_timecode=out_tc,
                    transcript=text,
                    color=color,
                )
            )

    return rows
