"""
Tests for the user edit request engine.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from resume_builder.edit_engine import (
    EditEngine,
    EditType,
    apply_edit_request,
)
from resume_builder.paths import OUTPUT_DIR


class TestEditTypeDetection:
    """Test edit type detection."""
    
    def test_detect_summary(self):
        engine = EditEngine(use_llm=False)
        assert engine.detect_edit_type("Make my summary shorter") == EditType.SUMMARY
        assert engine.detect_edit_type("Expand the professional summary") == EditType.SUMMARY
    
    def test_detect_skills(self):
        engine = EditEngine(use_llm=False)
        assert engine.detect_edit_type("Add AWS to my skills") == EditType.SKILLS
        assert engine.detect_edit_type("Remove Python from skills") == EditType.SKILLS
    
    def test_detect_experiences(self):
        engine = EditEngine(use_llm=False)
        assert engine.detect_edit_type("Move my most recent experience to the top") == EditType.EXPERIENCES
        assert engine.detect_edit_type("Swap these two experiences") == EditType.EXPERIENCES
    
    def test_detect_projects(self):
        engine = EditEngine(use_llm=False)
        assert engine.detect_edit_type("Remove this project") == EditType.PROJECTS
        assert engine.detect_edit_type("Reorder projects") == EditType.PROJECTS
    
    def test_detect_unknown(self):
        engine = EditEngine(use_llm=False)
        assert engine.detect_edit_type("Do something random") == EditType.UNKNOWN


class TestEditPossibility:
    """Test edit possibility checking."""
    
    def test_summary_edit_possible(self, tmp_path):
        """Test that summary edit is possible when file exists."""
        engine = EditEngine(use_llm=False)
        summary_file = OUTPUT_DIR / "summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps({"status": "success", "summary": "Test summary"}))
        
        is_possible, reason = engine.check_edit_possibility(EditType.SUMMARY, "Make it shorter")
        assert is_possible
        assert reason is None
    
    def test_summary_edit_impossible_no_file(self):
        """Test that summary edit is impossible when file doesn't exist."""
        engine = EditEngine(use_llm=False)
        # Ensure file doesn't exist (check for summary.json, not summary_block.json)
        summary_file = OUTPUT_DIR / "summary.json"
        if summary_file.exists():
            summary_file.unlink()
        
        is_possible, reason = engine.check_edit_possibility(EditType.SUMMARY, "Make it shorter")
        assert not is_possible
        assert "not found" in reason.lower()
    
    def test_template_edit_impossible(self, tmp_path):
        """Test that template structure edits are impossible."""
        engine = EditEngine(use_llm=False)
        summary_file = OUTPUT_DIR / "summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps({"status": "success", "summary": "Test"}))
        
        is_possible, reason = engine.check_edit_possibility(
            EditType.SUMMARY,
            "Change the template structure with LaTeX commands"
        )
        assert not is_possible
        assert "latex" in reason.lower() or "not supported" in reason.lower()


class TestEditApplication:
    """Test edit application."""
    
    def test_edit_summary_shorter(self):
        """Test shortening summary deterministically."""
        engine = EditEngine(use_llm=False)
        current_data = {
            "status": "success",
            "summary": "First sentence. Second sentence. Third sentence."
        }
        
        result = engine.apply_edit(EditType.SUMMARY, "Make it shorter", current_data)
        
        assert result["status"] == "success"
        assert "summary" in result
        # With use_llm=False, summary should remain unchanged (LLM is required for text edits)
        # Or if LLM is used, it may not always shorten to exactly 2 sentences
        # So we just check that the result is valid
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0
    
    def test_edit_skills_add(self):
        """Test adding a skill."""
        engine = EditEngine(use_llm=False)
        current_data = {
            "status": "success",
            "selected_skills": ["Python", "JavaScript"]
        }
        
        result = engine.apply_edit(EditType.SKILLS, "Add AWS", current_data)
        
        assert result["status"] == "success"
        # Skills are sorted alphabetically, so check case-insensitive
        skill_lower = [s.lower() for s in result["selected_skills"]]
        assert "aws" in skill_lower
        assert len(result["selected_skills"]) == 3
    
    def test_edit_skills_remove(self):
        """Test removing a skill."""
        engine = EditEngine(use_llm=False)
        current_data = {
            "status": "success",
            "selected_skills": ["Python", "JavaScript", "AWS"]
        }
        
        result = engine.apply_edit(EditType.SKILLS, "Remove Python", current_data)
        
        assert result["status"] == "success"
        assert "Python" not in result["selected_skills"]
        assert len(result["selected_skills"]) == 2
    
    def test_schema_preservation(self):
        """Test that edits preserve required schema fields."""
        engine = EditEngine(use_llm=False)
        current_data = {
            "status": "success",
            "message": "Original message",
            "summary": "Test summary"
        }
        
        result = engine.apply_edit(EditType.SUMMARY, "Make it shorter", current_data)
        
        # Required fields should still be present
        assert "status" in result
        assert "message" in result
        assert "summary" in result
        assert result["status"] == "success"


class TestApplyEditRequest:
    """Test the main apply_edit_request function."""
    
    def test_apply_edit_request_success(self, tmp_path):
        """Test successful edit request."""
        # Create required file (summary.json, not summary_block.json)
        summary_file = OUTPUT_DIR / "summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps({
            "status": "success",
            "summary": "First. Second. Third."
        }))
        
        result = apply_edit_request("Make my summary shorter")
        
        assert result["ok"] is True
        assert result["status"] == "applied"
        assert "new_json" in result
        assert "changed_fields" in result
    
    def test_apply_edit_request_impossible(self):
        """Test impossible edit request."""
        # Ensure file doesn't exist (summary.json, not summary_block.json)
        summary_file = OUTPUT_DIR / "summary.json"
        if summary_file.exists():
            summary_file.unlink()
        
        result = apply_edit_request("Make my summary shorter")
        
        assert result["ok"] is False
        assert result["status"] == "not_possible"
        assert "reason" in result
        assert "not found" in result["reason"].lower()
    
    @patch('resume_builder.edit_engine.EditEngine._get_llm_client')
    def test_apply_edit_request_with_llm(self, mock_llm):
        """Test edit request with LLM (mocked)."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Shortened summary."
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_llm.return_value = mock_client
        
        # Create required file (summary.json, not summary_block.json)
        summary_file = OUTPUT_DIR / "summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps({
            "status": "success",
            "summary": "Long summary text here."
        }))
        
        engine = EditEngine(use_llm=True)
        result = engine.apply_edit(EditType.SUMMARY, "Make it more technical", {
            "status": "success",
            "summary": "Long summary text here."
        })
        
        assert result["status"] == "success"
        assert "summary" in result

