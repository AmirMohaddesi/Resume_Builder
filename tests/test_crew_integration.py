"""
Pytest-based crew integration test.

Tests the full pipeline execution to catch errors before long runs.
This is faster to run than manual testing and integrates with CI/CD.
"""
import json
from pathlib import Path

import pytest

from resume_builder.main import run_pipeline
from resume_builder.paths import OUTPUT_DIR


# Minimal sample job description for testing
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


@pytest.fixture(scope="function")
def clean_output_dir():
    """Clean output directory before each test."""
    # Note: We don't clean everything - user_profile.json might be needed
    # Just clean the generated files that could cause conflicts
    files_to_clean = [
        "pipeline_status.json",
        "file_collection_report.json",
        "validated_profile.json",
    ]
    for file in files_to_clean:
        path = OUTPUT_DIR / file
        if path.exists():
            path.unlink()
    yield
    # Cleanup after test if needed


@pytest.mark.integration
class TestCrewIntegration:
    """Integration tests for the full crew pipeline."""
    
    def test_pipeline_executes_without_crashing(self, clean_output_dir):
        """Test that pipeline runs without exceptions."""
        pdf_path, status_message, cover_letter_pdf = run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,  # Uses default
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        # Pipeline should complete (even if blocked)
        assert status_message is not None
        # Status should be a string (not an exception)
        assert isinstance(status_message, str)
    
    def test_pipeline_status_json_generated(self, clean_output_dir):
        """Test that pipeline_status.json is generated."""
        run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
        assert pipeline_status_path.exists(), "pipeline_status.json should be generated"
        
        # Should be valid JSON
        with open(pipeline_status_path, 'r', encoding='utf-8') as f:
            pipeline_status = json.load(f)
        
        # Should have required fields
        assert "ok" in pipeline_status
        assert "status" in pipeline_status
        assert "ready_for_latex" in pipeline_status
        assert "blocking_errors" in pipeline_status
        assert "phase_status" in pipeline_status
    
    def test_file_collection_report_schema(self, clean_output_dir):
        """Test that file_collection_report.json has correct schema when phone is missing."""
        run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        file_collection_path = OUTPUT_DIR / "file_collection_report.json"
        if file_collection_path.exists():
            with open(file_collection_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # If phone is missing but email exists, ok should be true
            validation = report.get("validation", {})
            email_present = validation.get("email_present", False)
            phone_present = validation.get("phone_present", False)
            
            if email_present and not phone_present:
                # Phone missing should be ok=true, status="warning" (non-blocking)
                assert report.get("ok") is True, "Phone missing should not block if email exists"
                assert report.get("status") == "warning", "Phone missing should be warning, not error"
    
    def test_cover_letter_schema(self, clean_output_dir):
        """Test that cover_letter.json has correct schema."""
        run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        cover_letter_path = OUTPUT_DIR / "cover_letter.json"
        if cover_letter_path.exists():
            with open(cover_letter_path, 'r', encoding='utf-8') as f:
                cover_letter = json.load(f)
            
            # Should have required fields
            assert "ok" in cover_letter, "cover_letter.json missing 'ok' field"
            assert "status" in cover_letter, "cover_letter.json missing 'status' field"
            assert "cover_letter_md" in cover_letter, "cover_letter.json missing 'cover_letter_md' field (not 'cover_letter')"
    
    def test_all_json_files_valid(self, clean_output_dir):
        """Test that all generated JSON files are valid (no parsing errors)."""
        run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        json_files = [
            "pipeline_status.json",
            "file_collection_report.json",
            "validated_profile.json",
            "selected_experiences.json",
            "selected_skills.json",
            "summary_block.json",
            "cover_letter.json",
        ]
        
        json_errors = []
        for json_file in json_files:
            file_path = OUTPUT_DIR / json_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    json_errors.append(f"{json_file}: {e}")
        
        assert len(json_errors) == 0, f"JSON parsing errors: {json_errors}"
    
    def test_pipeline_not_blocked_by_phone_missing(self, clean_output_dir):
        """Test that pipeline doesn't block when phone is missing but email exists."""
        run_pipeline(
            jd_text=SAMPLE_JD,
            profile_path=None,
            custom_template_path=None,
            reference_pdf_paths=None,
            progress_callback=None,
            debug=True
        )
        
        pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
        if pipeline_status_path.exists():
            with open(pipeline_status_path, 'r', encoding='utf-8') as f:
                pipeline_status = json.load(f)
            
            file_collection_path = OUTPUT_DIR / "file_collection_report.json"
            if file_collection_path.exists():
                with open(file_collection_path, 'r', encoding='utf-8') as f:
                    file_collection = json.load(f)
                
                validation = file_collection.get("validation", {})
                email_present = validation.get("email_present", False)
                phone_present = validation.get("phone_present", False)
                
                # If email exists but phone is missing, pipeline should not be blocked
                if email_present and not phone_present:
                    blocking_errors = pipeline_status.get("blocking_errors", [])
                    phone_related_errors = [e for e in blocking_errors if "file_collection_report" in e.lower() and "phone" in e.lower()]
                    assert len(phone_related_errors) == 0, f"Pipeline blocked by phone missing: {blocking_errors}"

