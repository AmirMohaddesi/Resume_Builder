#!/usr/bin/env python
"""Debug script to test PDF comparison and LaTeX structure analysis tools.

Usage:
    python scripts/debug_pdf_diff.py
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from resume_builder.tools import PdfComparisonTool, LaTeXStructureAnalyzerTool
import json


def test_pdf_comparison():
    """Test PDF comparison tool."""
    print("=" * 80)
    print("Testing PdfComparisonTool")
    print("=" * 80)
    
    tool = PdfComparisonTool()
    
    # Use example paths - adjust as needed
    reference_pdf = project_root / "output" / "reference_resume.pdf"
    generated_pdf = project_root / "output" / "generated" / "final_resume.pdf"
    
    if not reference_pdf.exists():
        print(f"⚠️  Reference PDF not found: {reference_pdf}")
        print("   Please provide a reference PDF to compare against.")
        return
    
    if not generated_pdf.exists():
        print(f"⚠️  Generated PDF not found: {generated_pdf}")
        print("   Please generate a resume first.")
        return
    
    print(f"Reference PDF: {reference_pdf}")
    print(f"Generated PDF: {generated_pdf}")
    print()
    
    result_str = tool._run(
        reference_pdf=str(reference_pdf),
        generated_pdf=str(generated_pdf)
    )
    
    result = json.loads(result_str)
    
    if result.get("status") == "error":
        print(f"❌ Error: {result.get('error')}")
        if "hint" in result:
            print(f"   Hint: {result['hint']}")
        return
    
    print("✅ Comparison successful!")
    print()
    print("Lengths:")
    lengths = result.get("lengths", {})
    print(f"  Reference: {lengths.get('reference_chars', 0):,} chars, {lengths.get('reference_lines', 0)} lines")
    print(f"  Generated: {lengths.get('generated_chars', 0):,} chars, {lengths.get('generated_lines', 0)} lines")
    print()
    
    print("Sections detected:")
    sections = result.get("sections", {})
    ref_sections = sections.get("reference", {})
    gen_sections = sections.get("generated", {})
    
    print("  Reference sections:", list(ref_sections.keys()))
    print("  Generated sections:", list(gen_sections.keys()))
    print()
    
    print("Full result (JSON):")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def test_latex_structure_analyzer():
    """Test LaTeX structure analyzer tool."""
    print()
    print("=" * 80)
    print("Testing LaTeXStructureAnalyzerTool")
    print("=" * 80)
    
    tool = LaTeXStructureAnalyzerTool()
    
    # Try different possible paths
    possible_paths = [
        project_root / "output" / "generated" / "rendered_resume.tex",
        project_root / "output" / "custom_template.tex",
        project_root / "src" / "resume_builder" / "templates" / "main.tex",
    ]
    
    tex_path = None
    for path in possible_paths:
        if path.exists():
            tex_path = path
            break
    
    if not tex_path:
        print("⚠️  No LaTeX file found. Tried:")
        for path in possible_paths:
            print(f"   - {path}")
        return
    
    print(f"Analyzing: {tex_path}")
    print()
    
    result_str = tool._run(tex_path=str(tex_path))
    result = json.loads(result_str)
    
    if result.get("status") == "error":
        print(f"❌ Error: {result.get('error')}")
        return
    
    print("✅ Analysis successful!")
    print()
    print(f"Document class: {result.get('document_class', 'N/A')}")
    print(f"Total lines: {result.get('total_lines', 0)}")
    print()
    
    print("Sections:")
    sections = result.get("sections", {})
    for name, info in sections.items():
        if isinstance(info, dict) and "line_range" in info:
            print(f"  {name}: lines {info['line_range'][0]}-{info['line_range'][1]} ({info['line_count']} lines)")
    print()
    
    print("Template markers:", result.get("template_markers", []))
    print()
    
    print("Custom commands:")
    custom_commands = result.get("custom_commands", {})
    if custom_commands:
        for cmd, info in custom_commands.items():
            print(f"  \\{cmd}: {info.get('num_args', 0)} args, defined at line {info.get('line', '?')}")
    else:
        print("  (none)")
    print()
    
    commands = result.get("commands", [])
    print(f"Total commands found: {len(commands)}")
    print(f"First 10 commands: {commands[:10]}")
    print()
    
    print("Full result (JSON):")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("PDF Comparison & LaTeX Structure Analysis Test")
    print()
    
    try:
        test_pdf_comparison()
        test_latex_structure_analyzer()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

