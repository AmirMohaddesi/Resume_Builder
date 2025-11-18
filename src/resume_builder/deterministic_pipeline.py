"""
Deterministic pipeline functions - pure Python, no LLM calls.
These replace agent-based tasks for maximum speed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from resume_builder.paths import OUTPUT_DIR
from resume_builder.tools.preflight import PreflightTool
from resume_builder.tools.profile_reader import ProfileReaderTool
from resume_builder.tools.latex_package_checker import LaTeXPackageCheckerTool
from resume_builder.tools.ats_rules import ATSRulesTool
from resume_builder.tools.privacy_guard import PrivacyGuardTool

logger = logging.getLogger(__name__)


def run_preflight() -> Dict[str, Any]:
    """Run preflight checks - pure Python, no LLM."""
    tool = PreflightTool()
    result = tool._run(require_engine="xelatex")
    
    output_path = OUTPUT_DIR / "preflight_check.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def validate_profile(profile_path: str) -> Dict[str, Any]:
    """Validate profile - pure Python, no LLM."""
    tool = ProfileReaderTool()
    try:
        profile_str = tool._run(profile_path=profile_path)
        profile_data = json.loads(profile_str)
        
        if not profile_data.get('success', False):
            raise ValueError(profile_data.get('error', 'Failed to read profile'))
        
        profile = profile_data.get('profile', {})
        identity = profile.get('identity', {})
        
        missing_fields = []
        if not identity.get('first'):
            missing_fields.append('first')
        if not identity.get('last'):
            missing_fields.append('last')
        if not identity.get('email'):
            missing_fields.append('email')
        
        ok = len(missing_fields) == 0
        result = {
            "ok": ok,
            "status": "success" if ok else "error",
            "validation_status": "success" if ok else "failed",
            "message": "Profile validation passed" if ok else f"Missing required fields: {', '.join(missing_fields)}",
            "missing_fields": missing_fields,
            "error_type": None if ok else "missing_fields",
            "hint": None if ok else f"Please provide: {', '.join(missing_fields)}"
        }
    except Exception as e:
        result = {
            "ok": False,
            "status": "error",
            "validation_status": "failed",
            "message": f"Profile validation failed: {str(e)}",
            "missing_fields": [],
            "error_type": "validation_error",
            "hint": "Check profile file format and content"
        }
    
    output_path = OUTPUT_DIR / "validated_profile.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def collect_file_info(profile_path: str, custom_template_path: Optional[str] = None) -> Dict[str, Any]:
    """Collect file info - pure Python, no profile mutation."""
    profile_tool = ProfileReaderTool()
    
    try:
        profile_str = profile_tool._run(profile_path=profile_path)
        profile_data = json.loads(profile_str)
        
        if not profile_data.get('success', False):
            raise ValueError(profile_data.get('error', 'Failed to read profile'))
        
        profile = profile_data.get('profile', {})
        identity = profile.get('identity', {})
        
        tex_file_found = custom_template_path is not None and Path(custom_template_path).exists()
        
        email_present = bool(identity.get('email'))
        phone_present = bool(identity.get('phone'))
        missing_fields = []
        critical_missing = []
        
        if not email_present:
            missing_fields.append('email')
            critical_missing.append('email')
        
        if not phone_present:
            missing_fields.append('phone')
        
        if not email_present:
            ok = False
            status = "error"
            message = "Profile validation failed: email is required."
        elif not phone_present:
            ok = True
            status = "warning"
            message = "Profile validation completed with warnings. Email is present, but phone is missing."
        else:
            ok = True
            status = "success"
            message = "Profile validation completed successfully."
        
        result = {
            "ok": ok,
            "status": status,
            "tex_file_found": tex_file_found,
            "validation": {
                "email_present": email_present,
                "phone_present": phone_present,
                "missing_fields": missing_fields,
                "critical_missing": critical_missing
            },
            "recommendations": ["Provide a valid phone number."] if not phone_present else [],
            "message": message
        }
    except Exception as e:
        result = {
            "ok": False,
            "status": "error",
            "tex_file_found": False,
            "validation": {
                "email_present": False,
                "phone_present": False,
                "missing_fields": ["email", "phone"],
                "critical_missing": ["email"]
            },
            "recommendations": [],
            "message": f"File collection failed: {str(e)}"
        }
    
    output_path = OUTPUT_DIR / "file_collection_report.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def validate_template(custom_template_path: Optional[str] = None) -> Dict[str, Any]:
    """Validate template - pure Python, no LLM."""
    custom_template = OUTPUT_DIR / "custom_template.tex"
    if not custom_template.exists() and not (custom_template_path and Path(custom_template_path).exists()):
        result = {
            "status": "skipped",
            "message": "No custom template",
            "template_provided": False,
            "missing_packages": [],
            "critical_missing": [],
            "microtype_warning": False,
            "recommendations": [],
            "error_type": None,
            "hint": None
        }
    else:
        tex_path = custom_template if custom_template.exists() else Path(custom_template_path)
        tool = LaTeXPackageCheckerTool()
        result_str = tool._run(tex_file_path=str(tex_path))
        result = json.loads(result_str)
        result["template_provided"] = True
        result["status"] = "success" if not result.get("critical_missing") else "warning"
    
    output_path = OUTPUT_DIR / "template_validation.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def run_ats_rules_audit(tex_path: str) -> Dict[str, Any]:
    """Run ATS rules audit - pure Python, no LLM."""
    tool = ATSRulesTool()
    result_str = tool._run(tex_path=str(tex_path))
    result = json.loads(result_str)
    
    output_path = OUTPUT_DIR / "ats_rules_audit.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def run_privacy_guard(profile_path: str, jd_text: str) -> Dict[str, Any]:
    """Run privacy guard - uses tool, minimal LLM."""
    tool = PrivacyGuardTool()
    result = tool._run(
        content_path=profile_path,
        profile_path=profile_path,
        content_type="json",
        job_description=jd_text
    )
    
    output_path = OUTPUT_DIR / "privacy_report.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


