#!/usr/bin/env python3
"""Test script for multiple file support."""

from pathlib import Path
from csvtoxml.core.parser import parse_csv, CsvRow
from csvtoxml.core.segment import build_segments
import tempfile
import os

# Create test CSV with file names
csv_content = """Speaker Name,ファイル名,イン点,アウト点,文字起こし,色選択
田丸,Cam1.mov,00:00:00:00,00:00:05:00,テスト1,Violet
中島,Cam2.mov,00:00:05:00,00:00:10:00,テスト2,Rose
田丸,Cam1.mov,00:00:10:00,00:00:15:00,テスト3,Violet
"""

# Create test CSV without file names (backward compatibility)
csv_content_no_files = """Speaker Name,イン点,アウト点,文字起こし,色選択
田丸,00:00:00:00,00:00:05:00,テスト1,Violet
中島,00:00:05:00,00:00:10:00,テスト2,Rose
"""

def test_with_file_names():
    """Test CSV parsing with file names."""
    print("Testing CSV with ファイル名 column...")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        rows = parse_csv(csv_path)

        assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
        assert rows[0].file_name == "Cam1.mov", f"Expected 'Cam1.mov', got '{rows[0].file_name}'"
        assert rows[1].file_name == "Cam2.mov", f"Expected 'Cam2.mov', got '{rows[1].file_name}'"
        assert rows[2].file_name == "Cam1.mov", f"Expected 'Cam1.mov', got '{rows[2].file_name}'"

        # Test segment building
        segments, warnings = build_segments(rows, 30.0)
        assert len(segments) == 3, f"Expected 3 segments, got {len(segments)}"
        assert segments[0].file_name == "Cam1.mov"
        assert segments[1].file_name == "Cam2.mov"
        assert segments[2].file_name == "Cam1.mov"

        print("✓ CSV with ファイル名 column works correctly")
        print(f"  - Rows: {len(rows)}")
        print(f"  - Segments: {len(segments)}")
        for i, seg in enumerate(segments):
            print(f"    Segment {i+1}: {seg.file_name} ({seg.color})")

    finally:
        os.unlink(csv_path)

def test_without_file_names():
    """Test CSV parsing without file names (backward compatibility)."""
    print("\nTesting CSV without ファイル名 column (backward compatibility)...")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_content_no_files)
        csv_path = f.name

    try:
        rows = parse_csv(csv_path)

        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
        assert rows[0].file_name is None, f"Expected None, got '{rows[0].file_name}'"
        assert rows[1].file_name is None, f"Expected None, got '{rows[1].file_name}'"

        # Test segment building
        segments, warnings = build_segments(rows, 30.0)
        assert len(segments) == 2, f"Expected 2 segments, got {len(segments)}"
        assert segments[0].file_name is None
        assert segments[1].file_name is None

        print("✓ CSV without ファイル名 column works correctly (backward compatible)")
        print(f"  - Rows: {len(rows)}")
        print(f"  - Segments: {len(segments)}")

    finally:
        os.unlink(csv_path)

if __name__ == "__main__":
    test_with_file_names()
    test_without_file_names()
    print("\n✓ All tests passed!")
