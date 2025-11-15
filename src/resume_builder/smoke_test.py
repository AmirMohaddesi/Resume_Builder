#!/usr/bin/env python
"""
Pipeline smoke test - quick validation of orchestrator → main → LaTeX chain.

Usage:
    uv run -m resume_builder.smoke_test
    python -m resume_builder.smoke_test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from resume_builder.main import run_pipeline
from resume_builder.paths import OUTPUT_DIR

# Minimal sample job description
SAMPLE_JD = """
Software Engineer Position

We are looking for a software engineer with experience in Python, machine learning, and cloud technologies.
The ideal candidate will have:
- 3+ years of Python development experience
- Experience with machine learning frameworks (PyTorch, TensorFlow)
- Cloud platform experience (AWS, GCP, or Azure)
- Strong problem-solving skills
- Excellent communication skills

This is a full-time position based in San Francisco, CA.
"""


def main():
    """Run a smoke test of the pipeline."""
    print("=" * 80)
    print("Resume Builder Pipeline Smoke Test")
    print("=" * 80)
    print()
    
    # Use default profile path
    profile_path = None  # Will use default
    
    print("Running pipeline with sample job description...")
    print(f"Profile: default (from data/profile.json)")
    print(f"Job Description: {len(SAMPLE_JD)} characters")
    print()
    
    try:
        pdf_path, status_message, cover_letter_pdf_path = run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=profile_path,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,  # No UI for smoke test
            debug=True  # Enable debug mode for smoke test
        )
        
        print("=" * 80)
        print("Pipeline Execution Complete")
        print("=" * 80)
        print()
        
        # Check pipeline_status.json
        pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
        if pipeline_status_path.exists():
            print("[OK] pipeline_status.json found")
            try:
                with open(pipeline_status_path, 'r', encoding='utf-8') as f:
                    pipeline_status = json.load(f)
                
                print("\nPipeline Status:")
                print(f"  ok: {pipeline_status.get('ok', 'N/A')}")
                print(f"  status: {pipeline_status.get('status', 'N/A')}")
                print(f"  ready_for_latex: {pipeline_status.get('ready_for_latex', 'N/A')}")
                print(f"  message: {pipeline_status.get('message', 'N/A')}")
                
                blocking_errors = pipeline_status.get('blocking_errors', [])
                if blocking_errors:
                    print(f"\n  Blocking Errors ({len(blocking_errors)}):")
                    for error in blocking_errors:
                        print(f"    - {error}")
                
                warnings = pipeline_status.get('warnings', [])
                if warnings:
                    print(f"\n  Warnings ({len(warnings)}):")
                    for warning in warnings:
                        print(f"    - {warning}")
                
                phase_status = pipeline_status.get('phase_status', {})
                if phase_status:
                    print(f"\n  Phase Status ({len(phase_status)} phases):")
                    for phase, status in phase_status.items():
                        print(f"    - {phase}: {status}")
                
                skipped = pipeline_status.get('what_was_skipped_and_why', [])
                if skipped:
                    print(f"\n  Skipped Phases ({len(skipped)}):")
                    for item in skipped:
                        print(f"    - {item.get('phase', 'unknown')}: {item.get('reason', 'unknown')}")
                
            except Exception as e:
                print(f"[ERROR] Error reading pipeline_status.json: {e}")
        else:
            print("[ERROR] pipeline_status.json NOT FOUND")
        
        print()
        print("Generated JSON Files:")
        json_files = [
            "user_profile.json",
            "validated_profile.json",
            "parsed_jd.json",
            "selected_experiences.json",
            "selected_projects.json",
            "selected_skills.json",
            "summary_block.json",
            "education_block.json",
            "ats_report.json",
            "privacy_validation_report.json",
            "cover_letter.json",
            "template_validation.json",
            "tailor_plan.json",
            "pipeline_status.json",
        ]
        
        for json_file in json_files:
            file_path = OUTPUT_DIR / json_file
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  [OK] {json_file} ({size} bytes)")
            else:
                print(f"  [WARN] {json_file} (not found)")
        
        # Check for debug file if debug mode was enabled
        debug_file = OUTPUT_DIR / "pipeline_status_debug.json"
        if debug_file.exists():
            print(f"\n  [DEBUG] pipeline_status_debug.json ({debug_file.stat().st_size} bytes)")
        
        # Check for cover letter PDF (new feature)
        if cover_letter_pdf_path and Path(cover_letter_pdf_path).exists():
            cover_letter_size = Path(cover_letter_pdf_path).stat().st_size
            print(f"\n  [OK] Cover Letter PDF Generated: {cover_letter_pdf_path} ({cover_letter_size} bytes)")
        else:
            cover_letter_json = OUTPUT_DIR / "cover_letter.json"
            if cover_letter_json.exists():
                print(f"\n  [WARN] Cover letter JSON exists but PDF not generated")
            else:
                print(f"\n  [INFO] Cover letter not generated (may be optional)")
        
        # Validate recent fixes
        print()
        print("=" * 80)
        print("Validating Recent Fixes")
        print("=" * 80)
        
        # Check 1: Education is optional (should not block if missing)
        education_json = OUTPUT_DIR / "education_block.json"
        if not education_json.exists():
            print("[OK] Education block is optional (can be missing)")
        else:
            print("[OK] Education block found")
        
        # Check 2: Cover letter JSON exists
        cover_letter_json = OUTPUT_DIR / "cover_letter.json"
        if cover_letter_json.exists():
            print("[OK] Cover letter JSON generated")
            try:
                with open(cover_letter_json, 'r', encoding='utf-8') as f:
                    cover_data = json.load(f)
                if cover_data.get('ok') and cover_data.get('cover_letter_md'):
                    print("[OK] Cover letter content is valid")
            except Exception as e:
                print(f"[WARN] Cover letter JSON exists but invalid: {e}")
        else:
            print("[INFO] Cover letter JSON not found (may be optional)")
        
        # Check 3: JSON files are valid (no control character errors)
        json_errors = []
        for json_file in json_files:
            file_path = OUTPUT_DIR / json_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    json_errors.append(f"{json_file}: {e}")
        
        if json_errors:
            print(f"[ERROR] JSON parsing errors found:")
            for error in json_errors:
                print(f"  - {error}")
        else:
            print("[OK] All JSON files are valid (no control character errors)")
        
        print()
        print("Final Status:")
        print(f"  Status Message: {status_message}")
        
        if pdf_path:
            pdf_size = Path(pdf_path).stat().st_size
            print(f"  [OK] PDF Generated: {pdf_path} ({pdf_size} bytes)")
            print()
            print("=" * 80)
            print("[OK] SMOKE TEST PASSED")
            print("=" * 80)
            return 0
        else:
            print(f"  [ERROR] PDF NOT Generated")
            print()
            print("=" * 80)
            print("[ERROR] SMOKE TEST FAILED")
            print("=" * 80)
            return 1
            
    except Exception as e:
        print(f"[ERROR] Smoke test failed with exception: {e}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())

