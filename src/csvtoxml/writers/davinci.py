"""DaVinci Resolve FCPXML writer."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.dom import minidom

from ..core.parser import parse_csv
from ..core.segment import build_segments
from ..core.timecode import get_fps_from_rate


# DaVinci Resolve clip colors (FCPXML)
DAVINCI_COLORS = [
    "orange", "yellow", "green", "cyan", "blue", "purple", "pink", "red",
    "maroon", "rose", "lavender", "sand", "sepia", "mint", "olive", "violet", "peach"
]

# Map Premiere Pro labels to DaVinci clip colors
PREMIERE_TO_DAVINCI = {
    "Violet": "violet",
    "Rose": "rose",
    "Mango": "orange",
    "Yellow": "yellow",
    "Lavender": "lavender",
    "Caribbean": "cyan",
    "Tan": "sand",
    "Forest": "green",
    "Blue": "blue",
    "Purple": "purple",
    "Teal": "cyan",
    "Brown": "sepia",
    "Gray": "sand",
    "Iris": "violet",
    "Cerulean": "blue",
    "Magenta": "pink",
}

# Direct color name mapping
COLOR_TO_DAVINCI = {
    "violet": "violet",
    "rose": "rose",
    "pink": "pink",
    "cyan": "cyan",
    "blue": "blue",
    "mint": "mint",
    "green": "green",
    "yellow": "yellow",
    "orange": "orange",
    "red": "red",
    "purple": "purple",
    "brown": "sepia",
    "gray": "sand",
    "lavender": "lavender",
    "tan": "sand",
    "teal": "cyan",
    "magenta": "pink",
    "forest": "green",
    "iris": "violet",
    "cerulean": "blue",
    "caribbean": "cyan",
    "mango": "orange",
    "peach": "peach",
    "olive": "olive",
    "maroon": "maroon",
    "sand": "sand",
    "sepia": "sepia",
}


def color_to_davinci(color: str) -> str:
    """Convert color name to DaVinci Resolve clip color.

    Args:
        color: Color name from CSV or Premiere label

    Returns:
        Valid DaVinci Resolve clip color
    """
    if not color or color.strip() == "":
        return "blue"

    # Check Premiere label names first
    if color in PREMIERE_TO_DAVINCI:
        return PREMIERE_TO_DAVINCI[color]

    # Check direct color names
    color_lower = color.lower()
    if color_lower in COLOR_TO_DAVINCI:
        return COLOR_TO_DAVINCI[color_lower]

    # Check if already a valid DaVinci color
    if color_lower in DAVINCI_COLORS:
        return color_lower

    return "blue"  # Default


def _frames_to_rational(frames: int, fps: float) -> str:
    """Convert frames to FCPXML rational time format.

    FCPXML uses rational numbers like "1001/24000s" for timing.
    For simplicity, we use frames * timebase as numerator.

    Args:
        frames: Frame count
        fps: Frames per second

    Returns:
        Rational time string (e.g., "24024/24000s")
    """
    # Use 24000 as common denominator for NTSC compatibility
    if abs(fps - 23.976) < 0.01:
        return f"{frames * 1001}/24000s"
    elif abs(fps - 29.97) < 0.01:
        return f"{frames * 1001}/30000s"
    elif abs(fps - 59.94) < 0.01:
        return f"{frames * 1001}/60000s"
    else:
        # For integer frame rates (24, 25, 30, etc.)
        timebase = int(round(fps))
        return f"{frames}/{timebase}s"


def extract_media_info(xml_path: Path) -> Dict[str, Any]:
    """Extract media information from template XML.

    Args:
        xml_path: Path to template XMEML file

    Returns:
        Dict with fps, timebase, ntsc, media_name
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    info: Dict[str, Any] = {
        "timebase": 24,
        "ntsc": False,
        "media_name": xml_path.stem,
    }

    # Try to find rate info
    sequence = root.find("sequence")
    if sequence is not None:
        rate = sequence.find("rate")
        if rate is not None:
            tb = rate.find("timebase")
            ntsc = rate.find("ntsc")
            if tb is not None and tb.text:
                info["timebase"] = int(tb.text)
            if ntsc is not None and ntsc.text:
                info["ntsc"] = ntsc.text.strip().upper() == "TRUE"

        name = sequence.find("name")
        if name is not None and name.text:
            info["media_name"] = name.text

    info["fps"] = get_fps_from_rate(info["timebase"], info["ntsc"])
    return info


def generate_davinci_xml(
    csv_path: Path | str,
    template_xml_path: Path | str,
    output_path: Optional[Path | str] = None,
    gap_seconds: float = 5.0,
) -> Path:
    """Generate DaVinci Resolve FCPXML timeline from CSV.

    Args:
        csv_path: Path to timeline CSV file
        template_xml_path: Path to template XML file (for FPS info)
        output_path: Output XML path (auto-generated if not provided)
        gap_seconds: Gap duration between blocks in seconds

    Returns:
        Path to generated FCPXML file
    """
    csv_path = Path(csv_path)
    template_xml_path = Path(template_xml_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not template_xml_path.exists():
        raise FileNotFoundError(f"Template XML not found: {template_xml_path}")

    # Extract media info from template
    media_info = extract_media_info(template_xml_path)
    fps = media_info["fps"]
    timebase = media_info["timebase"]
    ntsc = media_info["ntsc"]
    media_name = media_info["media_name"]

    print(f"テンプレート情報: {timebase}fps {'NTSC' if ntsc else ''}")

    gap_frames = int(round(fps * gap_seconds))

    # Parse CSV and build segments
    rows = parse_csv(csv_path)
    segments, warnings = build_segments(rows, fps)

    blocks = [s for s in segments if not s.is_gap]
    gaps = [s for s in segments if s.is_gap]
    print(f"検出: ブロック {len(blocks)}個 / ギャップ {len(gaps)}個")

    for warning in warnings:
        print(f"警告: {warning}")

    # Calculate timeline duration and track offsets
    # Build timeline positions first
    timeline_positions = []
    timeline_position = 0

    for seg in segments:
        if seg.is_gap:
            timeline_position += seg.duration_frames
        else:
            timeline_position += gap_frames
            timeline_positions.append({
                "start": timeline_position,
                "duration": seg.duration_frames,
                "source_start": seg.start_frames,
                "color": seg.color,
            })
            timeline_position += seg.duration_frames

    total_duration = timeline_position

    # Create FCPXML structure
    fcpxml = ET.Element("fcpxml", version="1.10")

    # Resources
    resources = ET.SubElement(fcpxml, "resources")

    # Format resource
    format_id = f"r1"
    format_elem = ET.SubElement(resources, "format",
        id=format_id,
        name=f"FFVideoFormat{timebase}p",
        frameDuration=_frames_to_rational(1, fps),
        width="1920",
        height="1080",
    )

    # Asset resource (placeholder for source media)
    asset_id = "r2"
    asset = ET.SubElement(resources, "asset",
        id=asset_id,
        name=media_name,
        start="0s",
        duration=_frames_to_rational(total_duration + 10000, fps),
        hasVideo="1",
        hasAudio="1",
        format=format_id,
    )
    media_rep = ET.SubElement(asset, "media-rep",
        kind="original-media",
        src=f"file:///placeholder/{media_name}.mov",
    )

    # Library
    library = ET.SubElement(fcpxml, "library")

    # Event
    event = ET.SubElement(library, "event", name=f"{csv_path.stem}_event")

    # Project
    project = ET.SubElement(event, "project", name=f"{csv_path.stem}_cut")

    # Sequence
    sequence = ET.SubElement(project, "sequence",
        format=format_id,
        duration=_frames_to_rational(total_duration, fps),
        tcStart="0s",
        tcFormat="NDF" if not ntsc else "DF",
    )

    # Spine (main timeline container)
    spine = ET.SubElement(sequence, "spine")

    # Add clips
    clip_index = 0
    for pos_info in timeline_positions:
        clip_index += 1

        # Add gap before clip if not first
        if clip_index == 1 and pos_info["start"] > 0:
            gap_elem = ET.SubElement(spine, "gap",
                name="Gap",
                duration=_frames_to_rational(pos_info["start"], fps),
            )
        elif clip_index > 1:
            # Calculate gap between previous clip end and this clip start
            prev_end = timeline_positions[clip_index - 2]["start"] + timeline_positions[clip_index - 2]["duration"]
            gap_duration = pos_info["start"] - prev_end
            if gap_duration > 0:
                gap_elem = ET.SubElement(spine, "gap",
                    name="Gap",
                    duration=_frames_to_rational(gap_duration, fps),
                )

        # Create clip with color
        davinci_color = color_to_davinci(pos_info["color"] or "")

        # Note: DaVinci Resolve reads clipColor from the keyword element
        clip = ET.SubElement(spine, "clip",
            name=f"{media_name}_{clip_index:03d}",
            ref=asset_id,
            duration=_frames_to_rational(pos_info["duration"], fps),
            start=_frames_to_rational(pos_info["source_start"], fps),
        )

        # Add keyword with color (DaVinci reads this for clip color)
        keyword = ET.SubElement(clip, "keyword",
            value=davinci_color,
        )

        # Add note with color info (DaVinci reads this)
        note = ET.SubElement(clip, "note")
        note.text = f"Color: {davinci_color}"

        # Add marker with color
        marker = ET.SubElement(clip, "marker",
            start="0s",
            duration=_frames_to_rational(1, fps),
            value=davinci_color,
        )

    # Generate output path
    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_davinci.fcpxml"
    else:
        output_path = Path(output_path)

    # Write FCPXML
    xml_string = _prettify_fcpxml(fcpxml)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(xml_string)

    print(f"\nFCPXML generated: {output_path}")
    return output_path


def _prettify_fcpxml(elem: ET.Element) -> str:
    """Return pretty-printed FCPXML string."""
    rough_string = ET.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    xml_string = reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")

    # FCPXML doesn't need DOCTYPE
    return xml_string
