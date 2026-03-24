#!/usr/bin/env python3
"""Test file matching logic."""

from csvtoxml.writers.premiere import find_media_file

# Sample media files list
media_files = [
    {"name": "Cam1.mov", "pathurl": "/path/to/Cam1.mov", "file_id": "file-1"},
    {"name": "Cam2.mov", "pathurl": "/path/to/Cam2.mov", "file_id": "file-2"},
    {"name": "Background.mp4", "pathurl": "/path/to/Background.mp4", "file_id": "file-3"},
]

def test_exact_match():
    """Test exact file name match."""
    print("Testing exact match...")
    result = find_media_file(media_files, "Cam1.mov", 0)
    assert result["name"] == "Cam1.mov", f"Expected 'Cam1.mov', got '{result['name']}'"
    print("✓ Exact match works")

def test_case_insensitive():
    """Test case-insensitive match."""
    print("\nTesting case-insensitive match...")
    result = find_media_file(media_files, "cam2.mov", 0)
    assert result["name"] == "Cam2.mov", f"Expected 'Cam2.mov', got '{result['name']}'"
    print("✓ Case-insensitive match works")

def test_partial_match():
    """Test partial file name match."""
    print("\nTesting partial match...")
    result = find_media_file(media_files, "Background", 0)
    assert result["name"] == "Background.mp4", f"Expected 'Background.mp4', got '{result['name']}'"
    print("✓ Partial match works")

def test_fallback_to_track_index():
    """Test fallback to track index when file name is None."""
    print("\nTesting fallback to track index...")
    result = find_media_file(media_files, None, 0)
    assert result["name"] == "Cam1.mov", f"Expected 'Cam1.mov', got '{result['name']}'"

    result = find_media_file(media_files, None, 1)
    assert result["name"] == "Cam2.mov", f"Expected 'Cam2.mov', got '{result['name']}'"

    result = find_media_file(media_files, None, 2)
    assert result["name"] == "Background.mp4", f"Expected 'Background.mp4', got '{result['name']}'"

    # Out of bounds should use last file
    result = find_media_file(media_files, None, 10)
    assert result["name"] == "Background.mp4", f"Expected 'Background.mp4', got '{result['name']}'"
    print("✓ Fallback to track index works")

def test_nonexistent_file():
    """Test that nonexistent file falls back to track index."""
    print("\nTesting nonexistent file fallback...")
    result = find_media_file(media_files, "NonExistent.mov", 1)
    assert result["name"] == "Cam2.mov", f"Expected 'Cam2.mov' (fallback), got '{result['name']}'"
    print("✓ Nonexistent file fallback works")

if __name__ == "__main__":
    test_exact_match()
    test_case_insensitive()
    test_partial_match()
    test_fallback_to_track_index()
    test_nonexistent_file()
    print("\n✓ All file matching tests passed!")
