"""
Test script to verify 2-page limit enforcement is working correctly.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from resume_builder.paths import OUTPUT_DIR
from resume_builder.length_budget import (
    estimate_lines, 
    TARGET_LINES_PER_PAGE,
    enforce_length_budget_on_json_files
)
from resume_builder.iterative_page_reducer import iteratively_reduce_pages
from resume_builder.json_loaders import (
    load_summary_block,
    load_selected_experiences,
    load_selected_skills,
    load_education_block,
    load_selected_projects
)

def test_length_estimation():
    """Test that length estimation is working."""
    print("=" * 80)
    print("Test 1: Length Estimation")
    print("=" * 80)
    print()
    
    summary_json = OUTPUT_DIR / "summary.json"
    experience_json = OUTPUT_DIR / "selected_experiences.json"
    skills_json = OUTPUT_DIR / "selected_skills.json"
    projects_json = OUTPUT_DIR / "selected_projects.json"
    education_json = OUTPUT_DIR / "education.json"
    
    if not all([summary_json.exists(), experience_json.exists(), skills_json.exists()]):
        print("[SKIP] Required JSON files not found. Run pipeline first.")
        return False
    
    # Load data
    summary_data = load_summary_block(summary_json)
    exp_data = load_selected_experiences(experience_json)
    skills_data = load_selected_skills(skills_json)
    projects = []
    if projects_json.exists():
        proj_data = load_selected_projects(projects_json)
        projects = proj_data.get('selected_projects', [])
    education = []
    if education_json.exists():
        edu_data = load_education_block(education_json)
        education = edu_data.get('education', [])
    
    # Estimate
    estimated_lines = estimate_lines(
        summary_data.get('summary', ''),
        exp_data.get('selected_experiences', []),
        projects,
        skills_data.get('skills', skills_data.get('selected_skills', [])),
        education
    )
    estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
    
    print(f"Estimated lines: {estimated_lines}")
    print(f"Estimated pages: {estimated_pages:.2f}")
    print(f"Target: ≤2.0 pages")
    print(f"Status: {'[OK] Within limit' if estimated_pages <= 2.0 else '[OVER] Exceeds limit'}")
    print()
    
    return estimated_pages


def test_length_budget_enforcement():
    """Test that length budget enforcement is working."""
    print("=" * 80)
    print("Test 2: Length Budget Enforcement")
    print("=" * 80)
    print()
    
    summary_json = OUTPUT_DIR / "summary.json"
    experience_json = OUTPUT_DIR / "selected_experiences.json"
    skills_json = OUTPUT_DIR / "selected_skills.json"
    projects_json = OUTPUT_DIR / "selected_projects.json"
    education_json = OUTPUT_DIR / "education.json"
    
    if not all([summary_json.exists(), experience_json.exists(), skills_json.exists()]):
        print("[SKIP] Required JSON files not found. Run pipeline first.")
        return None
    
    try:
        metadata = enforce_length_budget_on_json_files(
            summary_path=summary_json,
            experience_path=experience_json,
            skills_path=skills_json,
            projects_path=projects_json if projects_json.exists() else None,
            education_path=education_json if education_json.exists() else None,
            max_pages=2
        )
        
        pages_before = metadata.get("estimated_pages_before", 0)
        pages_after = metadata.get("estimated_pages_after", 0)
        
        print(f"Pages before: {pages_before:.2f}")
        print(f"Pages after: {pages_after:.2f}")
        print(f"Target: ≤2.0 pages")
        print(f"Status: {'[OK] Within limit' if pages_after <= 2.0 else '[OVER] Still exceeds limit'}")
        print()
        
        # Show what was trimmed
        if metadata.get("trimmed_experiences", 0) > 0:
            print(f"  - Experiences removed: {metadata['trimmed_experiences']}")
        if metadata.get("trimmed_projects", 0) > 0:
            print(f"  - Projects removed: {metadata['trimmed_projects']}")
        if metadata.get("trimmed_skills", 0) > 0:
            print(f"  - Skills removed: {metadata['trimmed_skills']}")
        if metadata.get("trimmed_experience_bullets", 0) > 0:
            print(f"  - Experience bullets removed: {metadata['trimmed_experience_bullets']}")
        if metadata.get("trimmed_project_bullets", 0) > 0:
            print(f"  - Project bullets removed: {metadata['trimmed_project_bullets']}")
        if metadata.get("trimmed_summary_words", 0) > 0:
            print(f"  - Summary words removed: {metadata['trimmed_summary_words']}")
        if metadata.get("trimmed_education", 0) > 0:
            print(f"  - Education entries removed: {metadata['trimmed_education']}")
        print()
        
        return metadata
    except Exception as e:
        print(f"[ERROR] Length budget enforcement failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_iterative_reduction():
    """Test that iterative page reduction is working."""
    print("=" * 80)
    print("Test 3: Iterative Page Reduction")
    print("=" * 80)
    print()
    
    summary_json = OUTPUT_DIR / "summary.json"
    experience_json = OUTPUT_DIR / "selected_experiences.json"
    skills_json = OUTPUT_DIR / "selected_skills.json"
    projects_json = OUTPUT_DIR / "selected_projects.json"
    education_json = OUTPUT_DIR / "education.json"
    jd_json = OUTPUT_DIR / "parsed_jd.json"
    
    if not all([summary_json.exists(), experience_json.exists(), skills_json.exists(), jd_json.exists()]):
        print("[SKIP] Required JSON files not found. Run pipeline first.")
        return None
    
    try:
        reduction_log = iteratively_reduce_pages(
            summary_path=summary_json,
            experience_path=experience_json,
            skills_path=skills_json,
            projects_path=projects_json if projects_json.exists() else None,
            education_path=education_json if education_json.exists() else None,
            jd_path=jd_json,
            target_pages=2.0,
            max_iterations=5
        )
        
        initial_pages = reduction_log.get("initial_estimated_pages", 0)
        final_pages = reduction_log.get("final_estimated_pages", 0)
        target_met = reduction_log.get("target_met", False)
        iterations = reduction_log.get("iterations", 0)
        items_removed = reduction_log.get("items_removed", [])
        
        print(f"Initial pages: {initial_pages:.2f}")
        print(f"Final pages: {final_pages:.2f}")
        print(f"Target: ≤2.0 pages")
        print(f"Iterations: {iterations}")
        print(f"Target met: {target_met}")
        print()
        
        if items_removed:
            print(f"Items removed ({len(items_removed)}):")
            for item in items_removed:
                item_type = item.get('type', 'unknown')
                item_name = item.get('item', item.get('skill', item.get('title', item.get('name', 'Unknown'))))
                reason = item.get('reason', 'Low priority')
                print(f"  - {item_type}: {item_name} ({reason})")
        print()
        
        return reduction_log
    except Exception as e:
        print(f"[ERROR] Iterative reduction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_compact_layout():
    """Test that compact layout is being applied."""
    print("=" * 80)
    print("Test 4: Compact Layout Application")
    print("=" * 80)
    print()
    
    rendered_tex = OUTPUT_DIR / "generated" / "rendered_resume.tex"
    
    if not rendered_tex.exists():
        print("[SKIP] Generated LaTeX file not found. Run pipeline first.")
        return False
    
    content = rendered_tex.read_text(encoding='utf-8')
    
    # Check for compact layout definition
    has_compact_def = (
        r'\newcommand{\compactresumelayout}' in content or
        r'\newcommand*{\compactresumelayout}' in content or
        r'\def\compactresumelayout' in content
    )
    
    # Check for compact layout call
    doc_start = content.find(r'\begin{document}')
    if doc_start >= 0:
        document_body = content[doc_start:]
        has_compact_call = (
            r'\compactresumelayout' in document_body and
            r'\newcommand' not in document_body[max(0, document_body.find(r'\compactresumelayout')-30):document_body.find(r'\compactresumelayout')]
        )
    else:
        has_compact_call = False
    
    print(f"Compact layout definition: {'[OK] Present' if has_compact_def else '[MISSING]'}")
    print(f"Compact layout call: {'[OK] Present' if has_compact_call else '[MISSING]'}")
    print()
    
    if has_compact_def and has_compact_call:
        print("[OK] Compact layout is properly applied")
    else:
        print("[WARNING] Compact layout may not be applied correctly")
    print()
    
    return has_compact_def and has_compact_call


def check_reduction_log():
    """Check if reduction log exists and is valid."""
    print("=" * 80)
    print("Test 5: Reduction Log Check")
    print("=" * 80)
    print()
    
    reduction_log_path = OUTPUT_DIR / "page_reduction_log.json"
    
    if not reduction_log_path.exists():
        print("[INFO] No reduction log found (iterative reduction may not have run)")
        return None
    
    try:
        log_data = json.loads(reduction_log_path.read_text(encoding='utf-8'))
        
        initial = log_data.get("initial_estimated_pages", 0)
        final = log_data.get("final_estimated_pages", 0)
        target_met = log_data.get("target_met", False)
        iterations = log_data.get("iterations", 0)
        
        print(f"Initial pages: {initial:.2f}")
        print(f"Final pages: {final:.2f}")
        print(f"Target met: {target_met}")
        print(f"Iterations: {iterations}")
        print()
        
        return log_data
    except Exception as e:
        print(f"[ERROR] Failed to read reduction log: {e}")
        return None


if __name__ == "__main__":
    print()
    print("Testing 2-Page Limit Enforcement")
    print()
    
    # Run all tests
    pages_estimated = test_length_estimation()
    metadata = test_length_budget_enforcement()
    reduction_log = test_iterative_reduction()
    compact_ok = test_compact_layout()
    log_data = check_reduction_log()
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    if pages_estimated:
        print(f"1. Length estimation: {pages_estimated:.2f} pages")
    
    if metadata:
        pages_after = metadata.get("estimated_pages_after", 0)
        print(f"2. After budget enforcement: {pages_after:.2f} pages")
        if pages_after > 2.0:
            print("   [WARNING] Still over 2 pages after enforcement!")
    
    if reduction_log:
        final_pages = reduction_log.get("final_estimated_pages", 0)
        target_met = reduction_log.get("target_met", False)
        print(f"3. After iterative reduction: {final_pages:.2f} pages")
        if target_met:
            print("   [OK] Target met")
        else:
            print("   [WARNING] Target not met")
    
    print(f"4. Compact layout: {'[OK] Applied' if compact_ok else '[MISSING]'}")
    print()
    
    # Overall status
    if metadata:
        final_pages = metadata.get("estimated_pages_after", 0)
        if reduction_log:
            final_pages = reduction_log.get("final_estimated_pages", final_pages)
        
        if final_pages <= 2.0:
            print("[SUCCESS] 2-page limit enforcement is working!")
        else:
            print(f"[FAILED] 2-page limit enforcement not working - final: {final_pages:.2f} pages")
    else:
        print("[UNKNOWN] Could not determine status - check logs above")
    print()

