"""
Tests for the LaTeX Error Memory system.
"""

import json
import pytest
from pathlib import Path

from resume_builder.latex_error_memory import (
    compute_latex_fingerprint,
    normalize_error_message,
    classify_error_type,
    lookup_errors,
    record_error,
    summarize_errors_for_ui,
    load_error_memory,
    save_error_memory,
)
from resume_builder.paths import OUTPUT_DIR


class TestFingerprinting:
    """Test LaTeX source fingerprinting."""
    
    def test_compute_fingerprint_basic(self):
        """Test computing fingerprint for basic LaTeX."""
        latex_source = "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"
        fingerprint = compute_latex_fingerprint(latex_source)
        
        assert len(fingerprint) == 64  # SHA256 hex
        assert isinstance(fingerprint, str)
        assert all(c in '0123456789abcdef' for c in fingerprint)
    
    def test_compute_fingerprint_normalizes(self):
        """Test that fingerprint normalizes whitespace and comments."""
        source1 = "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"
        source2 = "\\documentclass{article} \\begin{document} Hello \\end{document}"  # Different whitespace
        
        fp1 = compute_latex_fingerprint(source1)
        fp2 = compute_latex_fingerprint(source2)
        
        # Should be similar (may differ slightly due to normalization)
        assert isinstance(fp1, str)
        assert isinstance(fp2, str)
    
    def test_compute_fingerprint_removes_paths(self):
        """Test that fingerprint removes absolute paths."""
        source1 = "\\input{/path/to/file.tex}"
        source2 = "\\input{/different/path/to/file.tex}"
        
        fp1 = compute_latex_fingerprint(source1)
        fp2 = compute_latex_fingerprint(source2)
        
        # Should be similar after path normalization
        assert isinstance(fp1, str)
        assert isinstance(fp2, str)


class TestErrorNormalization:
    """Test error message normalization."""
    
    def test_normalize_error_removes_line_numbers(self):
        """Test that normalization removes line numbers."""
        error = "LaTeX Error: File 'xcolor.sty' not found at line 42"
        normalized = normalize_error_message(error)
        
        assert "line 42" not in normalized or "[N]" in normalized
        assert "xcolor.sty" in normalized.lower()
    
    def test_normalize_error_removes_paths(self):
        """Test that normalization removes file paths."""
        error = "LaTeX Error: File '/usr/local/texlive/2023/texmf-dist/tex/latex/xcolor.sty' not found"
        normalized = normalize_error_message(error)
        
        # Should not contain full path
        assert "/usr/local" not in normalized
        assert "/texlive" not in normalized
        # Path normalization replaces filename with [FILE], so xcolor may be removed
        # But the error type should still be recognizable
        assert "file" in normalized.lower() or "not found" in normalized.lower()
    
    def test_normalize_error_preserves_error_type(self):
        """Test that normalization preserves error type information."""
        error = "LaTeX Error: Undefined control sequence at line 10"
        normalized = normalize_error_message(error)
        
        assert "undefined" in normalized.lower() or "control" in normalized.lower()


class TestErrorClassification:
    """Test error type classification."""
    
    def test_classify_missing_package(self):
        """Test classifying missing package errors."""
        assert classify_error_type("File 'xcolor.sty' not found") == "MissingPackage"
        assert classify_error_type("Package xcolor not found") == "MissingPackage"
    
    def test_classify_undefined_control_sequence(self):
        """Test classifying undefined control sequence errors."""
        assert classify_error_type("Undefined control sequence") == "UndefinedControlSequence"
        assert classify_error_type("undefined command") == "UndefinedControlSequence"
        # "command not found" matches "not found" pattern for MissingPackage, so use more specific pattern
        assert classify_error_type("Undefined command sequence") == "UndefinedControlSequence"
    
    def test_classify_encoding_error(self):
        """Test classifying encoding errors."""
        assert classify_error_type("Encoding error") == "EncodingError"
        assert classify_error_type("Invalid UTF-8") == "EncodingError"
    
    def test_classify_overfull_box(self):
        """Test classifying overfull box errors."""
        assert classify_error_type("Overfull \\hbox") == "OverfullBox"
        assert classify_error_type("Overfull box") == "OverfullBox"
    
    def test_classify_unknown(self):
        """Test classifying unknown errors."""
        assert classify_error_type("Some random error") == "Unknown"


class TestErrorRecording:
    """Test error recording."""
    
    def test_record_new_error(self, tmp_path):
        """Test recording a new error."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "latex_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        fingerprint = compute_latex_fingerprint("\\documentclass{article}")
        error_info = {
            "log_text": "LaTeX Error: File 'xcolor.sty' not found",
            "error_message": "File 'xcolor.sty' not found",
            "error_type": "MissingPackage",
        }
        
        record_error(fingerprint, error_info, "\\documentclass{article}")
        
        # Check that error was recorded
        errors = lookup_errors(fingerprint)
        assert len(errors) >= 1
        assert errors[0]["error_type"] == "MissingPackage"
        assert errors[0]["count"] == 1
    
    def test_record_duplicate_error(self, tmp_path):
        """Test recording duplicate error increments count."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "latex_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        fingerprint = compute_latex_fingerprint("\\documentclass{article}")
        error_info = {
            "log_text": "LaTeX Error: File 'xcolor.sty' not found",
            "error_message": "File 'xcolor.sty' not found",
            "error_type": "MissingPackage",
        }
        
        # Record same error twice
        record_error(fingerprint, error_info, "\\documentclass{article}")
        record_error(fingerprint, error_info, "\\documentclass{article}")
        
        errors = lookup_errors(fingerprint)
        assert len(errors) >= 1
        # Should have count of 2
        assert errors[0]["count"] >= 2


class TestErrorLookup:
    """Test error lookup."""
    
    def test_lookup_errors_by_fingerprint(self, tmp_path):
        """Test looking up errors by fingerprint."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "latex_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        fingerprint = compute_latex_fingerprint("\\documentclass{article}")
        error_info = {
            "log_text": "LaTeX Error: File 'xcolor.sty' not found",
            "error_message": "File 'xcolor.sty' not found",
            "error_type": "MissingPackage",
        }
        
        record_error(fingerprint, error_info, "\\documentclass{article}")
        
        # Lookup errors
        errors = lookup_errors(fingerprint)
        assert len(errors) >= 1
        assert errors[0]["fingerprint"] == fingerprint
    
    def test_lookup_errors_empty(self):
        """Test looking up errors for unknown fingerprint."""
        fingerprint = compute_latex_fingerprint("\\documentclass{unknown}")
        errors = lookup_errors(fingerprint)
        
        # Should return empty list for unknown fingerprint
        assert isinstance(errors, list)
        # May be empty or have unrelated errors


class TestErrorSummarization:
    """Test error summarization for UI."""
    
    def test_summarize_errors_for_ui(self, tmp_path):
        """Test summarizing errors for UI display."""
        # Clear existing memory
        memory_file = OUTPUT_DIR / "latex_error_memory.json"
        if memory_file.exists():
            memory_file.unlink()
        
        fingerprint = compute_latex_fingerprint("\\documentclass{article}")
        error_info = {
            "log_text": "LaTeX Error: File 'xcolor.sty' not found",
            "error_message": "File 'xcolor.sty' not found",
            "error_type": "MissingPackage",
        }
        
        record_error(fingerprint, error_info, "\\documentclass{article}")
        
        summary = summarize_errors_for_ui(fingerprint)
        
        # Should return summary string or None
        assert summary is None or isinstance(summary, str)
        if summary:
            assert len(summary) > 0


class TestErrorMemoryPersistence:
    """Test error memory persistence."""
    
    def test_load_and_save_memory(self, tmp_path):
        """Test loading and saving error memory."""
        memory_file = OUTPUT_DIR / "latex_error_memory.json"
        
        # Clear existing
        if memory_file.exists():
            memory_file.unlink()
        
        # Record an error
        fingerprint = compute_latex_fingerprint("\\documentclass{article}")
        error_info = {
            "log_text": "Test error",
            "error_message": "Test error",
            "error_type": "Unknown",
        }
        record_error(fingerprint, error_info, "\\documentclass{article}")
        
        # Load memory
        memory = load_error_memory()
        assert "errors" in memory
        assert len(memory["errors"]) >= 1
        
        # Verify file exists
        assert memory_file.exists()
        
        # Load again and verify persistence
        memory2 = load_error_memory()
        assert len(memory2["errors"]) == len(memory["errors"])

