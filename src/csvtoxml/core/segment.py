"""Segment building from CSV rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .parser import CsvRow
from .timecode import timecode_to_frames


@dataclass
class Segment:
    """Represents a timeline segment (block or gap)."""

    kind: str  # "block" or "gap"
    start_frames: int
    end_frames: int
    color: Optional[str] = None
    transcript: Optional[str] = None
    raw_rows: List[CsvRow] = field(default_factory=list)

    @property
    def duration_frames(self) -> int:
        """Get segment duration in frames."""
        return max(0, self.end_frames - self.start_frames)

    @property
    def is_gap(self) -> bool:
        """Check if this segment is a gap."""
        return self.kind == "gap"

    @property
    def gap_label(self) -> Optional[str]:
        """Extract gap label from color field."""
        if not self.is_gap or not self.color:
            return None
        if "_" in self.color:
            return self.color.split("_", 1)[1]
        return self.color


def build_segments(
    rows: List[CsvRow],
    fps: float
) -> Tuple[List[Segment], List[str]]:
    """Build timeline segments from CSV rows.

    Groups consecutive rows with the same color into blocks.
    GAP rows become gap segments.

    Args:
        rows: List of CsvRow objects from parse_csv
        fps: Frames per second for timecode conversion

    Returns:
        Tuple of (segments list, warnings list)
    """
    segments: List[Segment] = []
    warnings: List[str] = []
    current_color: Optional[str] = None
    current_block: Optional[Segment] = None

    for row in rows:
        color = row.color

        # Handle GAP rows
        if row.is_gap:
            # Save current block if exists
            if current_block is not None:
                segments.append(current_block)
                current_block = None
                current_color = None

            # Validate gap timecodes
            if not row.in_timecode or not row.out_timecode:
                warnings.append(f"GAP row missing timecodes: {row}")
                continue

            start = timecode_to_frames(row.in_timecode, fps)
            end = timecode_to_frames(row.out_timecode, fps)

            if end <= start:
                warnings.append(f"GAP out point <= in point: {row}")
                continue

            segments.append(
                Segment(
                    kind="gap",
                    start_frames=start,
                    end_frames=end,
                    color=color,
                    transcript=row.transcript,
                    raw_rows=[row],
                )
            )
            continue

        # Handle block rows
        if not row.in_timecode or not row.out_timecode or not color:
            warnings.append(f"Block row missing required fields: {row}")
            continue

        in_frames = timecode_to_frames(row.in_timecode, fps)
        out_frames = timecode_to_frames(row.out_timecode, fps)

        if out_frames <= in_frames:
            warnings.append(f"Out point <= in point: {row}")
            continue

        # Start new block if color changed
        if current_color != color:
            if current_block is not None:
                segments.append(current_block)

            current_color = color
            current_block = Segment(
                kind="block",
                start_frames=in_frames,
                end_frames=out_frames,
                color=color,
                transcript=row.transcript,
                raw_rows=[row],
            )
        else:
            # Extend current block
            assert current_block is not None
            current_block.end_frames = out_frames
            current_block.raw_rows.append(row)

    # Don't forget the last block
    if current_block is not None:
        segments.append(current_block)

    return segments, warnings
