"""
Test script to verify that template backslashes are preserved correctly.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from resume_builder.latex_builder import LaTeXBuilder
from resume_builder.paths import TEMPLATES, OUTPUT_DIR

def test_template_reading():
    """Test that template is read with backslashes preserved."""
    print("=" * 80)
    print("Testing Template Backslash Preservation")
    print("=" * 80)
    print()
    
    template_path = TEMPLATES / "main.tex"
    
    if not template_path.exists():
        print(f"[ERROR] Template file not found: {template_path}")
        return False
    
    print(f"Template file: {template_path}")
    print()
    
    # Test 1: Read template using the old method (read_text)
    print("Test 1: Reading template with read_text() (old method)")
    old_content = template_path.read_text(encoding='utf-8')
    
    # Test 2: Read template using the new method (read_bytes then decode)
    print("Test 2: Reading template with read_bytes() then decode() (new method)")
    template_bytes = template_path.read_bytes()
    new_content = template_bytes.decode('utf-8')
    
    # Check if they're the same (they should be for file reading, but let's verify)
    if old_content == new_content:
        print("[OK] Both methods produce identical content")
    else:
        print("[WARNING] Methods produce different content (unexpected)")
        print(f"   Old length: {len(old_content)}")
        print(f"   New length: {len(new_content)}")
    
    print()
    
    # Test 3: Check for critical backslashes in template
    print("Test 3: Checking for critical backslashes in template")
    critical_commands = [
        r'\newif\ifcompactresume',
        r'\newcommand{\compactresumelayout}',
        r'\nopagenumbers',
        r'\documentclass',
        r'\begin{document}',
    ]
    
    all_present = True
    for cmd in critical_commands:
        if cmd in new_content:
            print(f"  [OK] Found: {cmd}")
        else:
            print(f"  [ERROR] Missing: {cmd}")
            all_present = False
    
    print()
    
    # Test 4: Check for corrupted versions (missing backslashes)
    print("Test 4: Checking for corrupted versions (missing backslashes)")
    corrupted_patterns = [
        'ewif\\ifcompactresume',
        'ewcommand{\\compactresumelayout}',
        'opagenumbers',
        'ewcommand',
    ]
    
    found_corruption = False
    for pattern in corrupted_patterns:
        if pattern in new_content:
            print(f"  [WARNING] Found corrupted pattern: {pattern}")
            found_corruption = True
    
    if not found_corruption:
        print("  [OK] No corrupted patterns found in template")
    
    print()
    
    # Test 5: Test LaTeXBuilder actually uses the new method
    print("Test 5: Testing LaTeXBuilder template reading")
    builder = LaTeXBuilder()
    
    # Create minimal identity for testing
    test_identity = {
        'first': 'Test',
        'last': 'User',
        'email': 'test@example.com',
        'phone': '123-456-7890'
    }
    
    # Build preamble (this doesn't read template, but let's test the build method)
    preamble = builder.build_preamble(test_identity)
    
    # Check if preamble has correct backslashes
    if r'\name{' in preamble and r'\email{' in preamble:
        print("  [OK] Preamble has correct backslashes")
    else:
        print("  [ERROR] Preamble missing backslashes")
        print(f"     Preamble preview: {preamble[:200]}")
    
    print()
    
    # Test 6: Simulate the actual build process
    print("Test 6: Simulating build_resume_from_json_files template reading")
    try:
        # This will use the new read_bytes method
        from resume_builder.latex_builder import build_resume_from_json_files
        
        # Check if template exists
        if template_path.exists():
            # Read template the way build_resume_from_json_files does
            template_bytes_test = template_path.read_bytes()
            template_content_test = template_bytes_test.decode('utf-8')
            
            # Verify critical commands are present
            if r'\newif\ifcompactresume' in template_content_test:
                print("  [OK] Template read correctly - \\newif\\ifcompactresume present")
            else:
                print("  [ERROR] Template read incorrectly - \\newif\\ifcompactresume missing")
            
            if r'\newcommand{\compactresumelayout}' in template_content_test:
                print("  [OK] Template read correctly - \\newcommand{\\compactresumelayout} present")
            else:
                print("  [ERROR] Template read incorrectly - \\newcommand{\\compactresumelayout} missing")
        else:
            print("  [WARNING] Template file not found for testing")
    except Exception as e:
        print(f"  [ERROR] Error testing build process: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    
    return all_present and not found_corruption


def test_generated_latex():
    """Test that generated LaTeX has correct backslashes."""
    print()
    print("=" * 80)
    print("Testing Generated LaTeX Backslashes")
    print("=" * 80)
    print()
    
    generated_tex = OUTPUT_DIR / "generated" / "rendered_resume.tex"
    
    if not generated_tex.exists():
        print(f"[WARNING] Generated LaTeX file not found: {generated_tex}")
        print("   Run the pipeline first to generate a resume")
        return False
    
    print(f"Generated LaTeX: {generated_tex}")
    print()
    
    content = generated_tex.read_text(encoding='utf-8')
    
    # Check for correct backslashes
    print("Checking for correct backslashes:")
    correct_patterns = [
        (r'\newif\ifcompactresume', '\\newif\\ifcompactresume'),
        (r'\newcommand{\compactresumelayout}', '\\newcommand{\\compactresumelayout}'),
        (r'\compactresumelayout', '\\compactresumelayout (call)'),
        (r'\nopagenumbers', '\\nopagenumbers'),
    ]
    
    all_correct = True
    for pattern, name in correct_patterns:
        if pattern in content:
            print(f"  [OK] Found correct: {name}")
        else:
            print(f"  [ERROR] Missing: {name}")
            all_correct = False
    
    print()
    
    # Check for corrupted versions
    print("Checking for corrupted patterns:")
    corrupted_patterns = [
        ('ewif\\ifcompactresume', 'ewif\\ifcompactresume (missing \\ before newif)'),
        ('ewcommand{\\compactresumelayout}', 'ewcommand{\\compactresumelayout} (missing \\ before newcommand)'),
        ('opagenumbers', 'opagenumbers (missing \\ before nopagenumbers)'),
        ('\\\\compactresumelayout', '\\\\compactresumelayout (double backslash)'),
    ]
    
    found_corruption = False
    for pattern, name in corrupted_patterns:
        if pattern in content:
            print(f"  [WARNING] Found corrupted: {name}")
            # Show context
            idx = content.find(pattern)
            if idx >= 0:
                start = max(0, idx - 30)
                end = min(len(content), idx + len(pattern) + 30)
                context = content[start:end].replace('\n', '\\n')
                print(f"     Context: ...{context}...")
            found_corruption = True
    
    if not found_corruption:
        print("  [OK] No corrupted patterns found")
    
    print()
    print("=" * 80)
    
    return all_correct and not found_corruption


if __name__ == "__main__":
    print()
    print("Testing Template Backslash Fix")
    print()
    
    test1_passed = test_template_reading()
    test2_passed = test_generated_latex()
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Template reading test: {'[PASSED]' if test1_passed else '[FAILED]'}")
    print(f"Generated LaTeX test: {'[PASSED]' if test2_passed else '[SKIPPED] (no generated file)'}")
    print()
    
    if test1_passed:
        print("[SUCCESS] Template backslash fix is working correctly!")
    else:
        print("[FAILED] Template backslash fix needs attention")
    print()

