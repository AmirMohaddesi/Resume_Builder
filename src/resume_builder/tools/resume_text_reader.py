"""
Tool for reading resume text from PDF or DOCX files.
Used by the resume parsing agent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
from resume_builder.tools.resume_parser import parse_pdf, parse_docx


class ResumeTextReaderInput(BaseModel):
    """Input schema for the ResumeTextReaderTool."""
    resume_path: str = Field(..., description="Path to the resume file (PDF or DOCX) to read.")
    model_config = ConfigDict(extra="ignore")


class ResumeTextReaderTool(BaseTool):
    """
    Read and extract text content from a resume file (PDF, DOCX, DOC, or TXT).
    This allows the parsing agent to access the raw resume text for analysis.
    """
    
    name: str = "resume_text_reader"
    description: str = (
        "Read and extract text content from a resume file (PDF, DOCX, DOC, or TXT). "
        "Returns the full text content of the resume for analysis. "
        "Use this tool to get the resume text before extracting structured information."
    )
    args_schema: Type[BaseModel] = ResumeTextReaderInput
    
    def _run(self, resume_path: str) -> str:  # type: ignore[override]
        """Read the resume file and return its text content."""
        resume_path = Path(resume_path)
        
        if not resume_path.exists():
            return f"Error: Resume file not found: {resume_path}"
        
        try:
            file_ext = resume_path.suffix.lower()
            
            if file_ext == '.pdf':
                text, _ = parse_pdf(resume_path)  # Ignore hyperlinks for now, agent will extract URLs
            elif file_ext in ['.docx', '.doc']:
                text = parse_docx(resume_path)
            elif file_ext == '.txt':
                # Read plain text file
                text = resume_path.read_text(encoding='utf-8')
            else:
                return f"Error: Unsupported file type: {file_ext}. Supported: PDF, DOCX, DOC, TXT."
            
            return text
        except Exception as e:
            return f"Error reading resume file: {str(e)}"

