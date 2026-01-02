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

| Column | Description |
|--------|-------------|
| `Speaker Name` | Speaker identifier |
| `イン点` | In point timecode (HH:MM:SS:FF) |
| `アウト点` | Out point timecode (HH:MM:SS:FF) |
| `文字起こし` | Transcript text |
| `色選択` | Color label (e.g., Violet, Rose, Mango) |

### Gap Rows

Use `GAP_N` in the color column to insert gaps:

```csv
Speaker Name,イン点,アウト点,文字起こし,色選択
,00:00:00:00,00:00:10:00,--- GAP ---,GAP_1
```

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
