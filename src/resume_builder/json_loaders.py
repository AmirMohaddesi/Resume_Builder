"""
Centralized JSON loading functions with runtime consumer safety and backward compatibility.

RESPONSIBILITY: Runtime consumer safety + backward compatibility
- Load JSON files from disk with error handling
- Perform light validation (check required fields exist)
- Apply backward compatibility transforms (e.g., old format → new format)
- Return safe defaults on errors (never crash the pipeline)
- Handle missing files gracefully

This module is used by:
- LaTeX builder (to read JSON for resume generation)
- Orchestration (to check pipeline status)
- UI (to display current resume data)

NOT used for:
- LLM edit output validation (see json_validators.py for that)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from resume_builder.paths import OUTPUT_DIR
from resume_builder.utils import clean_json_content

logger = logging.getLogger(__name__)


def load_parsed_jd(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load parsed_jd.json with schema validation.
    
    Schema: {status: "success"|"error", message: string, title?: string, company?: string, 
             location?: string, skills: array, keywords: array, cleaned_text: string}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "parsed_jd.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"parsed_jd.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"parsed_jd.json missing 'message' field")
        
        return data
    except FileNotFoundError:
        logger.error(f"parsed_jd.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "skills": [], "keywords": [], "cleaned_text": ""}
    except json.JSONDecodeError as e:
        logger.error(f"parsed_jd.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "skills": [], "keywords": [], "cleaned_text": ""}
    except Exception as e:
        logger.error(f"parsed_jd.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "skills": [], "keywords": [], "cleaned_text": ""}


def load_selected_experiences(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load selected_experiences.json with schema validation.
    
    Schema: {status: "success", message: string, selected_experiences: [{id, title: string, 
             company: string, location?: string, dates?: string, priority: number, bullets: [string, ...]}]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "selected_experiences.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"selected_experiences.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"selected_experiences.json missing 'message' field")
        if "selected_experiences" not in data:
            logger.warning(f"selected_experiences.json missing 'selected_experiences' field")
            data["selected_experiences"] = []
        
        return data
    except FileNotFoundError:
        logger.error(f"selected_experiences.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "selected_experiences": []}
    except json.JSONDecodeError as e:
        logger.error(f"selected_experiences.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "selected_experiences": []}
    except Exception as e:
        logger.error(f"selected_experiences.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "selected_experiences": []}


def load_selected_skills(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load selected_skills.json with schema validation.
    
    Schema: {status: "success", message: string, skills: [string, ...], groups?: {name: [skills]}}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "selected_skills.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"selected_skills.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"selected_skills.json missing 'message' field")
        if "skills" not in data:
            logger.warning(f"selected_skills.json missing 'skills' field")
            data["skills"] = []
        # Backward compatibility: if selected_skills exists, use it as skills
        if "selected_skills" in data and "skills" not in data:
            data["skills"] = data.pop("selected_skills")
        
        return data
    except FileNotFoundError:
        logger.error(f"selected_skills.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "skills": []}
    except json.JSONDecodeError as e:
        logger.error(f"selected_skills.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "skills": []}
    except Exception as e:
        logger.error(f"selected_skills.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "skills": []}


def load_selected_projects(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load selected_projects.json with schema validation.
    
    Schema: {status: "success", message: string, selected_projects: [{name: string, 
             role?: string, priority: number, url?: string, bullets: [string, ...]}]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "selected_projects.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"selected_projects.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"selected_projects.json missing 'message' field")
        if "selected_projects" not in data:
            logger.warning(f"selected_projects.json missing 'selected_projects' field")
            data["selected_projects"] = []
        
        return data
    except FileNotFoundError:
        logger.error(f"selected_projects.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "selected_projects": []}
    except json.JSONDecodeError as e:
        logger.error(f"selected_projects.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "selected_projects": []}
    except Exception as e:
        logger.error(f"selected_projects.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "selected_projects": []}


def load_header_block(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load header.json with schema validation.
    
    Schema: {status: "success", message: string, name: string, location?: string, 
             email: string, phone?: string, links?: [string], target_title: string}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "header.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"header.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"header.json missing 'message' field")
        if "name" not in data:
            logger.warning(f"header.json missing 'name' field")
            data["name"] = ""
        if "email" not in data:
            logger.warning(f"header.json missing 'email' field")
            data["email"] = ""
        if "target_title" not in data:
            logger.warning(f"header.json missing 'target_title' field")
            data["target_title"] = ""
        # Backward compatibility: convert old format to new format
        if "title_line" in data and "target_title" not in data:
            data["target_title"] = data.pop("title_line")
        if "contact_info" in data:
            contact_info = data.pop("contact_info")
            if "name" not in data:
                data["name"] = ""
            if "location" not in data:
                data["location"] = contact_info.get("location", "")
            if "email" not in data:
                data["email"] = contact_info.get("email", "")
            if "phone" not in data:
                data["phone"] = contact_info.get("phone", "")
            if "links" not in data:
                links = []
                if contact_info.get("website"):
                    links.append(contact_info["website"])
                if contact_info.get("linkedin"):
                    links.append(f"linkedin.com/in/{contact_info['linkedin']}")
                if contact_info.get("github"):
                    links.append(f"github.com/{contact_info['github']}")
                if contact_info.get("google_scholar"):
                    links.append(contact_info["google_scholar"])
                data["links"] = links
        
        return data
    except FileNotFoundError:
        logger.debug(f"header.json not found: {file_path} (optional file)")
        return {"status": "success", "message": "File not found", "name": "", "email": "", "target_title": ""}
    except json.JSONDecodeError as e:
        logger.error(f"header.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "name": "", "email": "", "target_title": ""}
    except Exception as e:
        logger.error(f"header.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "name": "", "email": "", "target_title": ""}


def load_summary_block(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load summary.json with schema validation.
    
    Schema: {status: "success", message: string, summary: string, approx_word_count: number}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "summary.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"summary.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"summary.json missing 'message' field")
        if "summary" not in data:
            logger.warning(f"summary.json missing 'summary' field")
            data["summary"] = ""
        if "approx_word_count" not in data:
            # Calculate word count if missing
            data["approx_word_count"] = len(data.get("summary", "").split())
        
        return data
    except FileNotFoundError:
        logger.error(f"summary.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "summary": "", "approx_word_count": 0}
    except json.JSONDecodeError as e:
        logger.error(f"summary.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "summary": "", "approx_word_count": 0}
    except Exception as e:
        logger.error(f"summary.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "summary": "", "approx_word_count": 0}


def load_education_block(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load education.json with schema validation.
    
    Schema: {status: "success", message: string, education: [{degree: string, institution: string, 
             location?: string, dates?: string, honors?: string}]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "education.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"education.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"education.json missing 'message' field")
        if "education" not in data:
            logger.warning(f"education.json missing 'education' field")
            data["education"] = []
        
        return data
    except FileNotFoundError:
        logger.debug(f"education.json not found: {file_path} (optional file)")
        return {"status": "success", "message": "File not found", "education": []}
    except json.JSONDecodeError as e:
        logger.error(f"education.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "education": []}
    except Exception as e:
        logger.error(f"education.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "education": []}


def load_ats_report(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load ats_report.json with schema validation.
    
    Schema: {status: "success"|"degraded"|"error", message: string, keyword_coverage: number, 
             match_score: number, issues: [string], suggestions: [string]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "ats_report.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"ats_report.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"ats_report.json missing 'message' field")
        if "keyword_coverage" not in data:
            logger.warning(f"ats_report.json missing 'keyword_coverage' field")
            data["keyword_coverage"] = 0.0
        if "match_score" not in data:
            logger.warning(f"ats_report.json missing 'match_score' field")
            data["match_score"] = 0.0
        if "issues" not in data:
            logger.warning(f"ats_report.json missing 'issues' field")
            data["issues"] = []
        if "suggestions" not in data:
            logger.warning(f"ats_report.json missing 'suggestions' field")
            data["suggestions"] = []
        # Backward compatibility: convert old format to new format
        if "coverage_score" in data and "keyword_coverage" not in data:
            data["keyword_coverage"] = data.pop("coverage_score")
        if "recommendations" in data and "suggestions" not in data:
            data["suggestions"] = data.pop("recommendations")
        
        return data
    except FileNotFoundError:
        logger.debug(f"ats_report.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "keyword_coverage": 0.0, 
                "match_score": 0.0, "issues": [], "suggestions": []}
    except json.JSONDecodeError as e:
        logger.error(f"ats_report.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "keyword_coverage": 0.0,
                "match_score": 0.0, "issues": [], "suggestions": []}
    except Exception as e:
        logger.error(f"ats_report.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "keyword_coverage": 0.0,
                "match_score": 0.0, "issues": [], "suggestions": []}


def load_privacy_validation_report(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load privacy_report.json with schema validation.
    
    Schema: {status: "success"|"error", message: string, issues: [string], high_risk: [string]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "privacy_report.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"privacy_report.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"privacy_report.json missing 'message' field")
        if "issues" not in data:
            logger.warning(f"privacy_report.json missing 'issues' field")
            data["issues"] = []
        if "high_risk" not in data:
            logger.warning(f"privacy_report.json missing 'high_risk' field")
            data["high_risk"] = []
        
        return data
    except FileNotFoundError:
        logger.debug(f"privacy_report.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "issues": [], "high_risk": []}
    except json.JSONDecodeError as e:
        logger.error(f"privacy_report.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "issues": [], "high_risk": []}
    except Exception as e:
        logger.error(f"privacy_report.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "issues": [], "high_risk": []}


def load_cover_letter(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load cover_letter.json with schema validation.
    
    Schema: {status: "success"|"error", message: string, cover_letter_md: string,
             word_count: number, keywords_used: [string], skills_alignment: [string], red_flags: [string]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "cover_letter.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"cover_letter.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"cover_letter.json missing 'message' field")
        if "cover_letter_md" not in data:
            logger.warning(f"cover_letter.json missing 'cover_letter_md' field")
            data["cover_letter_md"] = ""
        if "word_count" not in data:
            # Calculate word count if missing
            data["word_count"] = len(data.get("cover_letter_md", "").split())
        if "keywords_used" not in data:
            logger.warning(f"cover_letter.json missing 'keywords_used' field")
            data["keywords_used"] = []
        if "skills_alignment" not in data:
            logger.warning(f"cover_letter.json missing 'skills_alignment' field")
            data["skills_alignment"] = []
        if "red_flags" not in data:
            logger.warning(f"cover_letter.json missing 'red_flags' field")
            data["red_flags"] = []
        # Backward compatibility: convert old format to new format
        if "meta" in data and isinstance(data["meta"], dict):
            if "word_count" not in data and "word_count" in data["meta"]:
                data["word_count"] = data["meta"].pop("word_count")
        
        return data
    except FileNotFoundError:
        logger.debug(f"cover_letter.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "cover_letter_md": "",
                "word_count": 0, "keywords_used": [], "skills_alignment": [], "red_flags": []}
    except json.JSONDecodeError as e:
        logger.error(f"cover_letter.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "cover_letter_md": "",
                "word_count": 0, "keywords_used": [], "skills_alignment": [], "red_flags": []}
    except Exception as e:
        logger.error(f"cover_letter.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "cover_letter_md": "",
                "word_count": 0, "keywords_used": [], "skills_alignment": [], "red_flags": []}


def load_template_fix_report(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load template_fix_report.json with schema validation.
    
    Schema: {status: "success"|"error", message: string, changes_made: array, 
             template_path: string, iterations: number, final_match_score: number}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "template_fix_report.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"template_fix_report.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"template_fix_report.json missing 'message' field")
        if "changes" not in data:
            logger.warning(f"template_fix_report.json missing 'changes' field")
            data["changes"] = []
        # Backward compatibility: convert old format to new format
        if "changes_made" in data and "changes" not in data:
            data["changes"] = data.pop("changes_made")
        if "template_path" not in data:
            logger.warning(f"template_fix_report.json missing 'template_path' field")
            data["template_path"] = ""
        if "iterations" not in data:
            logger.warning(f"template_fix_report.json missing 'iterations' field")
            data["iterations"] = 0
        if "final_match_score" not in data:
            logger.warning(f"template_fix_report.json missing 'final_match_score' field")
            data["final_match_score"] = 0.0
        
        return data
    except FileNotFoundError:
        logger.debug(f"template_fix_report.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "changes_made": [],
                "template_path": "", "iterations": 0, "final_match_score": 0.0}
    except json.JSONDecodeError as e:
        logger.error(f"template_fix_report.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "changes_made": [],
                "template_path": "", "iterations": 0, "final_match_score": 0.0}
    except Exception as e:
        logger.error(f"template_fix_report.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "changes_made": [],
                "template_path": "", "iterations": 0, "final_match_score": 0.0}

