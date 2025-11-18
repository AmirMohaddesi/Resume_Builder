"""Tools for reading and writing LaTeX files.

This module provides minimal tools for agents to read and write LaTeX files.
Used primarily for adjustments requested via the UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from ..paths import resolve_under_root

try:
    from resume_builder.logger import get_logger
    logger = get_logger("latex_file_editor")
except ImportError:
    import logging
    logger = logging.getLogger("latex_file_editor")


class ReadLatexFileInput(BaseModel):
    """Input schema for ReadLatexFileTool."""
    tex_path: str = Field(..., description="Path to the LaTeX file to read (absolute or relative to project root).")
    model_config = ConfigDict(extra="ignore")


class ReadLatexFileTool(BaseTool):
    """Read a LaTeX file and return its contents for analysis."""
    
    name: str = "read_latex_file"
    description: str = (
        "Read a LaTeX file and return its full contents. Use this to analyze the file structure, "
        "identify issues, and understand what needs to be fixed before making changes."
    )
    args_schema: Type[BaseModel] = ReadLatexFileInput
    
    def _run(self, tex_path: str) -> str:
        """Read and return LaTeX file contents.
        
        Standard paths:
        - Template: src/resume_builder/templates/main.tex
        - Generated LaTeX: output/generated/rendered_resume.tex
        """
        try:
            try:
                tex_file = resolve_under_root(tex_path)
            except ValueError as e:
                return f"[error] {str(e)}. Hint: Use a file path. Standard paths: src/resume_builder/templates/main.tex or output/generated/rendered_resume.tex"
            
            if not tex_file.exists():
                return f"[error] LaTeX file not found: {tex_path}. Standard paths: src/resume_builder/templates/main.tex (template) or output/generated/rendered_resume.tex (generated)"
            
            # Validate it's a file
            if tex_file.is_dir():
                return f"[error] Path is a directory, not a file: {tex_path}. Standard paths: src/resume_builder/templates/main.tex or output/generated/rendered_resume.tex"
            
            content = tex_file.read_text(encoding='utf-8')
            logger.info(f"Read LaTeX file: {tex_file} ({len(content)} characters)")
            
            return f"✅ Read LaTeX file successfully.\n\nFile: {tex_file}\nLength: {len(content)} characters\n\nContent:\n{content}"
        except Exception as e:
            error_msg = f"Failed to read LaTeX file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"[error] {error_msg}"


class WriteLatexFileInput(BaseModel):
    """Input schema for WriteLatexFileTool."""
    tex_path: str = Field(..., description="Path to the LaTeX file to write (absolute or relative to project root).")
    content: str = Field(..., description="The LaTeX content to write to the file.")
    model_config = ConfigDict(extra="ignore")


class WriteLatexFileTool(BaseTool):
    """Write LaTeX content to a file."""
    
    name: str = "write_latex_file"
    description: str = (
        "Write LaTeX content to a file. Use this after making adjustments to save the modified content. "
        "The file will be created or overwritten. Always verify the content is correct before writing."
    )
    args_schema: Type[BaseModel] = WriteLatexFileInput
    
    def _run(self, tex_path: str, content: str) -> str:
        """Write LaTeX content to file with validation and cleaning."""
        try:
            import re
            
            # Clean control characters that can corrupt LaTeX files
            # Remove control characters except newlines, tabs, and carriage returns
            cleaned_content = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', content)
            
            # Check for common corruption patterns
            if cleaned_content != content:
                removed_chars = len(content) - len(cleaned_content)
                logger.warning(f"Removed {removed_chars} control characters from LaTeX content")
            
            # Validate basic LaTeX structure
            if not cleaned_content.strip():
                error_msg = "LaTeX content is empty after cleaning"
                logger.error(error_msg)
                return f"[error] {error_msg}"
            
            # Check for essential LaTeX commands
            if '\\documentclass' not in cleaned_content and '\\begin{document}' not in cleaned_content:
                # This might be a fragment, which is okay for some edits
                logger.debug("LaTeX content appears to be a fragment (no documentclass or begin{document})")
            
            # Check for obvious corruption (backspace characters that create invalid sequences)
            if re.search(r'\x08', content):  # \x08 is backspace (^^H)
                logger.error("LaTeX content contains backspace characters - this will corrupt the file")
                # Remove backspace and the character before it (common corruption pattern)
                cleaned_content = re.sub(r'.\x08', '', cleaned_content)
                logger.warning("Removed backspace corruption patterns from LaTeX content")
            
            try:
                tex_file = resolve_under_root(tex_path)
            except ValueError as e:
                return f"[error] {str(e)}. Hint: Use a file path. Standard paths: src/resume_builder/templates/main.tex or output/generated/rendered_resume.tex"
            
            if not tex_file.parent.exists():
                tex_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if file exists
            if tex_file.exists():
                backup_path = tex_file.with_suffix(tex_file.suffix + '.backup')
                try:
                    import shutil
                    shutil.copy2(tex_file, backup_path)
                    logger.debug(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")
            
            tex_file.write_text(cleaned_content, encoding='utf-8')
            logger.info(f"Wrote LaTeX file: {tex_file} ({len(cleaned_content)} characters)")
            
            return f"✅ LaTeX file written successfully.\n\nFile: {tex_file}\nLength: {len(cleaned_content)} characters"
        except Exception as e:
            error_msg = f"Failed to write LaTeX file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"[error] {error_msg}"
