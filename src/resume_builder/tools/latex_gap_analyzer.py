"""
LaTeX Gap Analyzer Tool

Analyzes LaTeX source to detect:
- Excessive whitespace/gaps
- Useless sections (empty or minimal content)
- Sections that can be condensed or removed
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR

logger = get_logger("latex_gap_analyzer")


class LaTeXGapAnalyzerInput(BaseModel):
    """Input schema for LaTeXGapAnalyzerTool."""
    tex_path: str = Field(..., description="Path to the LaTeX file to analyze.")
    target_pages: float = Field(2.0, description="Target page count.")
    
    model_config = ConfigDict(extra="ignore")


class LaTeXGapAnalyzerTool(BaseTool):
    """
    Analyzes LaTeX source to detect gaps, excessive whitespace, and sections
    that can be removed or condensed to reduce page count.
    """
    name: str = "latex_gap_analyzer"
    description: str = (
        "Analyzes LaTeX source to detect excessive whitespace, gaps, and useless sections "
        "that can be removed or condensed. Returns a JSON with gap analysis and removal suggestions."
    )
    args_schema: Type[BaseModel] = LaTeXGapAnalyzerInput

    def _run(self, tex_path: str, target_pages: float = 2.0) -> str:
        """
        Analyze LaTeX for gaps and removable sections.
        
        Returns JSON with:
        - gap_analysis: List of detected gaps/excessive whitespace
        - removable_sections: List of sections that can be removed
        - condensation_suggestions: List of sections that can be condensed
        """
        try:
            # Resolve path
            tex_file = OUTPUT_DIR / tex_path if not Path(tex_path).is_absolute() else Path(tex_path)
            if not tex_file.exists():
                return json.dumps({
                    "status": "error",
                    "message": f"LaTeX file not found: {tex_path}",
                    "gap_analysis": [],
                    "removable_sections": [],
                    "condensation_suggestions": []
                })
            
            # Read LaTeX content
            latex_content = tex_file.read_text(encoding='utf-8')
            
            gap_analysis = []
            removable_sections = []
            condensation_suggestions = []
            
            lines = latex_content.split('\n')
            
            # Detect excessive whitespace (3+ consecutive empty lines)
            consecutive_blanks = 0
            last_non_blank = -1
            for i, line in enumerate(lines):
                if not line.strip():
                    consecutive_blanks += 1
                else:
                    if consecutive_blanks >= 3:
                        gap_analysis.append({
                            "type": "excessive_whitespace",
                            "line_range": f"{last_non_blank + 1}-{i}",
                            "blank_lines": consecutive_blanks,
                            "suggestion": f"Remove {consecutive_blanks - 1} blank lines (keep only 1-2)",
                            "estimated_savings_lines": consecutive_blanks - 2
                        })
                    consecutive_blanks = 0
                    last_non_blank = i
            
            # Detect empty or minimal sections
            section_pattern = r'\\section\{([^}]+)\}'
            for match in re.finditer(section_pattern, latex_content):
                section_name = match.group(1)
                section_start = match.start()
                
                # Find section end (next \section or end of document)
                next_section = latex_content.find(r'\section{', section_start + 1)
                doc_end = latex_content.find(r'\end{document}', section_start)
                
                if next_section > 0:
                    section_end = next_section
                elif doc_end > 0:
                    section_end = doc_end
                else:
                    section_end = len(latex_content)
                
                section_content = latex_content[section_start:section_end]
                
                # Count non-comment, non-whitespace lines
                section_lines = [l for l in section_content.split('\n') 
                               if l.strip() and not l.strip().startswith('%')]
                content_lines = len([l for l in section_lines if not l.strip().startswith('\\')])
                
                # If section has very little content, suggest removal
                if content_lines <= 2:
                    removable_sections.append({
                        "section": section_name,
                        "type": "minimal_content",
                        "content_lines": content_lines,
                        "suggestion": f"Remove '{section_name}' section (only {content_lines} lines of content)",
                        "estimated_savings_lines": len(section_lines) + 3  # +3 for section header/spacing
                    })
                elif content_lines <= 5:
                    condensation_suggestions.append({
                        "section": section_name,
                        "type": "condensable",
                        "content_lines": content_lines,
                        "suggestion": f"Condense '{section_name}' section ({content_lines} lines)",
                        "estimated_savings_lines": max(1, content_lines // 2)
                    })
            
            # Detect long itemize/enumerate lists with few items (can be condensed)
            list_pattern = r'\\begin\{(itemize|enumerate)\}'
            for match in re.finditer(list_pattern, latex_content):
                list_type = match.group(1)
                list_start = match.start()
                list_end = latex_content.find(f'\\end{{{list_type}}}', list_start)
                
                if list_end > 0:
                    list_content = latex_content[list_start:list_end + len(f'\\end{{{list_type}}}')]
                    items = len(re.findall(r'\\item', list_content))
                    
                    # If list has many items but could be condensed
                    if items > 5:
                        condensation_suggestions.append({
                            "section": f"{list_type} list",
                            "type": "long_list",
                            "items": items,
                            "suggestion": f"Condense {list_type} list with {items} items",
                            "estimated_savings_lines": max(2, items // 3)
                        })
            
            # Sort by estimated savings (highest first)
            gap_analysis.sort(key=lambda x: x.get("estimated_savings_lines", 0), reverse=True)
            removable_sections.sort(key=lambda x: x.get("estimated_savings_lines", 0), reverse=True)
            condensation_suggestions.sort(key=lambda x: x.get("estimated_savings_lines", 0), reverse=True)
            
            return json.dumps({
                "status": "success",
                "message": f"Analyzed LaTeX: found {len(gap_analysis)} gaps, {len(removable_sections)} removable sections, {len(condensation_suggestions)} condensable sections",
                "gap_analysis": gap_analysis,
                "removable_sections": removable_sections,
                "condensation_suggestions": condensation_suggestions,
                "total_estimated_savings": sum(x.get("estimated_savings_lines", 0) for x in gap_analysis + removable_sections + condensation_suggestions)
            }, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error in LaTeXGapAnalyzerTool: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to analyze LaTeX gaps: {str(e)}",
                "gap_analysis": [],
                "removable_sections": [],
                "condensation_suggestions": []
            })

