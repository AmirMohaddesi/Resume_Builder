"""
LaTeX generation modules for resume builder.

This package contains:
- core: Core LaTeX utilities (escaping, formatting)
- resume_template: Resume section generation functions
"""

from .core import escape_latex, format_phone, format_url
from .resume_template import (
    build_preamble,
    build_header,
    build_summary,
    build_experience_section,
    build_education_section,
    build_skills_section,
    build_projects_section,
)

__all__ = [
    'escape_latex',
    'format_phone',
    'format_url',
    'build_preamble',
    'build_header',
    'build_summary',
    'build_experience_section',
    'build_education_section',
    'build_skills_section',
    'build_projects_section',
]
