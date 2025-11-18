"""
JSON Schema Validators for Resume Sections

RESPONSIBILITY: LLM edit output gatekeeper
- Validates JSON sections AFTER LLM edits
- Enforces strict schema compliance
- Ensures data integrity (required fields, correct types)
- Pure validation only - NEVER mutates data
- Returns (is_valid, error_message) tuples

This module is used by:
- LLM JSON editor (to validate LLM output before saving)
- Edit engine (to ensure edits don't break schema)

NOT used for:
- Runtime JSON loading (see json_loaders.py for that)
- Backward compatibility (json_loaders.py handles that)

All validators are pure functions - they never modify the input data.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from resume_builder.logger import get_logger

logger = get_logger()


def validate_summary_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate summary section JSON.
    
    Required fields: summary (string)
    Optional fields: status, message, approx_word_count
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Summary must be a dictionary"
    
    if "summary" not in data:
        return False, "Summary section missing required 'summary' field"
    
    if not isinstance(data["summary"], str):
        return False, "Summary 'summary' field must be a string"
    
    if not data["summary"].strip():
        return False, "Summary 'summary' field cannot be empty"
    
    # Optional fields validation
    if "status" in data and data["status"] not in ["success", "error"]:
        return False, "Summary 'status' must be 'success' or 'error'"
    
    if "approx_word_count" in data:
        if not isinstance(data["approx_word_count"], int) or data["approx_word_count"] < 0:
            return False, "Summary 'approx_word_count' must be a non-negative integer"
    
    return True, None


def validate_experiences_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate experiences section JSON.
    
    Required: selected_experiences (list)
    Each experience must have: title, organization (or company), bullets (list)
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Experiences must be a dictionary"
    
    if "selected_experiences" not in data:
        return False, "Experiences section missing required 'selected_experiences' field"
    
    experiences = data["selected_experiences"]
    if not isinstance(experiences, list):
        return False, "Experiences 'selected_experiences' must be a list"
    
    for i, exp in enumerate(experiences):
        if not isinstance(exp, dict):
            return False, f"Experience {i} must be a dictionary"
        
        # Check for title or organization/company
        has_title = "title" in exp and isinstance(exp["title"], str) and exp["title"].strip()
        has_org = ("organization" in exp and exp["organization"]) or ("company" in exp and exp["company"])
        
        if not has_title:
            return False, f"Experience {i} missing required 'title' field"
        
        if not has_org:
            return False, f"Experience {i} missing required 'organization' or 'company' field"
        
        # Bullets should be a list
        if "bullets" in exp:
            if not isinstance(exp["bullets"], list):
                return False, f"Experience {i} 'bullets' must be a list"
            for j, bullet in enumerate(exp["bullets"]):
                if not isinstance(bullet, str):
                    return False, f"Experience {i}, bullet {j} must be a string"
    
    return True, None


def validate_skills_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate skills section JSON.
    
    Can be either:
    - Old format: {"selected_skills": ["skill1", "skill2", ...]}
    - New format: {"skills": ["skill1", ...], "groups": {...}}
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Skills must be a dictionary"
    
    # Check for old format
    if "selected_skills" in data:
        skills = data["selected_skills"]
        if not isinstance(skills, list):
            return False, "Skills 'selected_skills' must be a list"
        for i, skill in enumerate(skills):
            if not isinstance(skill, str):
                return False, f"Skill {i} must be a string"
    
    # Check for new format
    elif "skills" in data:
        skills = data["skills"]
        if not isinstance(skills, list):
            return False, "Skills 'skills' must be a list"
        for i, skill in enumerate(skills):
            if not isinstance(skill, str):
                return False, f"Skill {i} must be a string"
        
        if "groups" in data:
            if not isinstance(data["groups"], dict):
                return False, "Skills 'groups' must be a dictionary"
    else:
        return False, "Skills section missing 'selected_skills' or 'skills' field"
    
    return True, None


def validate_projects_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate projects section JSON.
    
    Required: selected_projects (list)
    Each project should have: name, bullets (list)
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Projects must be a dictionary"
    
    if "selected_projects" not in data:
        return False, "Projects section missing required 'selected_projects' field"
    
    projects = data["selected_projects"]
    if not isinstance(projects, list):
        return False, "Projects 'selected_projects' must be a list"
    
    for i, proj in enumerate(projects):
        if not isinstance(proj, dict):
            return False, f"Project {i} must be a dictionary"
        
        # Name is typically required
        if "name" in proj and not isinstance(proj["name"], str):
            return False, f"Project {i} 'name' must be a string"
        
        # Bullets should be a list if present
        if "bullets" in proj:
            if not isinstance(proj["bullets"], list):
                return False, f"Project {i} 'bullets' must be a list"
            for j, bullet in enumerate(proj["bullets"]):
                if not isinstance(bullet, str):
                    return False, f"Project {i}, bullet {j} must be a string"
    
    return True, None


def validate_education_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate education section JSON.
    
    Required: education (list)
    Each education entry should have: school, degree, dates
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Education must be a dictionary"
    
    if "education" not in data:
        return False, "Education section missing required 'education' field"
    
    education = data["education"]
    if not isinstance(education, list):
        return False, "Education 'education' must be a list"
    
    for i, edu in enumerate(education):
        if not isinstance(edu, dict):
            return False, f"Education entry {i} must be a dictionary"
        
        # Check required fields
        if "school" not in edu or not isinstance(edu["school"], str) or not edu["school"].strip():
            return False, f"Education entry {i} missing required 'school' field"
        
        if "degree" not in edu or not isinstance(edu["degree"], str) or not edu["degree"].strip():
            return False, f"Education entry {i} missing required 'degree' field"
        
        if "dates" not in edu or not isinstance(edu["dates"], str) or not edu["dates"].strip():
            return False, f"Education entry {i} missing required 'dates' field"
    
    return True, None


def validate_header_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate header section JSON.
    
    Can have: title_line, contact_info
    contact_info should have: email, phone, location, etc.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Header must be a dictionary"
    
    # Validate email if present
    if "contact_info" in data:
        contact_info = data["contact_info"]
        if not isinstance(contact_info, dict):
            return False, "Header 'contact_info' must be a dictionary"
        
        if "email" in contact_info:
            email = contact_info["email"]
            if not isinstance(email, str):
                return False, "Header 'contact_info.email' must be a string"
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email.strip()):
                return False, f"Header 'contact_info.email' has invalid format: {email}"
    
    # Validate title_line if present
    if "title_line" in data:
        if not isinstance(data["title_line"], str):
            return False, "Header 'title_line' must be a string"
    
    return True, None


def validate_cover_letter_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate cover letter section JSON.
    
    Required: cover_letter_md (string)
    Optional: status, message
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Cover letter must be a dictionary"
    
    if "cover_letter_md" not in data:
        return False, "Cover letter section missing required 'cover_letter_md' field"
    
    if not isinstance(data["cover_letter_md"], str):
        return False, "Cover letter 'cover_letter_md' must be a string"
    
    if not data["cover_letter_md"].strip():
        return False, "Cover letter 'cover_letter_md' cannot be empty"
    
    return True, None


# Section validator mapping
SECTION_VALIDATORS = {
    "summary": validate_summary_json,
    "experiences": validate_experiences_json,
    "skills": validate_skills_json,
    "projects": validate_projects_json,
    "education": validate_education_json,
    "header": validate_header_json,
    "cover_letter": validate_cover_letter_json,
}


def validate_section_json(section: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate JSON data for a specific section.
    
    Pure validation function - NEVER mutates the input data.
    
    Args:
        section: Section name (e.g., "summary", "experiences")
        data: JSON data to validate (will not be modified)
        
    Returns:
        (is_valid, error_message)
    """
    validator = SECTION_VALIDATORS.get(section)
    if not validator:
        logger.warning(f"No validator for section '{section}', skipping validation (treating as valid)")
        return True, None  # If no validator, treat as valid (backward compatibility)
    
    try:
        # Validators are pure functions - they never mutate data
        is_valid, error_msg = validator(data)
        if not is_valid:
            logger.error(f"Validation failed for section '{section}': {error_msg}")
        return is_valid, error_msg
    except Exception as e:
        logger.error(f"Validator exception for section '{section}': {e}")
        return False, f"Validation error: {str(e)}"

