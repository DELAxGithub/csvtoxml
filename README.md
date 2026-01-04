# csvtoxml

CSV to NLE Timeline XML converter for Premiere Pro and DaVinci Resolve.

## Overview

`csvtoxml` converts timeline edit decisions from CSV format into XML that can be imported into video editing software:

- **Premiere Pro**: XMEML format (Final Cut Pro XML 7)
- **DaVinci Resolve**: FCPXML format (coming soon)

## Installation

```bash
pip install csvtoxml
```

Or install from source:

```bash
git clone https://github.com/DELAxGithub/csvtoxml.git
cd csvtoxml
pip install -e .
```

## Usage

### Command Line

```bash
# Basic usage
csvtoxml timeline.csv template.xml

# Specify output file
csvtoxml timeline.csv template.xml -o output.xml

# Custom gap duration (seconds)
csvtoxml timeline.csv template.xml --gap 3.0

# DaVinci Resolve format (coming soon)
csvtoxml timeline.csv template.xml --format davinci
```

### Python API

```python
from pathlib import Path
from csvtoxml.writers.premiere import generate_premiere_xml

output_path = generate_premiere_xml(
    csv_path=Path("timeline.csv"),
    template_xml_path=Path("template.xml"),
    gap_seconds=5.0,
)
print(f"Generated: {output_path}")
```

## CSV Format

The CSV file must have these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `Speaker Name` | Yes | Speaker identifier |
| `イン点` | Yes | In point timecode (HH:MM:SS:FF) |
| `アウト点` | Yes | Out point timecode (HH:MM:SS:FF) |
| `文字起こし` | Yes | Transcript text |
| `色選択` | Yes | Color label (e.g., Violet, Rose, Mango) |
| `ファイル名` | No | Media file name for this segment (optional) |

### Gap Rows

Use `GAP_N` in the color column to insert gaps:

```csv
Speaker Name,イン点,アウト点,文字起こし,色選択
,00:00:00:00,00:00:10:00,--- GAP ---,GAP_1
```

### Multiple Media Files

When your template XML contains multiple media files, you can specify which file to use for each segment with the `ファイル名` column:

```csv
Speaker Name,ファイル名,イン点,アウト点,文字起こし,色選択
田丸,Cam1.mov,00:00:29:07,00:00:44:00,これは僕はどうですか？,Violet
中島,Cam2.mov,00:00:44:00,00:00:52:13,今年は万博があって,Rose
田丸,Cam1.mov,00:00:52:15,00:00:53:05,そうですね,Violet
```

If `ファイル名` is not specified, the tool will use the media file based on track index (same as before).

### Example

```csv
Speaker Name,イン点,アウト点,文字起こし,色選択
田丸,00:00:29:07,00:00:44:00,これは僕はどうですか？,Violet
田丸,00:00:44:00,00:00:52:13,もう最悪ですよ。,Violet
,00:00:00:00,00:00:10:02,--- 20s GAP ---,GAP_1
中島,00:07:15:19,00:07:29:05,今年は万博があって,Rose
```

## Supported Colors

Premiere Pro label colors:
- Violet, Rose, Mango, Yellow, Lavender, Caribbean
- Tan, Forest, Blue, Purple, Teal, Brown, Gray
- Iris, Cerulean, Magenta

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT License
