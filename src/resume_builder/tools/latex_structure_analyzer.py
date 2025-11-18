"""Tool for analyzing LaTeX structure, sections, and key commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Type, Dict, Any, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from ..paths import resolve_under_root

try:
    from resume_builder.logger import get_logger
    logger = get_logger("latex_structure_analyzer")
except ImportError:
    import logging
    logger = logging.getLogger("latex_structure_analyzer")


class LaTeXStructureAnalyzerInput(BaseModel):
    """Input schema for LaTeXStructureAnalyzerTool."""
    tex_path: str = Field(..., description="Path to the LaTeX file to analyze (absolute or relative to project root).")
    model_config = ConfigDict(extra="ignore")


class LaTeXStructureAnalyzerTool(BaseTool):
    """Analyze LaTeX structure, sections, and key commands.
    
    Current: Detects sections, extracts commands, finds template markers.
    
    Future: Could be extended to include length/section density estimates
    for use by higher-level logic (e.g. latex_builder or ATS tools) to
    suggest which blocks to compress or drop for 1-2 page layouts.
    """
    
    name: str = "latex_structure_analyzer"
    description: str = (
        "Analyze LaTeX file structure including sections, commands, and template markers. "
        "Use this to understand the current LaTeX structure before making fixes. "
        "Returns section line ranges, command list, and template markers."
    )
    args_schema: Type[BaseModel] = LaTeXStructureAnalyzerInput
    
    def _run(self, tex_path: str) -> str:
        """Analyze LaTeX structure and return JSON report.
        
        Standard paths:
        - Template: src/resume_builder/templates/main.tex
        - Generated LaTeX: output/generated/rendered_resume.tex
        """
        try:
            # Resolve path
            try:
                tex_file = resolve_under_root(tex_path)
            except ValueError as e:
                return json.dumps({
                    "error": str(e),
                    "status": "error",
                    "hint": "Use a file path, not a directory. Standard paths: src/resume_builder/templates/main.tex or output/generated/rendered_resume.tex"
                }, indent=2)
            
            if not tex_file.exists():
                return json.dumps({
                    "error": f"LaTeX file not found: {tex_path}",
                    "status": "error",
                    "hint": "Standard paths: src/resume_builder/templates/main.tex (template) or output/generated/rendered_resume.tex (generated)"
                }, indent=2)
            
            # Validate it's a file
            if tex_file.is_dir():
                return json.dumps({
                    "error": f"Path is a directory, not a file: {tex_path}",
                    "status": "error",
                    "hint": "Use a file path. Standard paths: src/resume_builder/templates/main.tex or output/generated/rendered_resume.tex"
                }, indent=2)
            
            # Read LaTeX content
            tex = tex_file.read_text(encoding="utf-8")
            lines = tex.splitlines()
            
            # Detect sections
            sections = self._detect_sections(tex, lines)
            
            # Extract all commands
            commands = sorted(set(re.findall(r"\\[A-Za-z@]+", tex)))
            
            # Find template markers
            markers = re.findall(r"% === AUTO:(\w+) ===", tex)
            
            # Find custom command definitions
            custom_commands = self._find_custom_commands(tex)
            
            # Find document class
            docclass_match = re.search(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}", tex)
            document_class = docclass_match.group(1) if docclass_match else None
            
            result = {
                "status": "success",
                "tex_path": str(tex_file),
                "document_class": document_class,
                "sections": sections,
                "commands": commands,
                "template_markers": markers,
                "custom_commands": custom_commands,
                "total_lines": len(lines),
            }
            
            return json.dumps(result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            error_msg = f"LaTeX structure analysis failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({
                "error": error_msg,
                "status": "error"
            }, indent=2)
    
    @staticmethod
    def _detect_sections(tex: str, lines: List[str]) -> Dict[str, Any]:
        r"""Detect sections in LaTeX by looking for \section commands."""
        
        sections = {}
        current = "preamble"
        sections[current] = []
        
        for i, line in enumerate(lines, start=1):
            # Check for \section*{...} or \section{...}
            m = re.search(r"\\section\*?\{([^}]*)\}", line)
            if m:
                # Save previous section
                if sections[current]:
                    sections[current] = {
                        "line_range": [sections[current][0]["line"], sections[current][-1]["line"]],
                        "line_count": len(sections[current]),
                    }
                # Start new section
                current = m.group(1).strip()
                sections[current] = []
            
            sections[current].append({"line": i, "text": line})
        
        # Convert last section
        if sections[current]:
            sections[current] = {
                "line_range": [sections[current][0]["line"], sections[current][-1]["line"]],
                "line_count": len(sections[current]),
            }
        
        return sections
    
    @staticmethod
    def _find_custom_commands(tex: str) -> Dict[str, Dict[str, Any]]:
        """Find custom command definitions (\newcommand, \renewcommand)."""
        import re
        
        custom_commands = {}
        
        # Pattern for \newcommand{\cmd}[num]{definition} or \newcommand*{\cmd}[num]{definition}
        pattern = r"\\(?:re)?newcommand\*?\{?\\([A-Za-z@]+)\}?(?:\[(\d+)\])?\{([^}]+)\}"
        
        for match in re.finditer(pattern, tex):
            cmd_name = match.group(1)
            num_args = int(match.group(2)) if match.group(2) else 0
            definition = match.group(3)
            
            # Find line number (approximate)
            line_num = tex[:match.start()].count('\n') + 1
            
            custom_commands[cmd_name] = {
                "definition": definition,
                "num_args": num_args,
                "line": line_num,
            }
        
        return custom_commands

