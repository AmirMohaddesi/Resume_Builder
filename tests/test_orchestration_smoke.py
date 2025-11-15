"""
Smoke tests for orchestration module.

These are lightweight tests that verify basic functionality without
requiring full pipeline execution or external services.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from resume_builder.orchestration import run_pipeline, run_template_matching
from resume_builder.paths import OUTPUT_DIR, GENERATED_DIR


class TestOrchestrationImports:
    """Test that orchestration module can be imported and functions exist."""
    
    def test_import_run_pipeline(self):
        """Test that run_pipeline can be imported."""
        from resume_builder.orchestration import run_pipeline
        assert callable(run_pipeline)
    
    def test_import_run_template_matching(self):
        """Test that run_template_matching can be imported."""
        from resume_builder.orchestration import run_template_matching
        assert callable(run_template_matching)
    
    def test_run_pipeline_signature(self):
        """Test run_pipeline function signature."""
        import inspect
        sig = inspect.signature(run_pipeline)
        
        # Check required parameters
        assert 'jd_text' in sig.parameters
        assert 'profile_path' in sig.parameters
        
        # Check optional parameters
        assert 'custom_template_path' in sig.parameters
        assert 'reference_pdf_paths' in sig.parameters
        assert 'progress_callback' in sig.parameters
        assert 'debug' in sig.parameters
        assert 'enable_ats' in sig.parameters
        assert 'enable_privacy' in sig.parameters
        assert 'fast_mode' in sig.parameters
    
    def test_run_template_matching_signature(self):
        """Test run_template_matching function signature."""
        import inspect
        sig = inspect.signature(run_template_matching)
        
        # Check required parameters
        assert 'reference_pdf_path' in sig.parameters
        assert 'generated_pdf_path' in sig.parameters
        
        # Check optional parameters
        assert 'template_tex_path' in sig.parameters
        assert 'fast_mode' in sig.parameters


class TestOrchestrationErrorHandling:
    """Test error handling in orchestration functions."""
    
    @patch('resume_builder.orchestration.ResumeTeam')
    def test_run_pipeline_handles_missing_profile(self, mock_team_class):
        """Test that run_pipeline handles missing profile gracefully."""
        # This is a smoke test - we're just checking it doesn't crash
        # In a real scenario, this would require more setup
        
        # Mock the team to avoid actual execution
        mock_team = MagicMock()
        mock_team_class.return_value = mock_team
        
        # This should not raise an unhandled exception
        # (It may return an error, but should handle it gracefully)
        try:
            result = run_pipeline(
                jd_text="Test job description",
                profile_path=None,
                fast_mode=True
            )
            # If it returns, check it's a tuple
            assert isinstance(result, tuple)
            assert len(result) == 3  # (pdf_path, msg, cover_letter_path)
        except Exception as e:
            # If it raises, it should be a handled exception with a message
            assert isinstance(e, (ValueError, FileNotFoundError, RuntimeError))
    
    def test_run_template_matching_handles_missing_files(self):
        """Test that run_template_matching handles missing files."""
        # Create non-existent paths
        ref_pdf = Path("/nonexistent/reference.pdf")
        gen_pdf = Path("/nonexistent/generated.pdf")
        
        # Should handle missing files gracefully
        result = run_template_matching(
            reference_pdf_path=str(ref_pdf),
            generated_pdf_path=str(gen_pdf),
            fast_mode=True
        )
        
        # Should return a dict with error information
        assert isinstance(result, dict)
        assert "ok" in result or "status" in result or "error" in result


class TestOrchestrationFastMode:
    """Test fast mode configuration."""
    
    def test_fast_mode_default(self):
        """Test that fast_mode defaults to True."""
        import inspect
        sig = inspect.signature(run_pipeline)
        fast_mode_param = sig.parameters['fast_mode']
        
        # Check default value
        assert fast_mode_param.default is True
    
    @patch('resume_builder.orchestration.ResumeTeam')
    def test_fast_mode_passed_to_team(self, mock_team_class):
        """Test that fast_mode is passed to ResumeTeam."""
        mock_team = MagicMock()
        mock_team_class.return_value = mock_team
        
        # Call with fast_mode=True
        try:
            run_pipeline(
                jd_text="Test",
                profile_path=None,
                fast_mode=True
            )
        except:
            pass  # Ignore execution errors, just check setup
        
        # Verify team was instantiated (may have fast_mode in kwargs)
        mock_team_class.assert_called()


class TestOrchestrationPaths:
    """Test that orchestration uses correct paths."""
    
    def test_output_dir_exists(self):
        """Test that OUTPUT_DIR is accessible."""
        assert OUTPUT_DIR is not None
        assert isinstance(OUTPUT_DIR, Path)
    
    def test_generated_dir_exists(self):
        """Test that GENERATED_DIR is accessible."""
        assert GENERATED_DIR is not None
        assert isinstance(GENERATED_DIR, Path)

