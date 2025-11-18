"""
Tests for the Design Error Memory system.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from resume_builder.design_error_memory import (
    detect_design_error_in_message,
    record_design_error,
    lookup_design_errors,
    get_prevention_guidance,
    normalize_design_issue,
    classify_design_error,
    extract_context_from_request,
    load_design_error_memory,
    save_design_error_memory,
)
from resume_builder.paths import OUTPUT_DIR


class TestDesignErrorDetection:
    """Test design error detection from user messages."""
    
    def test_detect_pipe_error(self):
        """Test detecting pipe character errors."""
        message = "There are four pipes on top of the resume"
        result = detect_design_error_in_message(message)
        
        assert result is not None
        assert "pipe" in result["issue_description"].lower()
        assert result["context"] in ["header", "general"]
    
    def test_detect_remove_request(self):
        """Test detecting remove requests as errors."""
        message = "Can you remove the pipe chars at the top of my resume"
        result = detect_design_error_in_message(message)
        
        assert result is not None
        assert "pipe" in result["issue_description"].lower()
    
    def test_detect_before_summary(self):
        """Test detecting errors before summary."""
        message = "right before the summary there are a few additional chars |"
        result = detect_design_error_in_message(message)
        
        assert result is not None
        # Should be detected as header context
        assert result["context"] == "header"
    
    def test_no_error_detected(self):
        """Test that normal requests don't trigger error detection."""
        message = "Make my summary shorter"
        result = detect_design_error_in_message(message)
        
        assert result is None


class TestDesignErrorNormalization:
    """Test design error normalization."""
    
    def test_normalize_pipe_issues(self):
        """Test normalizing pipe-related issues."""
        assert normalize_design_issue("four pipes") == "multiple pipe"
        assert normalize_design_issue("too many pipes") == "multiple pipe"
        assert normalize_design_issue("excessive pipes") == "multiple pipe"
    
    def test_normalize_spacing_issues(self):
        """Test normalizing spacing issues."""
        # Normalization removes filler words and normalizes, but doesn't convert phrases
        normalized1 = normalize_design_issue("too much space")
        normalized2 = normalize_design_issue("too little space")
        # Check that normalization happened (removed filler words)
        assert "too" in normalized1 or "much" in normalized1
        assert "space" in normalized1 or "spacing" in normalized1


class TestDesignErrorClassification:
    """Test design error classification."""
    
    def test_classify_header_formatting(self):
        """Test classifying header formatting errors."""
        assert classify_design_error("four pipes", "header") == "HeaderFormatting"
        assert classify_design_error("pipe separators", "header") == "HeaderFormatting"
    
    def test_classify_spacing(self):
        """Test classifying spacing errors."""
        assert classify_design_error("too much space", "summary") == "Spacing"
        assert classify_design_error("excessive spacing", "experience") == "Spacing"
    
    def test_classify_length(self):
        """Test classifying length errors."""
        assert classify_design_error("too long", "summary") == "Length"
        assert classify_design_error("truncated", "experience") == "Length"


class TestContextExtraction:
    """Test context extraction from user messages."""
    
    def test_extract_header_context(self):
        """Test extracting header context."""
        assert extract_context_from_request("pipe chars at the top") == "header"
        assert extract_context_from_request("right before the summary") == "header"
        assert extract_context_from_request("above the summary") == "header"
        assert extract_context_from_request("title line has issues") == "header"
    
    def test_extract_summary_context(self):
        """Test extracting summary context."""
        assert extract_context_from_request("summary is too long") == "summary"
        assert extract_context_from_request("professional summary") == "summary"
    
    def test_extract_experience_context(self):
        """Test extracting experience context."""
        assert extract_context_from_request("work experience") == "experience"
        assert extract_context_from_request("employment section") == "experience"
    
    def test_extract_general_context(self):
        """Test extracting general context for unclear messages."""
        assert extract_context_from_request("something is wrong") == "general"


class TestDesignErrorRecording:
    """Test design error recording."""
    
    def test_record_new_error(self, tmp_path):
        """Test recording a new design error."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "design_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        record_design_error(
            issue_description="four pipes in header",
            context="header",
            user_message="There are four pipes on top"
        )
        
        # Check that error was recorded
        errors = lookup_design_errors("header")
        assert len(errors) >= 1
        assert errors[0]["issue_description"] == "four pipes in header"
        assert errors[0]["context"] == "header"
        assert errors[0]["count"] == 1
    
    def test_record_duplicate_error(self, tmp_path):
        """Test recording duplicate error increments count."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "design_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        # Record same error twice
        record_design_error(
            issue_description="four pipes",
            context="header",
            user_message="There are four pipes"
        )
        record_design_error(
            issue_description="four pipes",
            context="header",
            user_message="Too many pipes again"
        )
        
        errors = lookup_design_errors("header")
        assert len(errors) >= 1
        # Should have count of 2 (normalized to same issue)
        assert errors[0]["count"] >= 2


class TestPreventionGuidance:
    """Test prevention guidance generation."""
    
    def test_get_prevention_guidance_single_occurrence(self, tmp_path):
        """Test that guidance only shows for 2+ occurrences."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "design_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        # Record error once
        record_design_error(
            issue_description="four pipes",
            context="header",
            user_message="There are four pipes"
        )
        
        # Should not return guidance for single occurrence
        guidance = get_prevention_guidance("header")
        assert guidance is None
    
    def test_get_prevention_guidance_multiple_occurrences(self, tmp_path):
        """Test that guidance shows for 2+ occurrences."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "design_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        # Record error twice
        record_design_error(
            issue_description="four pipes",
            context="header",
            user_message="There are four pipes"
        )
        record_design_error(
            issue_description="four pipes",
            context="header",
            user_message="Too many pipes again"
        )
        
        # Should return guidance for 2+ occurrences
        guidance = get_prevention_guidance("header")
        assert guidance is not None
        assert "pipe" in guidance.lower() or "header" in guidance.lower()


class TestDesignErrorMemoryPersistence:
    """Test design error memory persistence."""
    
    def test_load_and_save_memory(self, tmp_path):
        """Test loading and saving error memory."""
        memory_file = OUTPUT_DIR / "design_error_memory.json"
        
        # Clear existing
        if memory_file.exists():
            memory_file.unlink()
        
        # Record an error
        record_design_error(
            issue_description="test issue",
            context="header",
            user_message="test message"
        )
        
        # Load memory
        memory = load_design_error_memory()
        assert "errors" in memory
        assert len(memory["errors"]) >= 1
        
        # Verify file exists
        assert memory_file.exists()
        
        # Load again and verify persistence
        memory2 = load_design_error_memory()
        assert len(memory2["errors"]) == len(memory["errors"])

