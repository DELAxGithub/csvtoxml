"""Premiere Pro XMEML XML writer."""

from __future__ import annotations

import os
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.dom import minidom

from ..core.parser import parse_csv
from ..core.segment import Segment, build_segments
from ..core.timecode import frames_to_ppro_ticks, get_fps_from_rate


# Valid Premiere Pro label colors
VALID_LABELS = [
    "Violet", "Rose", "Mango", "Yellow", "Lavender", "Caribbean",
    "Tan", "Forest", "Blue", "Purple", "Teal", "Brown", "Gray",
    "Iris", "Cerulean", "Magenta"
]

# Legacy color name mapping for backwards compatibility
LEGACY_COLOR_MAP = {
    "rose": "Rose",
    "pink": "Rose",
    "cyan": "Caribbean",
    "blue": "Blue",
    "mint": "Mango",
    "green": "Forest",
    "yellow": "Yellow",
    "orange": "Mango",
    "red": "Rose",
    "purple": "Purple",
    "brown": "Brown",
    "gray": "Gray",
    "lavender": "Lavender",
    "tan": "Tan",
    "teal": "Teal",
    "magenta": "Magenta",
    "violet": "Violet",
    "forest": "Forest",
    "iris": "Iris",
    "cerulean": "Cerulean",
    "caribbean": "Caribbean",
    "mango": "Mango"
}


def color_to_premiere_label(color: str) -> str:
    """Convert color name to Premiere Pro label.

    Args:
        color: Color name from CSV

    Returns:
        Valid Premiere Pro label name
    """
    if not color or color.strip() == "":
        return "Caribbean"

    if color in VALID_LABELS:
        return color

    return LEGACY_COLOR_MAP.get(color.lower(), "Caribbean")


def find_media_file(
    media_files: List[Dict[str, Any]],
    file_name: Optional[str],
    track_idx: int
) -> Dict[str, Any]:
    """Find media file by name or fall back to track index.

    Args:
        media_files: List of media file info dicts
        file_name: Optional file name to search for
        track_idx: Track index for fallback

    Returns:
        Media file info dict
    """
    if file_name:
        # Try exact match first
        for mf in media_files:
            if mf.get("name") == file_name:
                return mf
        # Try case-insensitive match
        file_name_lower = file_name.lower()
        for mf in media_files:
            if mf.get("name", "").lower() == file_name_lower:
                return mf
        # Try partial match (contains)
        for mf in media_files:
            if file_name in mf.get("name", ""):
                return mf

    # Fall back to track index
    return media_files[min(track_idx, len(media_files) - 1)]


def _ensure_element(parent: ET.Element, tag: str) -> ET.Element:
    """Ensure an XML child element exists, create if not."""
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    return child


def _deep_copy(element: Optional[ET.Element]) -> Optional[ET.Element]:
    """Create a deep copy of an XML element."""
    if element is None:
        return None
    return ET.fromstring(ET.tostring(element))


def _parse_int(text: Any) -> Optional[int]:
    """Safely parse integer from text."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def extract_media_files(xml_path: Path) -> List[Dict[str, Any]]:
    """Extract media file information from template XML.

    Args:
        xml_path: Path to template XML file

    Returns:
        List of media file info dicts
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    media_files: List[Dict[str, Any]] = []
    seen_names: set = set()

    for clipitem in root.findall(".//clipitem"):
        file_elem = clipitem.find("file")
        if file_elem is None:
            continue

        name_elem = file_elem.find("name")
        pathurl_elem = file_elem.find("pathurl")

        file_id = file_elem.get("id")
        full_file_elem = file_elem

        if file_id:
            found = root.find(f".//media/file[@id='{file_id}']")
            if found is not None:
                full_file_elem = found

        if full_file_elem is not None:
            if name_elem is None:
                name_elem = full_file_elem.find("name")
            if pathurl_elem is None:
                pathurl_elem = full_file_elem.find("pathurl")

        if name_elem is None or pathurl_elem is None:
            continue

        name = name_elem.text
        if name is None or name in seen_names:
            continue

        file_info: Dict[str, Any] = {
            "name": name,
            "pathurl": pathurl_elem.text,
            "element": full_file_elem,
        }

        duration_elem = full_file_elem.find("duration") if full_file_elem is not None else None
        if duration_elem is not None and duration_elem.text and duration_elem.text.isdigit():
            file_info["source_duration"] = int(duration_elem.text)

        if file_id is None and full_file_elem is not None:
            file_id = full_file_elem.get("id")
        if file_id:
            file_info["file_id"] = file_id

        masterclipid_elem = clipitem.find("masterclipid")
        if masterclipid_elem is not None and masterclipid_elem.text:
            file_info["masterclipid"] = masterclipid_elem.text

        seen_names.add(name)
        media_files.append(file_info)

    return media_files


def generate_premiere_xml(
    csv_path: Path | str,
    template_xml_path: Path | str,
    output_path: Optional[Path | str] = None,
    gap_seconds: float = 5.0,
) -> Path:
    """Generate Premiere Pro XMEML timeline from CSV and template.

    Args:
        csv_path: Path to timeline CSV file
        template_xml_path: Path to template XML file
        output_path: Output XML path (auto-generated if not provided)
        gap_seconds: Gap duration between blocks in seconds

    Returns:
        Path to generated XML file

    Raises:
        FileNotFoundError: If input files don't exist
        ValueError: If template has no media files
    """
    csv_path = Path(csv_path)
    template_xml_path = Path(template_xml_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not template_xml_path.exists():
        raise FileNotFoundError(f"Template XML not found: {template_xml_path}")

    # Extract media from template
    media_files = extract_media_files(template_xml_path)
    if not media_files:
        raise ValueError("No media files found in template XML")

    print(f"XMLから抽出したファイル: {len(media_files)}個")
    for i, mf in enumerate(media_files):
        print(f"  {i+1}: {mf['name']}")

    # Parse template
    template_tree = ET.parse(template_xml_path)
    template_root = template_tree.getroot()
    template_sequence = template_root.find("sequence")

    if template_sequence is None:
        raise ValueError("No sequence found in template XML")

    # Get timeline FPS from template
    template_rate = template_sequence.find("rate")
    timebase = 30
    ntsc = True

    if template_rate is not None:
        tb_elem = template_rate.find("timebase")
        ntsc_elem = template_rate.find("ntsc")
        if tb_elem is not None and tb_elem.text:
            timebase = int(tb_elem.text)
        if ntsc_elem is not None and ntsc_elem.text:
            ntsc = ntsc_elem.text.strip().upper() == "TRUE"

    fps = get_fps_from_rate(timebase, ntsc)
    gap_frames = int(round(fps * gap_seconds))

    # Parse CSV and build segments
    rows = parse_csv(csv_path)
    segments, warnings = build_segments(rows, fps)

    blocks = [s for s in segments if not s.is_gap]
    gaps = [s for s in segments if s.is_gap]
    print(f"検出: ブロック {len(blocks)}個 / ギャップ {len(gaps)}個")

    for warning in warnings:
        print(f"警告: {warning}")

    # Create new XML
    root = ET.Element("xmeml", version="4")
    sequence = ET.SubElement(root, "sequence")

    # Copy sequence attributes
    for attr_name, attr_value in template_sequence.attrib.items():
        sequence.set(attr_name, attr_value)

    # Generate new UUID
    uuid_elem = ET.SubElement(sequence, "uuid")
    uuid_elem.text = str(uuid.uuid4())

    # Duration placeholder
    duration_elem = ET.SubElement(sequence, "duration")
    duration_elem.text = "0"

    # Copy rate
    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(timebase)
    ET.SubElement(rate, "ntsc").text = "TRUE" if ntsc else "FALSE"

    # Sequence name
    name_elem = ET.SubElement(sequence, "name")
    name_elem.text = f"{csv_path.stem}_cut"

    # Media container
    template_media = template_sequence.find("media")
    media = ET.SubElement(sequence, "media")

    template_video = template_media.find("video") if template_media is not None else None
    template_audio = template_media.find("audio") if template_media is not None else None

    video = ET.SubElement(media, "video")
    audio = ET.SubElement(media, "audio")

    # Copy format info (excluding tracks)
    if template_video is not None:
        for child in template_video:
            if child.tag != "track":
                copied = _deep_copy(child)
                if copied is not None:
                    video.append(copied)

    if template_audio is not None:
        for child in template_audio:
            if child.tag != "track":
                copied = _deep_copy(child)
                if copied is not None:
                    audio.append(copied)

    # Find max clipitem ID to avoid collisions
    id_re = re.compile(r"clipitem-(\d+)")
    max_clip_num = 0
    for ci in template_root.findall(".//clipitem"):
        cid = ci.get("id") or ""
        m = id_re.match(cid)
        if m:
            max_clip_num = max(max_clip_num, int(m.group(1)))
    next_clip_num = max_clip_num + 1

    # Build track sources from template
    template_video_tracks = template_video.findall("track") if template_video is not None else []
    template_audio_tracks = template_audio.findall("track") if template_audio is not None else []

    used_file_ids: set = set()
    max_timeline_end = 0

    # Process video tracks
    for track_idx, template_track in enumerate(template_video_tracks):
        template_clipitems = list(template_track.findall("clipitem"))

        if not template_clipitems:
            copied = _deep_copy(template_track)
            if copied is not None:
                video.append(copied)
            continue

        track = ET.SubElement(video, "track")
        for attr_name, attr_value in template_track.attrib.items():
            track.set(attr_name, attr_value)

        default_clipitem = template_clipitems[0]

        timeline_position = 0

        for seg in segments:
            if seg.is_gap:
                timeline_position += seg.duration_frames
                continue

            timeline_position += gap_frames

            start_frames = seg.start_frames
            duration_frames = seg.duration_frames

            # Find appropriate media file for this segment
            file_info = find_media_file(media_files, seg.file_name, track_idx)

            clipitem = _deep_copy(default_clipitem) or ET.Element("clipitem")
            clipitem.set("id", f"clipitem-{next_clip_num}")
            track.append(clipitem)

            # Remove existing links
            for link in list(clipitem.findall("link")):
                clipitem.remove(link)

            # Set clip properties
            _ensure_element(clipitem, "masterclipid").text = file_info.get("masterclipid", f"masterclip-v{track_idx + 1}")
            _ensure_element(clipitem, "name").text = file_info.get("name", f"Video Track {track_idx + 1}")
            _ensure_element(clipitem, "enabled").text = "TRUE"

            _ensure_element(clipitem, "start").text = str(timeline_position)
            _ensure_element(clipitem, "end").text = str(timeline_position + duration_frames)
            _ensure_element(clipitem, "in").text = str(start_frames)
            _ensure_element(clipitem, "out").text = str(start_frames + duration_frames)
            _ensure_element(clipitem, "pproTicksIn").text = str(frames_to_ppro_ticks(start_frames, fps))
            _ensure_element(clipitem, "pproTicksOut").text = str(frames_to_ppro_ticks(start_frames + duration_frames, fps))

            # File reference
            file_id = file_info.get("file_id")
            existing_files = clipitem.findall("file")
            if existing_files:
                file_elem = existing_files[0]
                for extra in existing_files[1:]:
                    clipitem.remove(extra)
            else:
                file_elem = ET.SubElement(clipitem, "file")

            if file_id:
                file_elem.set("id", file_id)
                if file_id not in used_file_ids:
                    file_elem.clear()
                    file_elem.set("id", file_id)
                    src_elem = file_info.get("element")
                    if src_elem is not None:
                        for child in src_elem:
                            copied = _deep_copy(child)
                            if copied is not None:
                                file_elem.append(copied)
                    used_file_ids.add(file_id)
                else:
                    for child in list(file_elem):
                        file_elem.remove(child)

            # Label
            labels = _ensure_element(clipitem, "labels")
            label2 = _ensure_element(labels, "label2")
            label2.text = color_to_premiere_label(seg.color or "")

            timeline_position += duration_frames
            if timeline_position > max_timeline_end:
                max_timeline_end = timeline_position
            next_clip_num += 1

        # Copy non-clipitem children
        for child in template_track:
            if child.tag != "clipitem":
                copied = _deep_copy(child)
                if copied is not None:
                    track.append(copied)

    # Process audio tracks
    for track_idx, template_track in enumerate(template_audio_tracks):
        template_clipitems = list(template_track.findall("clipitem"))

        if not template_clipitems:
            copied = _deep_copy(template_track)
            if copied is not None:
                audio.append(copied)
            continue

        track = ET.SubElement(audio, "track")
        for attr_name, attr_value in template_track.attrib.items():
            track.set(attr_name, attr_value)

        default_clipitem = template_clipitems[0]
        source_channel = 1 if track_idx % 2 == 0 else 2

        timeline_position = 0

        for seg in segments:
            if seg.is_gap:
                timeline_position += seg.duration_frames
                continue

            timeline_position += gap_frames

            start_frames = seg.start_frames
            duration_frames = seg.duration_frames

            # Find appropriate media file for this segment
            file_info = find_media_file(media_files, seg.file_name, track_idx)

            clipitem = _deep_copy(default_clipitem) or ET.Element("clipitem", premiereChannelType="mono")
            clipitem.set("id", f"clipitem-{next_clip_num}")
            track.append(clipitem)

            # Remove existing links
            for link in list(clipitem.findall("link")):
                clipitem.remove(link)

            # Set clip properties
            _ensure_element(clipitem, "masterclipid").text = file_info.get("masterclipid", f"masterclip-a{track_idx + 1}")
            _ensure_element(clipitem, "name").text = file_info.get("name", f"Audio Track {track_idx + 1}")
            _ensure_element(clipitem, "enabled").text = "TRUE"

            clip_rate = _ensure_element(clipitem, "rate")
            _ensure_element(clip_rate, "timebase").text = str(timebase)
            _ensure_element(clip_rate, "ntsc").text = "TRUE" if ntsc else "FALSE"

            _ensure_element(clipitem, "start").text = str(timeline_position)
            _ensure_element(clipitem, "end").text = str(timeline_position + duration_frames)
            _ensure_element(clipitem, "in").text = str(start_frames)
            _ensure_element(clipitem, "out").text = str(start_frames + duration_frames)
            _ensure_element(clipitem, "pproTicksIn").text = str(frames_to_ppro_ticks(start_frames, fps))
            _ensure_element(clipitem, "pproTicksOut").text = str(frames_to_ppro_ticks(start_frames + duration_frames, fps))

            # File reference
            file_id = file_info.get("file_id")
            existing_files = clipitem.findall("file")
            if existing_files:
                file_elem = existing_files[0]
                for extra in existing_files[1:]:
                    clipitem.remove(extra)
            else:
                file_elem = ET.SubElement(clipitem, "file")

            if file_id:
                file_elem.set("id", file_id)
                if file_id not in used_file_ids:
                    file_elem.clear()
                    file_elem.set("id", file_id)
                    src_elem = file_info.get("element")
                    if src_elem is not None:
                        for child in src_elem:
                            copied = _deep_copy(child)
                            if copied is not None:
                                file_elem.append(copied)
                    used_file_ids.add(file_id)
                else:
                    for child in list(file_elem):
                        file_elem.remove(child)

            # Source track
            sourcetrack = _ensure_element(clipitem, "sourcetrack")
            _ensure_element(sourcetrack, "mediatype").text = "audio"
            _ensure_element(sourcetrack, "trackindex").text = str(source_channel)

            # Label
            labels = _ensure_element(clipitem, "labels")
            label2 = _ensure_element(labels, "label2")
            label2.text = color_to_premiere_label(seg.color or "")

            timeline_position += duration_frames
            if timeline_position > max_timeline_end:
                max_timeline_end = timeline_position
            next_clip_num += 1

        # Copy non-clipitem children
        for child in template_track:
            if child.tag != "clipitem":
                copied = _deep_copy(child)
                if copied is not None:
                    track.append(copied)

    # Update duration
    duration_elem.text = str(max_timeline_end)

    # Generate output path
    if output_path is None:
        output_path = csv_path.parent / f"{csv_path.stem}_cut_from_{template_xml_path.stem}.xml"
    else:
        output_path = Path(output_path)

    # Write XML
    xml_string = _prettify_xml(root)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(xml_string)

    print(f"\nXML generated: {output_path}")
    return output_path


def _prettify_xml(elem: ET.Element) -> str:
    """Return pretty-printed XML string with DOCTYPE."""
    rough_string = ET.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    xml_string = reparsed.toprettyxml(indent="\t", encoding="UTF-8").decode("utf-8")

    # Add DOCTYPE declaration
    xml_lines = xml_string.split("\n")
    xml_lines.insert(1, "<!DOCTYPE xmeml>")

    return "\n".join(xml_lines)
