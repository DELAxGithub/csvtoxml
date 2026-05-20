import logging
from pathlib import Path
from csvtoxml.writers.premiere import generate_premiere_xml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    base_dir = Path("037radio")
    csv_path = base_dir / "37__S.csv"
    template_path = base_dir / "37_original.xml"
    output_path = base_dir / "37__S_editing.xml"

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return
    if not template_path.exists():
        logger.error(f"Template file not found: {template_path}")
        return

    try:
        xml_out = generate_premiere_xml(
            csv_path=csv_path,
            template_xml_path=template_path,
            output_path=output_path,
        )
        logger.info(f"Generated XML: {xml_out}")
        print(f"Successfully generated: {xml_out}")
    except Exception as e:
        logger.error(f"Failed to generate XML for {csv_path}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
