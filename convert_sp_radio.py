
import logging
from pathlib import Path
from csvtoxml.writers.premiere import generate_premiere_xml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_file(csv_path, template_path, output_path):
    logger.info(f"Processing {csv_path} with template {template_path}")
    
    try:
        xml_out = generate_premiere_xml(
            csv_path=csv_path,
            template_xml_path=template_path,
            output_path=output_path
        )
        logger.info(f"Generated XML: {xml_out}")
        print(f"Successfully generated: {xml_out}")
    except Exception as e:
        logger.error(f"Failed to generate XML for {csv_path}: {e}")
        import traceback
        traceback.print_exc()

def main():
    base_dir = Path("sp_radio")
    
    files = [
        ("sp_1.csv", "spオリジナル1.xml"),
        ("so_2.csv", "soオリジナル2.xml"),
        ("sp_3.csv", "spオリジナル3.xml")
    ]
    
    for csv_file, xml_file in files:
        csv_path = base_dir / csv_file
        template_path = base_dir / xml_file
        output_path = base_dir / f"{csv_path.stem}_editing.xml"
        
        if csv_path.exists() and template_path.exists():
            process_file(csv_path, template_path, output_path)
        else:
            if not csv_path.exists():
                logger.warning(f"CSV file not found: {csv_path}")
            if not template_path.exists():
                logger.warning(f"Template file not found: {template_path}")

if __name__ == "__main__":
    main()
