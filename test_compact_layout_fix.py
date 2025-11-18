"""
Test script to verify the compactresumelayout auto-injection fix.

This test verifies that:
1. The command definition is auto-injected when missing
2. Backslashes are preserved correctly
3. The enumitem package is added if needed
4. The command is called after begin{document}
"""

import tempfile
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from resume_builder.latex_builder import build_resume_from_json_files
from resume_builder.paths import OUTPUT_DIR

def create_test_json_files(temp_dir: Path):
    """Create minimal test JSON files."""
    # Identity
    identity_file = temp_dir / "identity.json"
    identity_file.write_text('{"identity": {"name": "Test User", "email": "test@example.com", "phone": "123-456-7890"}}', encoding='utf-8')
    
    # Summary
    summary_file = temp_dir / "summary.json"
    summary_file.write_text('{"status": "success", "message": "OK", "summary": "Test summary", "approx_word_count": 2}', encoding='utf-8')
    
    # Experiences
    exp_file = temp_dir / "selected_experiences.json"
    exp_file.write_text('{"status": "success", "message": "OK", "selected_experiences": []}', encoding='utf-8')
    
    # Education
    edu_file = temp_dir / "education.json"
    edu_file.write_text('{"status": "success", "message": "OK", "education": []}', encoding='utf-8')
    
    # Skills
    skills_file = temp_dir / "selected_skills.json"
    skills_file.write_text('{"status": "success", "message": "OK", "skills": ["Python", "LaTeX"]}', encoding='utf-8')
    
    return {
        "identity": identity_file,
        "summary": summary_file,
        "experiences": exp_file,
        "education": edu_file,
        "skills": skills_file
    }

def test_template_without_command():
    """Test that command is injected when template doesn't have it."""
    print("=" * 60)
    print("Test 1: Template WITHOUT \\compactresumelayout command")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        json_files = create_test_json_files(tmp_path)
        
        # Create a template WITHOUT the command
        template_file = tmp_path / "template.tex"
        template_content = r"""\documentclass[11pt,a4paper]{article}
\usepackage{enumitem}

\begin{document}
\section{Test}
Content here
\end{document}
"""
        template_file.write_text(template_content, encoding='utf-8')
        
        # Build resume with minimal page budget to force compact layout
        output_tex = tmp_path / "output.tex"
        latex = build_resume_from_json_files(
            identity_path=json_files["identity"],
            summary_path=json_files["summary"],
            experience_path=json_files["experiences"],
            education_path=json_files["education"],
            skills_path=json_files["skills"],
            template_path=template_file,
            output_path=output_tex,
            page_budget_pages=1  # Force compact layout with very tight budget
        )
        
        # Check results
        output_content = output_tex.read_text(encoding='utf-8')
        
        # Check 1: Command definition should be present
        has_definition = r'\newcommand{\compactresumelayout}' in output_content
        print(f"[OK] Command definition present: {has_definition}")
        
        # Check 2: Backslashes should be preserved (not 'ewcommand')
        has_correct_backslashes = r'\newcommand{\compactresumelayout}' in output_content
        has_broken_backslashes = 'ewcommand' in output_content
        print(f"[OK] Backslashes preserved: {has_correct_backslashes}")
        print(f"[FAIL] Broken backslashes found: {has_broken_backslashes}")
        
        # Check 3: Command should be called after \begin{document}
        has_command_call = r'\begin{document}' in output_content and r'\compactresumelayout' in output_content
        # Check that it's after \begin{document}
        doc_pos = output_content.find(r'\begin{document}')
        cmd_pos = output_content.find(r'\compactresumelayout')
        is_after_doc = cmd_pos > doc_pos if doc_pos != -1 and cmd_pos != -1 else False
        print(f"[OK] Command called after begin{{document}}: {is_after_doc}")
        
        # Check 4: enumitem should be present (we added it in template, but check it's still there)
        has_enumitem = r'\usepackage{enumitem}' in output_content
        print(f"[OK] enumitem package present: {has_enumitem}")
        
        # Show relevant snippet
        if has_definition:
            def_start = output_content.find(r'\newcommand{\compactresumelayout}')
            def_end = output_content.find('}', def_start) + 1
            snippet = output_content[def_start:def_end+50]
            print(f"\nCommand definition snippet:\n{snippet}")
        
        success = has_definition and has_correct_backslashes and not has_broken_backslashes and is_after_doc
        print(f"\n[{'PASS' if success else 'FAIL'}] TEST {'PASSED' if success else 'FAILED'}")
        return success

def test_template_with_command():
    """Test that existing command is not duplicated."""
    print("\n" + "=" * 60)
    print("Test 2: Template WITH \\compactresumelayout command")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        json_files = create_test_json_files(tmp_path)
        
        # Create a template WITH the command already defined
        template_file = tmp_path / "template.tex"
        template_content = r"""\documentclass[11pt,a4paper]{article}
\usepackage{enumitem}

\newif\ifcompactresume
\compactresumefalse

\newcommand{\compactresumelayout}{%
  \compactresumetrue
  \setlength{\itemsep}{0.2em}
}

\begin{document}
\section{Test}
Content here
\end{document}
"""
        template_file.write_text(template_content, encoding='utf-8')
        
        # Build resume with minimal page budget to force compact layout
        output_tex = tmp_path / "output.tex"
        latex = build_resume_from_json_files(
            identity_path=json_files["identity"],
            summary_path=json_files["summary"],
            experience_path=json_files["experiences"],
            education_path=json_files["education"],
            skills_path=json_files["skills"],
            template_path=template_file,
            output_path=output_tex,
            page_budget_pages=1  # Force compact layout with very tight budget
        )
        
        # Check results
        output_content = output_tex.read_text(encoding='utf-8')
        
        # Count how many times the command is defined
        definition_count = output_content.count(r'\newcommand{\compactresumelayout}')
        print(f"[OK] Command definition count: {definition_count} (should be 1)")
        
        # Should not have duplicate definitions
        no_duplicates = definition_count == 1
        print(f"[OK] No duplicate definitions: {no_duplicates}")
        
        success = no_duplicates
        print(f"\n[{'PASS' if success else 'FAIL'}] TEST {'PASSED' if success else 'FAILED'}")
        return success

def test_template_without_enumitem():
    """Test that enumitem is added when missing."""
    print("\n" + "=" * 60)
    print("Test 3: Template WITHOUT enumitem package")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        json_files = create_test_json_files(tmp_path)
        
        # Create a template WITHOUT enumitem
        template_file = tmp_path / "template.tex"
        template_content = r"""\documentclass[11pt,a4paper]{article}

\begin{document}
\section{Test}
Content here
\end{document}
"""
        template_file.write_text(template_content, encoding='utf-8')
        
        # Build resume with minimal page budget to force compact layout
        output_tex = tmp_path / "output.tex"
        latex = build_resume_from_json_files(
            identity_path=json_files["identity"],
            summary_path=json_files["summary"],
            experience_path=json_files["experiences"],
            education_path=json_files["education"],
            skills_path=json_files["skills"],
            template_path=template_file,
            output_path=output_tex,
            page_budget_pages=1  # Force compact layout with very tight budget
        )
        
        # Check results
        output_content = output_tex.read_text(encoding='utf-8')
        
        # enumitem should be added
        has_enumitem = r'\usepackage{enumitem}' in output_content
        print(f"[OK] enumitem package added: {has_enumitem}")
        
        # Command definition should use \setlist (which requires enumitem)
        has_setlist = r'\setlist[' in output_content
        print(f"[OK] setlist commands present: {has_setlist}")
        
        success = has_enumitem and has_setlist
        print(f"\n[{'PASS' if success else 'FAIL'}] TEST {'PASSED' if success else 'FAILED'}")
        return success

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing \\compactresumelayout Auto-Injection Fix")
    print("=" * 60 + "\n")
    
    results = []
    
    try:
        results.append(("Template without command", test_template_without_command()))
    except Exception as e:
        print(f"[FAIL] Test 1 failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Template without command", False))
    
    try:
        results.append(("Template with command", test_template_with_command()))
    except Exception as e:
        print(f"[FAIL] Test 2 failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Template with command", False))
    
    try:
        results.append(("Template without enumitem", test_template_without_enumitem()))
    except Exception as e:
        print(f"[FAIL] Test 3 failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Template without enumitem", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("[PASS] ALL TESTS PASSED!")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())

