#!/usr/bin/env python3
"""
Quick test script to verify LaTeX fixes before running full pipeline.
Tests:
1. Header tabular alignment fix
2. Length budget enforcement improvements
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from resume_builder.latex_builder import LaTeXBuilder, enforce_length_budget
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_header_tabular_fix():
    """Test that header generates correct tabular with multicolumn email."""
    print("\n" + "="*60)
    print("TEST 1: Header Tabular Alignment Fix")
    print("="*60)
    
    builder = LaTeXBuilder()
    
    # Test case: phone, email (multicolumn), location
    contact_info = {
        'phone': '(949) 426-8113',
        'email': 'amir.mohaddesi@gmail.com',
        'location': 'San Mateo, CA',
        'website': 'https://amirmohaddesi.github.io/',
        'linkedin': 'amohaddesi',
        'github': 'AmirMohaddesi'
    }
    
    header = builder.build_header(contact_info=contact_info)
    
    print("\nGenerated header LaTeX:")
    print("-" * 60)
    print(header)
    print("-" * 60)
    
    # Check for correct tabular structure
    issues = []
    
    # Should have exactly 4 columns in tabular definition
    if '\\begin{tabular}{ c c c c }' not in header:
        issues.append("[FAIL] Tabular should have exactly 4 columns: { c c c c }")
    else:
        print("[PASS] Tabular has correct 4-column definition")
    
    # Should have multicolumn for email
    if '\\multicolumn{2}{c}' not in header:
        issues.append("[FAIL] Email should use \\multicolumn{2}{c}")
    else:
        print("[PASS] Email uses multicolumn correctly")
    
    # Count & separators in row 1 (should be 3 & for 4 columns: phone & email(multicolumn) & location)
    row1_start = header.find('\\begin{tabular}')
    row1_end = header.find('\\\\', row1_start)
    if row1_end > 0:
        row1 = header[row1_start:row1_end]
        # Count & that are NOT inside multicolumn
        # Simple check: should have 2 & separators (phone & email & location)
        # But email uses multicolumn, so we need to be careful
        # Actually, with multicolumn, we should have: phone & \multicolumn{2}{c}{email} & location
        # That's 2 & separators for 4 columns total
        ampersand_count = row1.count(' & ')
        if ampersand_count < 2 or ampersand_count > 3:
            issues.append(f"[FAIL] Row 1 should have 2-3 & separators (found {ampersand_count})")
        else:
            print(f"[PASS] Row 1 has correct number of & separators ({ampersand_count})")
    
    # Check row 2 (should have 3 & for 4 columns)
    row2_start = header.find('\\hline')
    if row2_start > 0:
        row2_end = header.find('\\\\', row2_start)
        if row2_end > 0:
            row2 = header[row2_start:row2_end]
            ampersand_count = row2.count(' & ')
            if ampersand_count != 3:
                issues.append(f"[FAIL] Row 2 should have exactly 3 & separators (found {ampersand_count})")
            else:
                print(f"[PASS] Row 2 has correct number of & separators ({ampersand_count})")
    
    if issues:
        print("\n[FAIL] ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n[PASS] All header tabular checks passed!")
        return True


def test_length_budget_enforcement():
    """Test improved length budget estimation and trimming."""
    print("\n" + "="*60)
    print("TEST 2: Length Budget Enforcement")
    print("="*60)
    
    # Create test data with nested lists (like the actual resume)
    experiences = [
        {
            'title': 'Graduate Researcher',
            'company': 'CARL Lab',
            'priority': 1,
            'bullets': [
                'Built multi-robot simulation platform',
                'Scaled system from Webots to ROS2',
                'Conducted simulation-based experiments',
                'Designed communication-aware coordination framework',
                'Integrated C++ and Python nodes'
            ]
        },
        {
            'title': 'Assistant',
            'company': 'NMI Lab',
            'priority': 2,
            'bullets': [
                'Developed 8-bit quantized spiking neural network',
                'Reduced energy consumption by 12-18%'
            ]
        }
    ]
    
    projects = [
        {
            'name': 'Alter Ego: Personalized Conversational AI',
            'priority': 1,
            'bullets': [
                'Designed and deployed conversational AI agent',
                'Built using Python, Gradio, and OpenAI API',
                'Deployed on Hugging Face Spaces'
            ]
        },
        {
            'name': 'Multi-Robot Coordination System',
            'priority': 1,
            'bullets': [
                'Built ROS2 Humble-based simulation platform',
                'Integrated SLAM Toolbox, Nav2, map_merge'
            ]
        }
    ]
    
    skills_data = {
        'skills': ['Python', 'C++', 'PyTorch', 'ROS2', 'Machine Learning', 'RL', 'LLMs']
    }
    
    education_data = [
        {'degree': 'Ph.D.', 'institution': 'UC Irvine', 'dates': '2019-2025'},
        {'degree': 'B.S.', 'institution': 'Sharif University', 'dates': '2015-2019'}
    ]
    
    print(f"\nInput data:")
    print(f"  Experiences: {len(experiences)} (with {sum(len(e.get('bullets', [])) for e in experiences)} total bullets)")
    print(f"  Projects: {len(projects)} (with {sum(len(p.get('bullets', [])) for p in projects)} total bullets)")
    print(f"  Skills: {len(skills_data['skills'])}")
    print(f"  Education entries: {len(education_data)}")
    
    # Test with 2-page budget
    result = enforce_length_budget(
        experiences=experiences,
        projects=projects,
        skills_data=skills_data,
        education_data=education_data,
        page_budget_pages=2
    )
    
    print(f"\nAfter trimming (2-page budget):")
    print(f"  Experiences: {len(result['experiences'])} (with {sum(len(e.get('bullets', [])) for e in result['experiences'])} total bullets)")
    print(f"  Projects: {len(result['projects'])} (with {sum(len(p.get('bullets', [])) for p in result['projects'])} total bullets)")
    print(f"  Used compact layout: {result['used_compact_layout']}")
    
    # Check that trimming worked
    issues = []
    
    # Should trim bullets to max 2
    for exp in result['experiences']:
        bullets = exp.get('bullets', [])
        if len(bullets) > 2:
            issues.append(f"[FAIL] Experience '{exp.get('title')}' still has {len(bullets)} bullets (should be <=2)")
    
    for proj in result['projects']:
        bullets = proj.get('bullets', [])
        if len(bullets) > 2:
            issues.append(f"[FAIL] Project '{proj.get('name')}' still has {len(bullets)} bullets (should be <=2)")
    
    # Should drop priority 2 experiences if needed
    priority_2_count = sum(1 for exp in result['experiences'] if exp.get('priority') == 2)
    if priority_2_count > 0 and len(result['experiences']) > 2:
        issues.append(f"[FAIL] Still has {priority_2_count} priority-2 experiences when over budget")
    
    if issues:
        print("\n[FAIL] ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n[PASS] All length budget checks passed!")
        return True


def test_existing_latex_file():
    """Test if existing LaTeX file compiles without tabular errors."""
    print("\n" + "="*60)
    print("TEST 3: Existing LaTeX File Compilation Check")
    print("="*60)
    
    tex_file = Path("output/generated/rendered_resume.tex")
    
    if not tex_file.exists():
        print(f"[SKIP] LaTeX file not found: {tex_file}")
        print("   Skipping compilation test (run pipeline first to generate)")
        return None
    
    print(f"\nChecking LaTeX file: {tex_file}")
    
    content = tex_file.read_text(encoding='utf-8')
    
    # Check for the problematic tabular structure
    issues = []
    
    # Find header tabular
    tabular_start = content.find('\\begin{center}\\begin{tabular}')
    if tabular_start > 0:
        tabular_end = content.find('\\end{tabular}', tabular_start)
        if tabular_end > 0:
            tabular_block = content[tabular_start:tabular_end + len('\\end{tabular}')]
            
            # Check column definition
            if '{ c c c c }' in tabular_block:
                print("[PASS] Tabular has correct 4-column definition")
            else:
                issues.append("[FAIL] Tabular column definition incorrect")
            
            # Check row 1 for correct structure
            row1_lines = [line for line in tabular_block.split('\n') if '&' in line and '\\hline' not in line]
            if row1_lines:
                row1 = row1_lines[0]
                # Should have multicolumn for email
                if '\\multicolumn{2}{c}' in row1:
                    print("[PASS] Row 1 uses multicolumn correctly")
                else:
                    issues.append("[FAIL] Row 1 missing multicolumn for email")
                
                # Count & separators (should be 2 for: phone & email(multicolumn) & location)
                ampersand_count = row1.count(' & ')
                if ampersand_count == 2:
                    print(f"[PASS] Row 1 has correct number of & separators ({ampersand_count})")
                else:
                    issues.append(f"[FAIL] Row 1 has {ampersand_count} & separators (should be 2)")
    
    if issues:
        print("\n[FAIL] ISSUES FOUND in existing LaTeX file:")
        for issue in issues:
            print(f"  {issue}")
        print("\n[WARN] You may need to regenerate the LaTeX file for fixes to take effect")
        return False
    else:
        print("\n[PASS] Existing LaTeX file structure looks correct!")
        print("   (Note: This doesn't test compilation, just structure)")
        return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TESTING LATEX FIXES")
    print("="*60)
    
    results = []
    
    # Test 1: Header tabular fix
    results.append(("Header Tabular Fix", test_header_tabular_fix()))
    
    # Test 2: Length budget enforcement
    results.append(("Length Budget Enforcement", test_length_budget_enforcement()))
    
    # Test 3: Existing LaTeX file check
    result3 = test_existing_latex_file()
    if result3 is not None:
        results.append(("Existing LaTeX File", result3))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        if result is None:
            status = "[SKIP]"
        print(f"{status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[PASS] All tests passed! Ready to run full pipeline.")
        return 0
    else:
        print("\n[WARN] Some tests failed. Review issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

