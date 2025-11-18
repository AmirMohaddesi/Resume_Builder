"""
Test script for iterative page reduction tool.

Tests if the iterative removal tool can reduce a 3-page resume to 2 pages.
"""

import json
from pathlib import Path
from resume_builder.paths import OUTPUT_DIR
from resume_builder.iterative_page_reducer import iteratively_reduce_pages
from resume_builder.json_loaders import (
    load_summary_block,
    load_selected_experiences,
    load_selected_skills,
    load_selected_projects,
    load_education_block
)
from resume_builder.length_budget import estimate_lines, TARGET_LINES_PER_PAGE

def test_iterative_removal():
    """Test iterative page reduction on existing resume JSON files."""
    
    print("=" * 80)
    print("TEST: Iterative Page Reduction Tool")
    print("=" * 80)
    print()
    
    # Check if JSON files exist
    summary_path = OUTPUT_DIR / "summary.json"
    experience_path = OUTPUT_DIR / "selected_experiences.json"
    skills_path = OUTPUT_DIR / "selected_skills.json"
    projects_path = OUTPUT_DIR / "selected_projects.json"
    education_path = OUTPUT_DIR / "education.json"
    jd_path = OUTPUT_DIR / "parsed_jd.json"
    
    missing_files = []
    for name, path in [
        ("summary", summary_path),
        ("experiences", experience_path),
        ("skills", skills_path),
        ("JD", jd_path)
    ]:
        if not path.exists():
            missing_files.append(f"{name} ({path})")
    
    if missing_files:
        print("[ERROR] Missing required JSON files:")
        for f in missing_files:
            print(f"   - {f}")
        print()
        print("Please run the resume generation pipeline first to create these files.")
        return False
    
    # Load and estimate initial pages
    print("[STEP 1] Loading resume content and estimating pages...")
    summary_data = load_summary_block(summary_path)
    summary = summary_data.get('summary', '')
    
    exp_data = load_selected_experiences(experience_path)
    experiences = exp_data.get('selected_experiences', [])
    
    skills_data = load_selected_skills(skills_path)
    skills = skills_data.get('skills', skills_data.get('selected_skills', []))
    
    projects = []
    if projects_path.exists():
        proj_data = load_selected_projects(projects_path)
        projects = proj_data.get('selected_projects', [])
    
    education = []
    if education_path.exists():
        edu_data = load_education_block(education_path)
        education = edu_data.get('education', [])
    
    estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
    estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
    
    print(f"   Initial estimate: {estimated_lines} lines (~{estimated_pages:.2f} pages)")
    print(f"   Experiences: {len(experiences)}")
    print(f"   Projects: {len(projects)}")
    print(f"   Skills: {len(skills)}")
    print(f"   Education entries: {len(education)}")
    print()
    
    if estimated_pages <= 2.0:
        print("[OK] Resume already fits in 2 pages. No reduction needed.")
        print(f"   Current: {estimated_pages:.2f} pages")
        return True
    
    print(f"[WARNING] Resume exceeds 2-page limit: {estimated_pages:.2f} pages")
    print()
    print("[STEP 2] Running iterative page reduction...")
    print()
    
    # Run iterative reduction
    reduction_log = iteratively_reduce_pages(
        summary_path=summary_path,
        experience_path=experience_path,
        skills_path=skills_path,
        projects_path=projects_path if projects_path.exists() else None,
        education_path=education_path if education_path.exists() else None,
        jd_path=jd_path,
        target_pages=2.0,
        max_iterations=5
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Status: {reduction_log.get('status', 'unknown')}")
    message = reduction_log.get('message', 'N/A')
    # Replace Unicode characters for Windows console
    message = message.replace('≤', '<=').replace('≥', '>=').replace('⚠', '[WARNING]').replace('✅', '[OK]')
    print(f"Message: {message}")
    print(f"Iterations: {reduction_log.get('iterations', 0)}")
    print(f"Initial pages: {reduction_log.get('initial_estimated_pages', 0):.2f}")
    print(f"Final pages: {reduction_log.get('final_estimated_pages', 0):.2f}")
    print(f"Target met: {reduction_log.get('target_met', False)}")
    print()
    
    items_removed = reduction_log.get('items_removed', [])
    if items_removed:
        print(f"Items removed ({len(items_removed)}):")
        for item in items_removed:
            print(f"   [{item.get('iteration', '?')}] {item.get('type', 'unknown')}: {item.get('item', 'N/A')} ({item.get('reason', 'N/A')})")
    else:
        print("No items were removed.")
    print()
    
    # Verify final state
    print("[STEP 3] Verifying final state...")
    summary_data = load_summary_block(summary_path)
    summary = summary_data.get('summary', '')
    
    exp_data = load_selected_experiences(experience_path)
    experiences = exp_data.get('selected_experiences', [])
    
    skills_data = load_selected_skills(skills_path)
    skills = skills_data.get('skills', skills_data.get('selected_skills', []))
    
    if projects_path.exists():
        proj_data = load_selected_projects(projects_path)
        projects = proj_data.get('selected_projects', [])
    else:
        projects = []
    
    if education_path.exists():
        edu_data = load_education_block(education_path)
        education = edu_data.get('education', [])
    else:
        education = []
    
    final_lines = estimate_lines(summary, experiences, projects, skills, education)
    final_pages = final_lines / TARGET_LINES_PER_PAGE
    
    print(f"   Final estimate: {final_lines} lines (~{final_pages:.2f} pages)")
    print(f"   Experiences: {len(experiences)}")
    print(f"   Projects: {len(projects)}")
    print(f"   Skills: {len(skills)}")
    print(f"   Education entries: {len(education)}")
    print()
    
    # Check if target was met
    if final_pages <= 2.0:
        print("[SUCCESS] Resume reduced to <=2 pages!")
        print(f"   Final: {final_pages:.2f} pages (target: <=2.0)")
        return True
    else:
        print("[WARNING] Resume still exceeds 2-page limit")
        print(f"   Final: {final_pages:.2f} pages (target: <=2.0)")
        print(f"   Reduction: {estimated_pages - final_pages:.2f} pages")
        return False

if __name__ == "__main__":
    success = test_iterative_removal()
    exit(0 if success else 1)

