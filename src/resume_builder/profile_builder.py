"""
Profile builder UI components for collecting user profile data.
Supports resume upload, manual form, and profile management.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    from resume_builder.tools.resume_parser import (
        save_profile_json,
    )
    from resume_builder.tools.agent_resume_parser import (
        parse_resume_with_agent,
    )
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False


def build_profile_from_upload(resume_file) -> Tuple[Optional[Dict[str, Any]], str]:
    """Parse uploaded resume file and return profile dict."""
    if not PARSER_AVAILABLE:
        return None, "Resume parser not available. Install: pip install pypdf python-docx"
    
    if resume_file is None:
        return None, "Please upload a resume file (PDF, DOCX, DOC, or TXT)"
    
    try:
        # Handle different file input types from Gradio
        if isinstance(resume_file, str):
            tmp_path = Path(resume_file)
        else:
            # Gradio file object
            file_path = Path(resume_file.name) if hasattr(resume_file, 'name') else Path(str(resume_file))
            tmp_path = file_path
        
        # Parse resume using agent-based parser for better accuracy
        profile = parse_resume_with_agent(tmp_path)
        
        return profile, "Resume parsed successfully! Review and edit the profile below."
    except Exception as e:
        return None, f"Error parsing resume: {str(e)}"


def build_profile_from_form(
    first_name: str,
    last_name: str,
    title: str,
    email: str,
    phone: str,
    website: str,
    linkedin: str,
    github: str,
    experience_json: str,
    education_json: str,
    skills_text: str,
    projects_json: str,
    awards_text: str,
    additional_links: Optional[Dict[str, Dict[str, str]]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Build profile from form inputs."""
    try:
        # Parse JSON fields
        experience = json.loads(experience_json) if experience_json.strip() else []
        education = json.loads(education_json) if education_json.strip() else []
        projects = json.loads(projects_json) if projects_json.strip() else []
        
        # Parse skills (comma-separated or newline-separated)
        skills = []
        if skills_text:
            for line in skills_text.split('\n'):
                skills.extend([s.strip() for s in line.split(',') if s.strip()])
        
        # Parse awards
        awards = [a.strip() for a in awards_text.split('\n') if a.strip()] if awards_text else []
        
        # Build identity with additional links
        identity = {
            "first": first_name.strip(),
            "last": last_name.strip(),
            "title": title.strip(),
            "email": email.strip(),
            "phone": phone.strip(),
            "website": website.strip(),
            "linkedin": linkedin.strip(),
            "github": github.strip(),
            "education": education,
        }
        
        # Add any additional links
        if additional_links:
            for field_id, field_data in additional_links.items():
                field_label = field_data.get("label", "").lower().replace(" ", "_").replace("/", "_")
                if field_label:
                    identity[field_label] = field_data.get("value", "")
        
        profile = {
            "identity": identity,
            "experience": experience,
            "projects": projects,
            "skills": skills,
            "awards": awards,
        }
        
        return profile, "Profile created successfully!"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON format: {str(e)}"
    except Exception as e:
        return None, f"Error creating profile: {str(e)}"


def save_profile(profile: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
    """Save profile to JSON file."""
    if output_path is None:
        # Find project root reliably by looking for markers
        def find_project_root() -> Path:
            """Find project root by looking for markers."""
            # Start from current file's location
            current = Path(__file__).resolve().parent
            # Check up to 5 levels up
            for _ in range(5):
                # Check for project markers
                if (current / "pyproject.toml").exists() or \
                   (current / "src").exists() or \
                   (current / "output").exists():
                    return current
                if current.parent == current:  # Reached filesystem root
                    break
                current = current.parent
            # Fallback: use current working directory
            return Path.cwd()
        
        project_root = find_project_root()
        output_dir = project_root / "output"
        output_dir.mkdir(exist_ok=True, parents=True)
        output_path = output_dir / "user_profile.json"
    return save_profile_json(profile, output_path)


def load_profile_template() -> Dict[str, Any]:
    """Return an empty profile structure for manual entry."""
    return {
        "identity": {
            "first": "",
            "last": "",
            "title": "",
            "email": "",
            "phone": "",
            "website": "",
            "linkedin": "",
            "github": "",
            "education": []
        },
        "experience": [],
        "projects": [],
        "skills": [],
        "awards": []
    }

