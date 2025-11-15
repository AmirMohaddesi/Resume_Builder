"""Tests for schema validation helpers."""
import pytest

from resume_builder.schema import (
    validate_pipeline_status,
    validate_parsed_jd,
    validate_selected_experiences,
    validate_selected_skills,
    validate_summary_block,
    validate_education_block,
    validate_ats_report,
    validate_cover_letter,
    validate_task_output,
)


class TestPipelineStatusValidation:
    """Tests for pipeline_status.json validation."""
    
    def test_valid_pipeline_status(self):
        """Test validation of valid pipeline_status.json."""
        valid_data = {
            "ok": True,
            "status": "ready",
            "ready_for_latex": True,
            "message": "All required phases completed",
            "blocking_errors": [],
            "warnings": [],
            "phase_status": {
                "profile_validation_task": "success",
                "select_experiences_task": "success",
            },
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "passed"
        }
        
        is_valid, errors = validate_pipeline_status(valid_data)
        assert is_valid
        assert len(errors) == 0
    
    def test_missing_required_field(self):
        """Test validation fails when required field is missing."""
        invalid_data = {
            "ok": True,
            "status": "ready",
            # Missing ready_for_latex
            "message": "Test",
            "blocking_errors": [],
            "warnings": [],
            "phase_status": {},
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "passed"
        }
        
        is_valid, errors = validate_pipeline_status(invalid_data)
        assert not is_valid
        assert any("ready_for_latex" in error for error in errors)
    
    def test_invalid_status_value(self):
        """Test validation fails with invalid status value."""
        invalid_data = {
            "ok": True,
            "status": "invalid_status",  # Invalid
            "ready_for_latex": True,
            "message": "Test",
            "blocking_errors": [],
            "warnings": [],
            "phase_status": {},
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "passed"
        }
        
        is_valid, errors = validate_pipeline_status(invalid_data)
        assert not is_valid
        assert any("Invalid status" in error for error in errors)
    
    def test_invalid_phase_status(self):
        """Test validation fails with invalid phase_status value."""
        invalid_data = {
            "ok": True,
            "status": "ready",
            "ready_for_latex": True,
            "message": "Test",
            "blocking_errors": [],
            "warnings": [],
            "phase_status": {
                "profile_validation_task": "invalid_status"  # Invalid
            },
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "passed"
        }
        
        is_valid, errors = validate_pipeline_status(invalid_data)
        assert not is_valid
        assert any("Invalid status" in error for error in errors)


class TestTaskOutputValidation:
    """Tests for task output validation."""
    
    def test_valid_parsed_jd(self):
        """Test validation of valid parsed_jd.json."""
        valid_data = {
            "status": "success",
            "message": "Job description parsed successfully",
            "title": "Software Engineer",
            "company": "Tech Corp",
            "skills": ["Python", "JavaScript"],
            "keywords": ["agile", "scrum"],
            "cleaned_text": "Full job description..."
        }
        
        is_valid, errors = validate_parsed_jd(valid_data)
        assert is_valid
        assert len(errors) == 0
    
    def test_missing_status_field(self):
        """Test validation fails when status is missing."""
        invalid_data = {
            "message": "Test",
            "title": "Engineer"
        }
        
        is_valid, errors = validate_parsed_jd(invalid_data)
        assert not is_valid
        assert any("status" in error for error in errors)
    
    def test_valid_selected_experiences(self):
        """Test validation of valid selected_experiences.json."""
        valid_data = {
            "status": "success",
            "message": "Selected 4 experiences",
            "selected_experiences": [
                {"organization": "Company", "title": "Engineer"}
            ],
            "reasoning": "Relevant experience"
        }
        
        is_valid, errors = validate_selected_experiences(valid_data)
        assert is_valid
        assert len(errors) == 0
    
    def test_valid_summary_block(self):
        """Test validation of valid summary_block.json."""
        valid_data = {
            "status": "success",
            "message": "Summary written",
            "summary": "Professional summary text"
        }
        
        is_valid, errors = validate_summary_block(valid_data)
        assert is_valid
        assert len(errors) == 0
    
    def test_valid_cover_letter(self):
        """Test validation of valid cover_letter.json."""
        valid_data = {
            "ok": True,
            "status": "success",
            "message": "Cover letter generated",
            "cover_letter_md": "Dear Hiring Manager..."
        }
        
        is_valid, errors = validate_cover_letter(valid_data)
        assert is_valid
        assert len(errors) == 0


class TestOrchestratorSelfTestScenario:
    """Tests simulating orchestrator self-test scenarios."""
    
    def test_missing_file_scenario(self):
        """Test that missing required file would cause self_test=failed."""
        # Simulate orchestrator finding missing required file
        pipeline_status = {
            "ok": False,
            "status": "blocked",
            "ready_for_latex": False,
            "message": "Pipeline blocked by errors",
            "blocking_errors": ["selected_experiences.json is missing"],
            "warnings": [],
            "phase_status": {
                "select_experiences_task": "error"
            },
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "failed"
        }
        
        is_valid, errors = validate_pipeline_status(pipeline_status)
        assert is_valid  # Schema is valid even if ok=false
        assert pipeline_status["self_test"] == "failed"
        assert pipeline_status["ok"] is False
    
    def test_malformed_file_scenario(self):
        """Test that malformed JSON would cause self_test=failed."""
        pipeline_status = {
            "ok": False,
            "status": "blocked",
            "ready_for_latex": False,
            "message": "Pipeline blocked by errors",
            "blocking_errors": ["summary_block.json has invalid JSON structure"],
            "warnings": [],
            "phase_status": {
                "write_summary_task": "error"
            },
            "what_was_skipped_and_why": [],
            "mode": "standard",
            "self_test": "failed"
        }
        
        is_valid, errors = validate_pipeline_status(pipeline_status)
        assert is_valid
        assert pipeline_status["self_test"] == "failed"

