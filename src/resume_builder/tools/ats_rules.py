"""Deterministic ATS (Applicant Tracking System) rules checker."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, Type, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict


class ATSInput(BaseModel):
    """Input schema for ATSRulesTool."""
    model_config = ConfigDict(extra="forbid")
    tex_path: str = Field(..., description="Path to LaTeX file to check")
    max_links: int = Field(default=12, description="Maximum number of hyperlinks allowed (default: 12)")


class ATSRulesTool(BaseTool):
    """Run simple deterministic checks for ATS friendliness."""
    
    name: str = "ats_rules_audit"
    description: str = "Run deterministic ATS checks on LaTeX file. Returns JSON with score and findings."
    args_schema: Type[BaseModel] = ATSInput
    
    def _run(self, tex_path: str, max_links: int = 12) -> str:
        """Run ATS rules audit.
        
        Args:
            tex_path: Path to LaTeX file
            max_links: Maximum number of hyperlinks allowed (default: 12)
            
        Returns:
            JSON string with score and findings
        """
        tex_file = Path(tex_path)
        if not tex_file.exists():
            return json.dumps({
                "score": 0.0,
                "error": f"File not found: {tex_path}",
                "findings": []
            }, indent=2, ensure_ascii=False)
        
        txt = tex_file.read_text(encoding="utf-8")
        findings: List[Dict[str, Any]] = []
        
        def add(id: str, ok: bool, msg: str):
            findings.append({"id": id, "ok": ok, "msg": msg})
        
        # Check 1: Email present
        add("contact_email", bool(re.search(r"@[\w\.-]+", txt)), "Email address present")
        
        # Check 2: Phone number present
        add("phone_digits", bool(re.search(r"\+?\d[\d\-\s]{7,}", txt)), "Phone number present")
        
        # Check 3: No embedded images (ATS may not parse images)
        add("no_images", not bool(re.search(r"\\includegraphics", txt)), "No embedded images")
        
        # Check 4: No wide tables (can break parsing) - but allow narrow tabular (two columns)
        # Check for wide tables (table environment) but allow narrow tabular
        has_wide_tables = bool(re.search(r"\\begin\{table\}", txt))
        # Allow narrow tabular (two short columns are OK)
        add("no_wide_tables", not has_wide_tables, "No wide tables (narrow tabular OK)")
        
        # Check 5: Limited hyperlinks (some ATS strip links) - cap configurable
        href_count = len(re.findall(r"\\href\{", txt))
        mailto_count = len(re.findall(r"mailto:", txt, re.I))
        total_links = href_count + mailto_count
        add("limited_hyperlinks", total_links <= max_links, f"Limited hyperlinks ({total_links} links, cap: ≤{max_links})")
        
        # Check 6: Standard sections present
        has_summary = bool(re.search(r"\\section\{.*[Ss]ummary", txt))
        has_experience = bool(re.search(r"\\section\{.*[Ee]xperience", txt))
        has_education = bool(re.search(r"\\section\{.*[Ee]ducation", txt))
        add("standard_sections", has_summary and has_experience and has_education, "Standard sections (Summary, Experience, Education) present")
        
        # Check 7: Unicode-safe (allow basic Unicode: bullets •, en-dash –, em-dash —)
        # Only flag problematic Unicode that might break parsing, not common typography
        problematic_unicode = bool(re.search(r"[^\x00-\x7F\u2022\u2013\u2014]", txt))  # Allow • – —
        add("unicode_safe", not problematic_unicode, "Unicode-safe (basic typography • – — allowed)")
        
        # Check 8: Reasonable length (not too short, not too long)
        word_count = len(re.findall(r'\b\w+\b', txt))
        reasonable_length = 200 <= word_count <= 5000
        add("reasonable_length", reasonable_length, f"Reasonable length ({word_count} words)")
        
        # Calculate score
        score = sum(1 for f in findings if f["ok"]) / max(1, len(findings))
        
        report = {
            "score": round(score, 3),
            "findings": findings,
            "summary": f"{sum(1 for f in findings if f['ok'])}/{len(findings)} checks passed"
        }
        
        return json.dumps(report, indent=2, ensure_ascii=False)

