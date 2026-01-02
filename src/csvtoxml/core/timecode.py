"""Timecode conversion utilities."""

from __future__ import annotations

# Common frame rates
FPS_NTSC_30 = 30000 / 1001  # ~29.97
FPS_24 = 24.0
FPS_25 = 25.0
FPS_30 = 30.0

# Premiere Pro ticks per second
PPRO_TICKS_PER_SECOND = 254016000000


def timecode_to_frames(timecode: str, fps: float = FPS_NTSC_30) -> int:
    """Convert timecode string (HH:MM:SS:FF) to frame number.

    Args:
        timecode: Timecode string in format HH:MM:SS:FF or MM:SS:FF or SS:FF
                  Supports both : and ; separators (drop-frame notation)
        fps: Frames per second (default: 29.97 NTSC)

    Returns:
        Frame number as integer

    Examples:
        >>> timecode_to_frames("00:01:00:00", fps=24.0)
        1440
        >>> timecode_to_frames("00:00:01:12", fps=24.0)
        36
    """
    if not timecode or timecode.strip() == "":
        return 0

    # Handle both : and ; separators (drop-frame notation)
    parts = timecode.replace(";", ":").split(":")

    if len(parts) == 4:  # HH:MM:SS:FF
        hours, minutes, seconds, frames = map(int, parts)
    elif len(parts) == 3:  # MM:SS:FF
        hours = 0
        minutes, seconds, frames = map(int, parts)
    elif len(parts) == 2:  # SS:FF
        hours = minutes = 0
        seconds, frames = map(int, parts)
    else:
        return 0

    total_frames = (hours * 3600 + minutes * 60 + seconds) * fps + frames
    return int(round(total_frames))


def frames_to_timecode(frames: int, fps: float = FPS_NTSC_30) -> str:
    """Convert frame number to timecode string (HH:MM:SS:FF).

    Args:
        frames: Frame number
        fps: Frames per second (default: 29.97 NTSC)

    Returns:
        Timecode string in format HH:MM:SS:FF
    """
    total_seconds = frames / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    remaining_frames = int(round((total_seconds - int(total_seconds)) * fps))

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{remaining_frames:02d}"


def frames_to_ppro_ticks(frames: int, fps: float = FPS_NTSC_30) -> int:
    """Convert frames to Premiere Pro ticks.

    Premiere Pro uses 254016000000 ticks per second for internal timing.

    Args:
        frames: Frame number
        fps: Frames per second (default: 29.97 NTSC)

    Returns:
        Premiere Pro ticks as integer
    """
    seconds = frames / fps
    return int(seconds * PPRO_TICKS_PER_SECOND)


def get_fps_from_rate(timebase: int, ntsc: bool = True) -> float:
    """Get FPS from rate specification.

    Args:
        timebase: Base frame rate (e.g., 24, 30)
        ntsc: Whether NTSC timing is used (1000/1001 multiplier)

    Returns:
        Actual frames per second
    """
    if ntsc:
        return timebase * 1000.0 / 1001.0
    return float(timebase)
