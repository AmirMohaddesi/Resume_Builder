"""
Test iterative page reduction on a larger resume (3+ pages).

Temporarily expands the resume content, then tests the removal tool.
"""

import json
import time
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

def expand_resume_for_testing():
    """Temporarily expand resume content to make it 3+ pages."""
    
    print("=" * 80)
    print("EXPANDING RESUME FOR TESTING (3+ pages)")
    print("=" * 80)
    print()
    
    # Backup original files
    summary_path = OUTPUT_DIR / "summary.json"
    exp_path = OUTPUT_DIR / "selected_experiences.json"
    skills_path = OUTPUT_DIR / "selected_skills.json"
    projects_path = OUTPUT_DIR / "selected_projects.json"
    
    backups = {}
    for path in [summary_path, exp_path, skills_path, projects_path]:
        if path.exists():
            backups[path] = path.read_text(encoding='utf-8')
    
    try:
        # Expand summary
        if summary_path.exists():
            summary_data = load_summary_block(summary_path)
            original_summary = summary_data.get('summary', '')
            # Add more content to summary
            expanded_summary = original_summary + " " + " ".join([
                "Experienced professional with extensive background in software development, machine learning, and robotics.",
                "Strong expertise in Python, PyTorch, ROS2, and distributed systems.",
                "Proven track record in building scalable applications and leading technical teams.",
                "Excellent problem-solving skills and ability to work in fast-paced environments.",
                "Passionate about innovation and continuous learning in emerging technologies."
            ] * 3)  # Repeat 3 times
            summary_data['summary'] = expanded_summary
            summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"[EXPANDED] Summary: {len(original_summary.split())} -> {len(expanded_summary.split())} words")
        
        # Expand experiences with more bullets
        if exp_path.exists():
            exp_data = load_selected_experiences(exp_path)
            experiences = exp_data.get('selected_experiences', [])
            for exp in experiences:
                bullets = exp.get('bullets', [])
                # Add more bullets
                new_bullets = bullets + [
                    "Led cross-functional teams to deliver high-impact projects on time and within budget.",
                    "Implemented best practices for code quality, testing, and documentation.",
                    "Mentored junior developers and conducted technical interviews.",
                    "Collaborated with stakeholders to define requirements and technical specifications.",
                    "Optimized system performance and reduced operational costs by 30%."
                ]
                exp['bullets'] = new_bullets
            exp_data['selected_experiences'] = experiences
            exp_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"[EXPANDED] Experiences: Added 5 bullets per experience")
        
        # Expand skills
        if skills_path.exists():
            skills_data = load_selected_skills(skills_path)
            skills = skills_data.get('skills', [])
            # Add many more skills
            additional_skills = [
                "Docker", "Kubernetes", "AWS", "Azure", "GCP",
                "TensorFlow", "Keras", "Scikit-learn", "Pandas", "NumPy",
                "React", "Node.js", "JavaScript", "TypeScript", "HTML/CSS",
                "MongoDB", "PostgreSQL", "Redis", "Elasticsearch", "Kafka",
                "Git", "CI/CD", "Jenkins", "GitLab", "GitHub Actions",
                "Agile", "Scrum", "JIRA", "Confluence", "Slack"
            ]
            skills_data['skills'] = skills + additional_skills
            skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"[EXPANDED] Skills: {len(skills)} -> {len(skills_data['skills'])} skills")
        
        # Add more projects if possible
        if projects_path.exists():
            proj_data = load_selected_projects(projects_path)
            projects = proj_data.get('selected_projects', [])
            # Add a few more projects
            new_projects = [
                {
                    "name": "Distributed ML Training System",
                    "bullets": [
                        "Built scalable distributed training pipeline using PyTorch and Horovod",
                        "Reduced training time by 60% through optimization and parallelization",
                        "Deployed on AWS with auto-scaling capabilities"
                    ]
                },
                {
                    "name": "Real-time Analytics Dashboard",
                    "bullets": [
                        "Developed real-time dashboard using React and WebSocket connections",
                        "Processed millions of events per second using Kafka and Redis",
                        "Improved user engagement by 40% through better data visualization"
                    ]
                }
            ]
            proj_data['selected_projects'] = projects + new_projects
            projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"[EXPANDED] Projects: {len(projects)} -> {len(proj_data['selected_projects'])} projects")
        
        # Estimate new page count
        summary_data = load_summary_block(summary_path)
        exp_data = load_selected_experiences(exp_path)
        skills_data = load_selected_skills(skills_path)
        proj_data = load_selected_projects(projects_path) if projects_path.exists() else None
        
        estimated_lines = estimate_lines(
            summary_data.get('summary', ''),
            exp_data.get('selected_experiences', []),
            proj_data.get('selected_projects', []) if proj_data else [],
            skills_data.get('skills', []),
            []
        )
        estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
        
        print()
        print(f"[RESULT] Expanded resume: {estimated_lines} lines (~{estimated_pages:.2f} pages)")
        print()
        
        return estimated_pages >= 3.0
        
    except Exception as e:
        print(f"[ERROR] Failed to expand resume: {e}")
        # Restore backups
        for path, content in backups.items():
            path.write_text(content, encoding='utf-8')
        return False

def restore_backups(backups):
    """Restore original files from backups."""
    print()
    print("[RESTORING] Original resume files...")
    for path, content in backups.items():
        path.write_text(content, encoding='utf-8')
    print("[RESTORED] Original files restored")

def test_large_resume_reduction():
    """Test iterative page reduction on a large resume."""
    
    print("=" * 80)
    print("TEST: Iterative Page Reduction on Large Resume (3+ pages)")
    print("=" * 80)
    print()
    
    # Check if required files exist
    required_files = [
        ("summary", OUTPUT_DIR / "summary.json"),
        ("experiences", OUTPUT_DIR / "selected_experiences.json"),
        ("skills", OUTPUT_DIR / "selected_skills.json"),
        ("JD", OUTPUT_DIR / "parsed_jd.json")
    ]
    
    missing = [name for name, path in required_files if not path.exists()]
    if missing:
        print(f"[ERROR] Missing files: {', '.join(missing)}")
        print("Please run resume generation first.")
        return False
    
    # Backup original files
    backups = {}
    for name, path in required_files:
        if path.exists():
            backups[path] = path.read_text(encoding='utf-8')
    
    try:
        # Expand resume to 3+ pages
        if not expand_resume_for_testing():
            print("[WARNING] Could not expand resume to 3+ pages")
            return False
        
        # Load and estimate
        summary_data = load_summary_block(OUTPUT_DIR / "summary.json")
        exp_data = load_selected_experiences(OUTPUT_DIR / "selected_experiences.json")
        skills_data = load_selected_skills(OUTPUT_DIR / "selected_skills.json")
        proj_data = load_selected_projects(OUTPUT_DIR / "selected_projects.json") if (OUTPUT_DIR / "selected_projects.json").exists() else None
        
        initial_lines = estimate_lines(
            summary_data.get('summary', ''),
            exp_data.get('selected_experiences', []),
            proj_data.get('selected_projects', []) if proj_data else [],
            skills_data.get('skills', []),
            []
        )
        initial_pages = initial_lines / TARGET_LINES_PER_PAGE
        
        print(f"[INITIAL] Resume: {initial_lines} lines (~{initial_pages:.2f} pages)")
        print()
        
        if initial_pages <= 2.0:
            print("[SKIP] Resume is already <=2 pages after expansion")
            restore_backups(backups)
            return True
        
        # Run iterative reduction with timing
        print("[TESTING] Running iterative page reduction...")
        print()
        
        start_time = time.time()
        
        reduction_log = iteratively_reduce_pages(
            summary_path=OUTPUT_DIR / "summary.json",
            experience_path=OUTPUT_DIR / "selected_experiences.json",
            skills_path=OUTPUT_DIR / "selected_skills.json",
            projects_path=OUTPUT_DIR / "selected_projects.json" if (OUTPUT_DIR / "selected_projects.json").exists() else None,
            education_path=OUTPUT_DIR / "education.json" if (OUTPUT_DIR / "education.json").exists() else None,
            jd_path=OUTPUT_DIR / "parsed_jd.json",
            target_pages=2.0,
            max_iterations=5
        )
        
        elapsed_time = time.time() - start_time
        
        # Final estimate (BEFORE restoring backups) - use reduction log first
        final_pages = reduction_log.get('final_estimated_pages', 0)
        
        # If reduction log doesn't have final estimate, calculate it
        if final_pages == 0:
            summary_data = load_summary_block(OUTPUT_DIR / "summary.json")
            exp_data = load_selected_experiences(OUTPUT_DIR / "selected_experiences.json")
            skills_data = load_selected_skills(OUTPUT_DIR / "selected_skills.json")
            proj_data = load_selected_projects(OUTPUT_DIR / "selected_projects.json") if (OUTPUT_DIR / "selected_projects.json").exists() else None
            
            final_lines = estimate_lines(
                summary_data.get('summary', ''),
                exp_data.get('selected_experiences', []),
                proj_data.get('selected_projects', []) if proj_data else [],
                skills_data.get('skills', []),
                []
            )
            final_pages = final_lines / TARGET_LINES_PER_PAGE
        
        # Results
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)
        print()
        print(f"Status: {reduction_log.get('status', 'unknown')}")
        message = reduction_log.get('message', 'N/A')
        message = message.replace('≤', '<=').replace('≥', '>=')
        print(f"Message: {message}")
        print(f"Iterations: {reduction_log.get('iterations', 0)}")
        print(f"Initial pages: {initial_pages:.2f}")
        print(f"Final pages: {final_pages:.2f}")
        print(f"Reduction: {initial_pages - final_pages:.2f} pages")
        print(f"Time taken: {elapsed_time:.1f} seconds")
        print(f"Target met: {reduction_log.get('target_met', False)}")
        print()
        
        items_removed = reduction_log.get('items_removed', [])
        if items_removed:
            print(f"Items removed ({len(items_removed)}):")
            for item in items_removed:
                print(f"  [{item.get('iteration', '?')}] {item.get('type', 'unknown')}: {item.get('item', 'N/A')[:50]}")
        print()
        
        # Success check
        if final_pages <= 2.0:
            print("[SUCCESS] Resume successfully reduced to <=2 pages!")
            print(f"  Initial: {initial_pages:.2f} pages")
            print(f"  Final: {final_pages:.2f} pages")
            print(f"  Time: {elapsed_time:.1f}s")
            success = True
        else:
            print("[PARTIAL] Resume reduced but still exceeds 2 pages")
            print(f"  Initial: {initial_pages:.2f} pages")
            print(f"  Final: {final_pages:.2f} pages")
            print(f"  Reduction: {initial_pages - final_pages:.2f} pages")
            success = False
        
        return success
        
    finally:
        # Always restore backups
        restore_backups(backups)

if __name__ == "__main__":
    success = test_large_resume_reduction()
    exit(0 if success else 1)

