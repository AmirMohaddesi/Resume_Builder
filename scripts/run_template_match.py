#!/usr/bin/env python
"""CLI script to run LaTeX template matching against a reference PDF.

Usage:
    python scripts/run_template_match.py \
      --reference ./reference/Amirhosein.pdf \
      --generated ./output/generated/final_resume.pdf \
      --template ./output/generated/rendered_resume.tex
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import argparse
import json
from resume_builder.main import run_template_matching
from resume_builder.logger import get_logger

logger = get_logger("template_match_cli")


def main() -> int:
    """Run template matching CLI."""
    parser = argparse.ArgumentParser(
        description="Run LaTeX template matching to align generated resume with reference PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Match generated resume to reference
  python scripts/run_template_match.py \\
    --reference ./reference/Amirhosein.pdf \\
    --generated ./output/generated/final_resume.pdf \\
    --template ./output/generated/rendered_resume.tex

  # Use default template path
  python scripts/run_template_match.py \\
    --reference ./reference/Amirhosein.pdf \\
    --generated ./output/generated/final_resume.pdf
        """
    )
    parser.add_argument(
        "--reference",
        required=True,
        type=str,
        help="Path to reference (good) resume PDF, e.g. ./reference/Amirhosein.pdf",
    )
    parser.add_argument(
        "--generated",
        required=True,
        type=str,
        help="Path to currently generated resume PDF, e.g. ./output/generated/final_resume.pdf",
    )
    parser.add_argument(
        "--template",
        required=False,
        type=str,
        default=None,
        help="Path to LaTeX template to fix (optional, defaults to output/generated/rendered_resume.tex)",
    )

    args = parser.parse_args()

    # Validate paths exist
    ref_path = Path(args.reference)
    gen_path = Path(args.generated)
    
    if not ref_path.exists():
        logger.error(f"Reference PDF not found: {ref_path}")
        return 1
    
    if not gen_path.exists():
        logger.error(f"Generated PDF not found: {gen_path}")
        return 1
    
    if args.template:
        template_path = Path(args.template)
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}, agent will try to locate it")
    else:
        template_path = None
        logger.info("No template specified, using default: output/generated/rendered_resume.tex")

    try:
        logger.info("Starting template matching...")
        result = run_template_matching(
            reference_pdf_path=str(ref_path),
            generated_pdf_path=str(gen_path),
            template_tex_path=str(template_path) if template_path else None,
        )

        # Display results
        print("\n" + "="*80)
        print("=== Template Matching Finished ===")
        print("="*80 + "\n")
        
        # Try to read the report file
        from resume_builder.paths import OUTPUT_DIR
        report_path = OUTPUT_DIR / "template_fix_report.json"
        
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                print("Report:")
                print(json.dumps(report, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Could not parse report JSON: {e}")
                print(f"Report file exists at: {report_path}")
        else:
            logger.warning(f"Report file not found at: {report_path}")
        
        # Show raw result if available
        if result:
            print("\nRaw result:")
            if isinstance(result, dict):
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                print(str(result))
        
        print("\n" + "="*80)
        print("Next steps:")
        print("1. Review the updated LaTeX template")
        print("2. Re-run the resume generation pipeline to compile the fixed template")
        print("3. Compare the new generated PDF with the reference")
        print("="*80)
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Template matching failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

