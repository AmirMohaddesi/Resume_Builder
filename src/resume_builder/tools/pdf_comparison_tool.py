"""Tool for comparing two PDFs and generating structured diff reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type, Optional, Dict, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from ..paths import resolve_under_root

try:
    from resume_builder.logger import get_logger
    logger = get_logger("pdf_comparison_tool")
except ImportError:
    import logging
    logger = logging.getLogger("pdf_comparison_tool")


class PdfComparisonInput(BaseModel):
    """Input schema for PdfComparisonTool."""
    reference_pdf: str = Field(..., description="Path to the reference PDF file (the target visual appearance).")
    generated_pdf: str = Field(..., description="Path to the generated PDF file (current output to compare).")
    model_config = ConfigDict(extra="ignore")


class PdfComparisonTool(BaseTool):
    """Compare two PDFs and return a structured, section-level diff.
    
    MVP version: Extracts raw text and basic metrics.
    Future: Section detection, visual diff, layout comparison.
    """
    
    name: str = "pdf_comparison_tool"
    description: str = (
        "Compare two PDFs (reference vs generated) and return a structured diff report. "
        "Extracts text content, identifies sections, and highlights differences. "
        "Use this to understand what needs to be fixed in the LaTeX template to match the reference."
    )
    args_schema: Type[BaseModel] = PdfComparisonInput
    
    def _run(self, reference_pdf: str, generated_pdf: str) -> str:
        """Compare two PDFs and return structured diff as JSON string."""
        try:
            import fitz  # PyMuPDF
            
            # Resolve paths
            ref_path = resolve_under_root(reference_pdf)
            gen_path = resolve_under_root(generated_pdf)
            
            if not ref_path.exists():
                return json.dumps({
                    "error": f"Reference PDF not found: {reference_pdf}",
                    "status": "error"
                }, indent=2)
            
            if not gen_path.exists():
                return json.dumps({
                    "error": f"Generated PDF not found: {generated_pdf}",
                    "status": "error"
                }, indent=2)
            
            # Open PDFs
            ref_doc = fitz.open(str(ref_path))
            gen_doc = fitz.open(str(gen_path))
            
            try:
                # Naive text extraction (page-wise)
                ref_text = "\n".join(page.get_text("text") for page in ref_doc)
                gen_text = "\n".join(page.get_text("text") for page in gen_doc)
                
                # Basic metrics
                ref_chars = len(ref_text)
                gen_chars = len(gen_text)
                ref_lines = len(ref_text.splitlines())
                gen_lines = len(gen_text.splitlines())
                
                # Simple section detection (heuristic: split by common section headings)
                ref_sections = self._detect_sections(ref_text)
                gen_sections = self._detect_sections(gen_text)
                
                # Build result
                result = {
                    "status": "success",
                    "reference_pdf": str(ref_path),
                    "generated_pdf": str(gen_path),
                    "lengths": {
                        "reference_chars": ref_chars,
                        "generated_chars": gen_chars,
                        "reference_lines": ref_lines,
                        "generated_lines": gen_lines,
                    },
                    "sections": {
                        "reference": ref_sections,
                        "generated": gen_sections,
                    },
                    "note": "MVP version – basic text extraction and section detection. Visual/layout diff coming soon.",
                }
                
                return json.dumps(result, indent=2, ensure_ascii=False)
                
            finally:
                ref_doc.close()
                gen_doc.close()
                
        except ImportError:
            error_msg = "PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "status": "error",
                "hint": "Install PyMuPDF: pip install PyMuPDF"
            }, indent=2)
        except Exception as e:
            error_msg = f"PDF comparison failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({
                "error": error_msg,
                "status": "error"
            }, indent=2)
    
    @staticmethod
    def _detect_sections(text: str) -> Dict[str, Any]:
        """Detect sections in text using simple heuristics.
        
        Looks for common section headings like:
        - Summary
        - Research Experience / Experience
        - Projects
        - Skills
        - Education
        - Achievements
        """
        import re  # Import here to avoid top-level dependency
        
        sections = {}
        lines = text.splitlines()
        
        # Common section patterns
        section_patterns = [
            r"^Summary\s*$",
            r"^Research Experience\s*$",
            r"^Experience\s*$",
            r"^Projects?\s*$",
            r"^Skills?\s*$",
            r"^Education\s*$",
            r"^Achievements?\s*$",
            r"^Additional Info\s*$",
        ]
        
        current_section = "header"  # Everything before first section
        current_content = []
        
        for i, line in enumerate(lines):
            # Check if this line is a section heading
            is_section = False
            section_name = None
            
            for pattern in section_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    # Save previous section
                    if current_section:
                        sections[current_section] = {
                            "text": "\n".join(current_content).strip(),
                            "line_count": len(current_content),
                        }
                    # Start new section
                    current_section = line.strip()
                    current_content = []
                    is_section = True
                    break
            
            if not is_section:
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = {
                "text": "\n".join(current_content).strip(),
                "line_count": len(current_content),
            }
        
        return sections

