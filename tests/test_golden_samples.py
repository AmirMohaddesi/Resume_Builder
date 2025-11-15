"""Tests that validate golden JSON samples against schemas."""
import json
from pathlib import Path

import pytest

from resume_builder.schema import (
    validate_pipeline_status,
    validate_parsed_jd,
    validate_selected_experiences,
    validate_selected_skills,
    validate_summary_block,
    validate_education_block,
)


# Get the tests/data directory
TESTS_DIR = Path(__file__).parent
DATA_DIR = TESTS_DIR / "data"


class TestGoldenSamples:
    """Tests that golden JSON samples pass schema validation."""
    
    def test_golden_pipeline_status(self):
        """Test that golden pipeline_status.json passes validation."""
        golden_file = DATA_DIR / "pipeline_status.json"
        if not golden_file.exists():
            pytest.skip(f"Golden file not found: {golden_file}")
        
        with open(golden_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        is_valid, errors = validate_pipeline_status(data)
        assert is_valid, f"Validation errors: {errors}"
    
    def test_golden_tailor_plan(self):
        """Test that golden tailor_plan.json has required fields."""
        golden_file = DATA_DIR / "tailor_plan.json"
        if not golden_file.exists():
            pytest.skip(f"Golden file not found: {golden_file}")
        
        with open(golden_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Basic structure check
        assert "ok" in data
        assert "status" in data
        assert "message" in data
        assert "plan" in data
        assert "mode" in data  # Should match pipeline_status mode
    
    def test_golden_parsed_jd(self):
        """Test that golden parsed_jd.json passes validation."""
        golden_file = DATA_DIR / "parsed_jd.json"
        if not golden_file.exists():
            pytest.skip(f"Golden file not found: {golden_file}")
        
        with open(golden_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        is_valid, errors = validate_parsed_jd(data)
        assert is_valid, f"Validation errors: {errors}"
    
    def test_golden_selected_experiences(self):
        """Test that golden selected_experiences.json passes validation."""
        golden_file = DATA_DIR / "selected_experiences.json"
        if not golden_file.exists():
            pytest.skip(f"Golden file not found: {golden_file}")
        
        with open(golden_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        is_valid, errors = validate_selected_experiences(data)
        assert is_valid, f"Validation errors: {errors}"

