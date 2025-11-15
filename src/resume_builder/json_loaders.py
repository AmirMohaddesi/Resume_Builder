"""
Centralized JSON loading functions with schema validation.

All JSON files written by agents follow standardized schemas defined in tasks.yaml.
This module provides helper functions to load and validate these JSON files.
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
    
    Schema: {status: "success", message: string, selected_experiences: [{organization: string, 
             title: string, location?: string, dates: string, description: string}]}
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
    
    Schema: {status: "success", message: string, selected_skills: [string, ...]}
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
        if "selected_skills" not in data:
            logger.warning(f"selected_skills.json missing 'selected_skills' field")
            data["selected_skills"] = []
        
        return data
    except FileNotFoundError:
        logger.error(f"selected_skills.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "selected_skills": []}
    except json.JSONDecodeError as e:
        logger.error(f"selected_skills.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "selected_skills": []}
    except Exception as e:
        logger.error(f"selected_skills.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "selected_skills": []}


def load_selected_projects(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load selected_projects.json with schema validation.
    
    Schema: {status: "success", message: string, selected_projects: [{name: string, 
             description: string, url?: string}]}
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
    Load header_block.json with schema validation.
    
    Schema: {status: "success", message: string, title_line: string, 
             contact_info: {phone?: string, email?: string, location?: string, 
             website?: string, linkedin?: string, github?: string, google_scholar?: string}}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "header_block.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"header_block.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"header_block.json missing 'message' field")
        if "title_line" not in data:
            logger.warning(f"header_block.json missing 'title_line' field")
            data["title_line"] = ""
        if "contact_info" not in data:
            logger.warning(f"header_block.json missing 'contact_info' field")
            data["contact_info"] = {}
        
        return data
    except FileNotFoundError:
        logger.debug(f"header_block.json not found: {file_path} (optional file)")
        return {"status": "success", "message": "File not found", "title_line": "", "contact_info": {}}
    except json.JSONDecodeError as e:
        logger.error(f"header_block.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "title_line": "", "contact_info": {}}
    except Exception as e:
        logger.error(f"header_block.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "title_line": "", "contact_info": {}}


def load_summary_block(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load summary_block.json with schema validation.
    
    Schema: {status: "success", message: string, summary: string}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "summary_block.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"summary_block.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"summary_block.json missing 'message' field")
        if "summary" not in data:
            logger.warning(f"summary_block.json missing 'summary' field")
            data["summary"] = ""
        
        return data
    except FileNotFoundError:
        logger.error(f"summary_block.json not found: {file_path}")
        return {"status": "error", "message": "File not found", "summary": ""}
    except json.JSONDecodeError as e:
        logger.error(f"summary_block.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "summary": ""}
    except Exception as e:
        logger.error(f"summary_block.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "summary": ""}


def load_education_block(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load education_block.json with schema validation.
    
    Schema: {status: "success", message: string, education: [{degree: string, institution: string, 
             location?: string, dates: string, gpa?: string, honors?: string}]}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "education_block.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"education_block.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"education_block.json missing 'message' field")
        if "education" not in data:
            logger.warning(f"education_block.json missing 'education' field")
            data["education"] = []
        
        return data
    except FileNotFoundError:
        logger.debug(f"education_block.json not found: {file_path} (optional file)")
        return {"status": "success", "message": "File not found", "education": []}
    except json.JSONDecodeError as e:
        logger.error(f"education_block.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "education": []}
    except Exception as e:
        logger.error(f"education_block.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "education": []}


def load_ats_report(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load ats_report.json with schema validation.
    
    Schema: {status: "success"|"degraded"|"error", message: string, coverage_score: number, 
             present_keywords: array, missing_keywords: array, recommendations: array, 
             error_type?: string, hint?: string}
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
        if "coverage_score" not in data:
            logger.warning(f"ats_report.json missing 'coverage_score' field")
            data["coverage_score"] = 0.0
        if "present_keywords" not in data:
            logger.warning(f"ats_report.json missing 'present_keywords' field")
            data["present_keywords"] = []
        if "missing_keywords" not in data:
            logger.warning(f"ats_report.json missing 'missing_keywords' field")
            data["missing_keywords"] = []
        if "recommendations" not in data:
            logger.warning(f"ats_report.json missing 'recommendations' field")
            data["recommendations"] = []
        
        return data
    except FileNotFoundError:
        logger.debug(f"ats_report.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "coverage_score": 0.0, 
                "present_keywords": [], "missing_keywords": [], "recommendations": []}
    except json.JSONDecodeError as e:
        logger.error(f"ats_report.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "coverage_score": 0.0,
                "present_keywords": [], "missing_keywords": [], "recommendations": []}
    except Exception as e:
        logger.error(f"ats_report.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "coverage_score": 0.0,
                "present_keywords": [], "missing_keywords": [], "recommendations": []}


def load_privacy_validation_report(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load privacy_validation_report.json with schema validation.
    
    Schema: {status: "success"|"error", message: string, validation_status: "passed"|"failed"|"warning", 
             issues: array, error_type?: string, hint?: string}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "privacy_validation_report.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "status" not in data:
            logger.warning(f"privacy_validation_report.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"privacy_validation_report.json missing 'message' field")
        if "validation_status" not in data:
            logger.warning(f"privacy_validation_report.json missing 'validation_status' field")
            data["validation_status"] = "unknown"
        if "issues" not in data:
            logger.warning(f"privacy_validation_report.json missing 'issues' field")
            data["issues"] = []
        
        return data
    except FileNotFoundError:
        logger.debug(f"privacy_validation_report.json not found: {file_path} (optional file)")
        return {"status": "error", "message": "File not found", "validation_status": "unknown", "issues": []}
    except json.JSONDecodeError as e:
        logger.error(f"privacy_validation_report.json: Invalid JSON - {e}")
        return {"status": "error", "message": f"Invalid JSON: {e}", "validation_status": "unknown", "issues": []}
    except Exception as e:
        logger.error(f"privacy_validation_report.json: Error reading file - {e}")
        return {"status": "error", "message": str(e), "validation_status": "unknown", "issues": []}


def load_cover_letter(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load cover_letter.json with schema validation.
    
    Schema: {ok: boolean, status: "success"|"error", message: string, cover_letter_md: string, 
             keywords_used: array, skills_alignment: array, red_flags: array, 
             meta: {word_count: number, jd_available: boolean}, error_type: string|null, hint: string|null}
    """
    if file_path is None:
        file_path = OUTPUT_DIR / "cover_letter.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            cleaned_content = clean_json_content(raw_content)
            data = json.loads(cleaned_content)
        
        # Validate required fields
        if "ok" not in data:
            logger.warning(f"cover_letter.json missing 'ok' field")
        if "status" not in data:
            logger.warning(f"cover_letter.json missing 'status' field")
        if "message" not in data:
            logger.warning(f"cover_letter.json missing 'message' field")
        if "cover_letter_md" not in data:
            logger.warning(f"cover_letter.json missing 'cover_letter_md' field")
            data["cover_letter_md"] = ""
        if "keywords_used" not in data:
            logger.warning(f"cover_letter.json missing 'keywords_used' field")
            data["keywords_used"] = []
        if "skills_alignment" not in data:
            logger.warning(f"cover_letter.json missing 'skills_alignment' field")
            data["skills_alignment"] = []
        if "red_flags" not in data:
            logger.warning(f"cover_letter.json missing 'red_flags' field")
            data["red_flags"] = []
        if "meta" not in data:
            logger.warning(f"cover_letter.json missing 'meta' field")
            data["meta"] = {"word_count": 0, "jd_available": False}
        
        return data
    except FileNotFoundError:
        logger.debug(f"cover_letter.json not found: {file_path} (optional file)")
        return {"ok": False, "status": "error", "message": "File not found", "cover_letter_md": "",
                "keywords_used": [], "skills_alignment": [], "red_flags": [],
                "meta": {"word_count": 0, "jd_available": False}, "error_type": None, "hint": None}
    except json.JSONDecodeError as e:
        logger.error(f"cover_letter.json: Invalid JSON - {e}")
        return {"ok": False, "status": "error", "message": f"Invalid JSON: {e}", "cover_letter_md": "",
                "keywords_used": [], "skills_alignment": [], "red_flags": [],
                "meta": {"word_count": 0, "jd_available": False}, "error_type": None, "hint": None}
    except Exception as e:
        logger.error(f"cover_letter.json: Error reading file - {e}")
        return {"ok": False, "status": "error", "message": str(e), "cover_letter_md": "",
                "keywords_used": [], "skills_alignment": [], "red_flags": [],
                "meta": {"word_count": 0, "jd_available": False}, "error_type": None, "hint": None}


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
        if "changes_made" not in data:
            logger.warning(f"template_fix_report.json missing 'changes_made' field")
            data["changes_made"] = []
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

