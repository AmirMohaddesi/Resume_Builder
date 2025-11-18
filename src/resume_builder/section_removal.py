"""
Section Removal System

Handles removal of LaTeX sections from resumes in a clean, extensible way.
Sections are removed at LaTeX generation time, not by manipulating JSON data.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Set, Optional
from enum import Enum

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR

logger = get_logger()


class SectionName(Enum):
    """Standard section names in LaTeX resumes."""
    SUMMARY = "Summary"
    EXPERIENCE = "Experience"
    EDUCATION = "Education"
    SKILLS = "Skills"
    PROJECTS = "Projects"
    ACHIEVEMENTS = "Achievements"
    ADDITIONAL_INFO = "Additional Info"
    HEADER = "Header"


# Mapping from user-friendly names to section names
SECTION_NAME_MAPPING: Dict[str, SectionName] = {
    "summary": SectionName.SUMMARY,
    "professional summary": SectionName.SUMMARY,
    "profile summary": SectionName.SUMMARY,
    "experience": SectionName.EXPERIENCE,
    "work": SectionName.EXPERIENCE,
    "employment": SectionName.EXPERIENCE,
    "work experience": SectionName.EXPERIENCE,
    "education": SectionName.EDUCATION,
    "degree": SectionName.EDUCATION,
    "degrees": SectionName.EDUCATION,
    "skills": SectionName.SKILLS,
    "skill": SectionName.SKILLS,
    "projects": SectionName.PROJECTS,
    "project": SectionName.PROJECTS,
    "achievements": SectionName.ACHIEVEMENTS,
    "achievement": SectionName.ACHIEVEMENTS,
    "additional info": SectionName.ADDITIONAL_INFO,
    "additional information": SectionName.ADDITIONAL_INFO,
    "header": SectionName.HEADER,
    "contact": SectionName.HEADER,
}


def detect_section_name(request: str) -> Optional[SectionName]:
    """Detect which section the user wants to remove from their request.
    
    Args:
        request: User's edit request (e.g., "remove additional info section")
        
    Returns:
        SectionName enum if detected, None otherwise
    """
    request_lower = request.lower()
    
    # Check for "remove" + section name
    if "remove" not in request_lower:
        return None
    
    # Try to match section names
    for key, section in SECTION_NAME_MAPPING.items():
        if key in request_lower:
            return section
    
    return None


def load_removed_sections() -> Set[SectionName]:
    """Load set of sections to remove from metadata file.
    
    Returns:
        Set of SectionName enums that should be removed
    """
    metadata_file = OUTPUT_DIR / "section_removal_metadata.json"
    
    if not metadata_file.exists():
        return set()
    
    try:
        import json
        data = json.loads(metadata_file.read_text(encoding='utf-8'))
        removed_names = data.get("removed_sections", [])
        return {SectionName(name) for name in removed_names if name in [s.value for s in SectionName]}
    except Exception as e:
        logger.warning(f"Failed to load section removal metadata: {e}")
        return set()


def save_removed_sections(removed_sections: Set[SectionName]) -> None:
    """Save set of sections to remove to metadata file.
    
    Args:
        removed_sections: Set of SectionName enums that should be removed
    """
    metadata_file = OUTPUT_DIR / "section_removal_metadata.json"
    
    try:
        import json
        data = {
            "removed_sections": [section.value for section in removed_sections]
        }
        metadata_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        logger.info(f"Saved section removal metadata: {[s.value for s in removed_sections]}")
    except Exception as e:
        logger.error(f"Failed to save section removal metadata: {e}")


def mark_section_for_removal(section: SectionName) -> None:
    """Mark a section for removal.
    
    Args:
        section: SectionName enum to mark for removal
    """
    removed = load_removed_sections()
    removed.add(section)
    save_removed_sections(removed)
    logger.info(f"Marked section '{section.value}' for removal")


def unmark_section_for_removal(section: SectionName) -> None:
    """Unmark a section for removal (restore it).
    
    Args:
        section: SectionName enum to restore
    """
    removed = load_removed_sections()
    removed.discard(section)
    save_removed_sections(removed)
    logger.info(f"Unmarked section '{section.value}' for removal")


def remove_section_from_latex(latex: str, section: SectionName) -> str:
    """Remove a section from LaTeX content.
    
    This handles different section patterns:
    - Standard sections: \\section*{Section Name}
    - Template markers: % === AUTO:SECTION ===
    - Both together
    
    Args:
        latex: LaTeX content
        section: SectionName enum to remove
        
    Returns:
        LaTeX content with section removed
    """
    section_name = section.value
    
    # Pattern 1: Remove section header + marker on separate lines
    # Matches: \section*{Section Name}\n% === AUTO:MARKER ===\n
    marker_map = {
        SectionName.SUMMARY: "SUMMARY",
        SectionName.EXPERIENCE: "EXPERIENCE",
        SectionName.EDUCATION: "EDUCATION",
        SectionName.SKILLS: "SKILLS",
        SectionName.PROJECTS: "ACHIEVEMENTS",  # Projects can be under ACHIEVEMENTS
        SectionName.ACHIEVEMENTS: "ACHIEVEMENTS",
        SectionName.ADDITIONAL_INFO: "ADDITIONAL",
        SectionName.HEADER: "HEADER",
    }
    
    marker = marker_map.get(section, "")
    
    # Escape section name for regex
    escaped_name = re.escape(section_name)
    
    # Pattern 1: Section header on one line, marker on next line (most common)
    # Use double braces to escape in f-string, then format
    pattern1 = r'\\section\*\{' + escaped_name + r'\}\s*\n\s*% === AUTO:' + marker + r' ===\s*\n'
    latex = re.sub(pattern1, '', latex)
    
    # Pattern 2: Section header and marker on same line
    pattern2 = r'\\section\*\{' + escaped_name + r'\}.*?% === AUTO:' + marker + r' ===.*?\n'
    latex = re.sub(pattern2, '', latex)
    
    # Pattern 3: Just the section header (if marker already removed)
    pattern3 = r'\\section\*\{' + escaped_name + r'\}\s*\n'
    # Only remove if there's no content between this and next section
    # This is safer - we'll let the marker removal handle most cases
    # But we can remove standalone headers that are clearly empty
    
    # Pattern 4: Remove marker alone (if section header was already removed)
    if marker:
        pattern4 = r'% === AUTO:' + marker + r' ===\s*\n'
        latex = re.sub(pattern4, '', latex)
    
    # Pattern 5: Remove section with content (more aggressive - for sections that have content)
    # Match from section header to next section or end of document
    # This is more complex and should be done carefully
    # For now, we rely on the builder not generating content for removed sections
    
    return latex


def apply_section_removals(latex: str) -> str:
    """Apply all section removals to LaTeX content.
    
    Args:
        latex: LaTeX content
        
    Returns:
        LaTeX content with all marked sections removed
    """
    removed_sections = load_removed_sections()
    
    if not removed_sections:
        return latex
    
    original_latex = latex
    for section in removed_sections:
        latex = remove_section_from_latex(latex, section)
    
    if latex != original_latex:
        logger.info(f"Applied section removals: {[s.value for s in removed_sections]}")
    
    return latex

