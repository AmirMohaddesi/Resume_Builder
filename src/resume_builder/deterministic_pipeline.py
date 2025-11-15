"""
Deterministic pipeline functions - pure Python, no LLM calls.
These replace agent-based tasks for maximum speed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from resume_builder.paths import OUTPUT_DIR
from resume_builder.tools.preflight import PreflightTool
from resume_builder.tools.profile_reader import ProfileReaderTool
from resume_builder.tools.tex_info_extractor import TexInfoExtractorTool
from resume_builder.tools.latex_package_checker import LaTeXPackageCheckerTool
from resume_builder.tools.ats_rules import ATSRulesTool
from resume_builder.tools.privacy_guard import PrivacyGuardTool

logger = logging.getLogger(__name__)


def run_preflight() -> Dict[str, Any]:
    """Run preflight checks - pure Python, no LLM."""
    tool = PreflightTool()
    result = tool._run(require_engine="xelatex")
    
    # Write to file
    output_path = OUTPUT_DIR / "preflight_check.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def validate_profile(profile_path: str) -> Dict[str, Any]:
    """Validate profile - pure Python, no LLM."""
    tool = ProfileReaderTool()
    try:
        profile_str = tool._run(profile_path=profile_path)
        profile_data = json.loads(profile_str)
        
        # ProfileReaderTool returns {"success": True, "profile": {...}, "profile_path": "..."}
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
    
    # Write to file
    output_path = OUTPUT_DIR / "validated_profile.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def collect_file_info(profile_path: str, custom_template_path: Optional[str] = None) -> Dict[str, Any]:
    """Collect and merge file info - pure Python, minimal LLM."""
    profile_tool = ProfileReaderTool()
    tex_tool = TexInfoExtractorTool()
    
    try:
        # Read profile
        profile_str = profile_tool._run(profile_path=profile_path)
        profile_data = json.loads(profile_str)
        
        # ProfileReaderTool returns {"success": True, "profile": {...}, "profile_path": "..."}
        if not profile_data.get('success', False):
            raise ValueError(profile_data.get('error', 'Failed to read profile'))
        
        profile = profile_data.get('profile', {})
        identity = profile.get('identity', {})
        
        tex_file_found = False
        fields_updated = []
        
        # Check for custom template
        custom_template = OUTPUT_DIR / "custom_template.tex"
        if custom_template.exists() or (custom_template_path and Path(custom_template_path).exists()):
            tex_file_found = True
            tex_path = custom_template if custom_template.exists() else Path(custom_template_path)
            
            # Extract contact info from .tex
            tex_info_str = tex_tool._run(tex_file_path=str(tex_path))
            tex_info = json.loads(tex_info_str)
            
            # Merge into profile.identity
            if tex_info.get('email') and not identity.get('email'):
                identity['email'] = tex_info['email']
                fields_updated.append('email')
            if tex_info.get('phone') and not identity.get('phone'):
                identity['phone'] = tex_info['phone']
                fields_updated.append('phone')
            if tex_info.get('website') and not identity.get('website'):
                identity['website'] = tex_info['website']
                fields_updated.append('website')
            if tex_info.get('linkedin') and not identity.get('linkedin'):
                identity['linkedin'] = tex_info['linkedin']
                fields_updated.append('linkedin')
            if tex_info.get('github') and not identity.get('github'):
                identity['github'] = tex_info['github']
                fields_updated.append('github')
            
            # Save updated profile
            profile['identity'] = identity
            profile_path_obj = Path(profile_path)
            profile_path_obj.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        
        # Validate
        email_present = bool(identity.get('email'))
        phone_present = bool(identity.get('phone'))
        missing_fields = []
        critical_missing = []
        
        if not email_present:
            missing_fields.append('email')
            critical_missing.append('email')
        
        if not phone_present:
            missing_fields.append('phone')
        
        # Determine status
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
            "fields_updated": fields_updated,
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
            "fields_updated": [],
            "validation": {
                "email_present": False,
                "phone_present": False,
                "missing_fields": ["email", "phone"],
                "critical_missing": ["email"]
            },
            "recommendations": [],
            "message": f"File collection failed: {str(e)}"
        }
    
    # Write to file
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
        # Parse the JSON result string
        result = json.loads(result_str)
        result["template_provided"] = True
        result["status"] = "success" if not result.get("critical_missing") else "warning"
    
    # Write to file
    output_path = OUTPUT_DIR / "template_validation.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def compute_pipeline_status(
    has_reference_pdfs: bool = False,
    debug: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Compute pipeline status - pure Python, no LLM. Includes task timing tracking."""
    from resume_builder.tools.progress_reporter import ProgressReporterTool
    
    required_files = {
        "validated_profile.json": "profile_validation_task",
        "file_collection_report.json": "collect_file_info_task",
        "selected_experiences.json": "select_experiences_task",
        "selected_skills.json": "select_skills_task",
        "summary_block.json": "write_summary_task",
        "header_block.json": "write_header_task",
    }
    
    optional_files = {
        "preflight_check.json": "preflight_task",
        "template_validation.json": "template_validation_task",
        "parsed_jd.json": "parse_job_description_task",
        "selected_projects.json": "select_projects_task",
        "education_block.json": "write_education_section_task",  # Optional: can read from profile.identity.education
        "ats_report.json": "ats_check_task",
        "privacy_validation_report.json": "privacy_validation_task",
        "cover_letter.json": "write_cover_letter_task",
    }
    
    # Track task timings
    task_timings = {}
    all_files = {**required_files, **optional_files}
    
    # Get start time from preflight (first deterministic task)
    preflight_path = OUTPUT_DIR / "preflight_check.json"
    start_time = None
    if preflight_path.exists():
        try:
            start_time = preflight_path.stat().st_mtime
        except Exception:
            pass
    
    blocking_errors = []
    warnings = []
    phase_status = {}
    what_was_skipped_and_why = []
    
    # Check required files
    for filename, task_name in required_files.items():
        file_path = OUTPUT_DIR / filename
        if not file_path.exists():
            blocking_errors.append(f"Missing required file: {filename}")
            phase_status[task_name] = "skipped"
            what_was_skipped_and_why.append({"phase": task_name, "reason": f"Missing {filename}"})
            task_timings[task_name] = 0.0
        else:
            try:
                # Calculate task duration from file modification time
                if start_time:
                    task_duration = file_path.stat().st_mtime - start_time
                    if task_duration > 0:
                        task_timings[task_name] = task_duration
                    else:
                        task_timings[task_name] = 0.0
                else:
                    task_timings[task_name] = 0.0
                
                data = json.loads(file_path.read_text(encoding='utf-8'))
                ok = data.get('ok', data.get('status') == 'success')
                status = data.get('status', 'success' if ok else 'error')
                
                if not ok or status not in ('success', 'warning'):
                    if filename == "file_collection_report.json" and status == "error":
                        blocking_errors.append(f"{filename}: {data.get('message', 'Validation failed')}")
                        phase_status[task_name] = "error"
                    elif filename == "file_collection_report.json" and status == "warning":
                        warnings.append(f"{filename}: {data.get('message', 'Warning')}")
                        phase_status[task_name] = "warning"
                    else:
                        blocking_errors.append(f"{filename}: {data.get('message', 'Validation failed')}")
                        phase_status[task_name] = "error"
                else:
                    phase_status[task_name] = "success"
            except Exception as e:
                blocking_errors.append(f"{filename}: Invalid JSON - {str(e)}")
                phase_status[task_name] = "error"
                task_timings[task_name] = 0.0
    
    # Check optional files
    for filename, task_name in optional_files.items():
        file_path = OUTPUT_DIR / filename
        if not file_path.exists():
            phase_status[task_name] = "skipped"
            what_was_skipped_and_why.append({"phase": task_name, "reason": f"Missing {filename}"})
            task_timings[task_name] = 0.0
        else:
            try:
                # Calculate task duration
                if start_time:
                    task_duration = file_path.stat().st_mtime - start_time
                    if task_duration > 0:
                        task_timings[task_name] = task_duration
                    else:
                        task_timings[task_name] = 0.0
                else:
                    task_timings[task_name] = 0.0
                
                data = json.loads(file_path.read_text(encoding='utf-8'))
                status = data.get('status', 'success')
                if status == "degraded":
                    phase_status[task_name] = "degraded"
                elif status in ("success", "warning"):
                    phase_status[task_name] = status
                else:
                    phase_status[task_name] = "error"
            except Exception:
                phase_status[task_name] = "skipped"
                task_timings[task_name] = 0.0
    
    # Determine mode
    template_validation = OUTPUT_DIR / "template_validation.json"
    if template_validation.exists():
        try:
            data = json.loads(template_validation.read_text(encoding='utf-8'))
            if data.get('template_provided'):
                mode = "custom_template"
            else:
                mode = "standard"
        except Exception:
            mode = "standard"
    else:
        mode = "standard"
    
    if has_reference_pdfs:
        mode = f"{mode}_with_reference" if mode != "standard" else "with_reference"
    
    # Determine overall status
    ok = len(blocking_errors) == 0
    if ok:
        status = "ready"
        message = "All systems operational."
    else:
        status = "blocked"
        message = "Pipeline has errors."
    
    ready_for_latex = ok and phase_status.get("write_header_task") == "success"
    
    # Report task timings via progress_reporter
    if task_timings:
        total_duration = sum(v for v in task_timings.values() if v > 0)
        progress_tool = ProgressReporterTool()
        for task_name, duration in task_timings.items():
            if duration > 0:
                progress_tool._run(
                    progress=0.55,
                    description="Analyzing task timings...",
                    task_name=task_name,
                    task_duration_seconds=duration
                )
    
    pipeline_status = {
        "ok": ok,
        "status": status,
        "ready_for_latex": ready_for_latex,
        "message": message,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "phase_status": phase_status,
        "what_was_skipped_and_why": what_was_skipped_and_why,
        "mode": mode,
        "self_test": "passed" if ok else "failed"
    }
    
    # Create simple tailor plan
    tailor_plan = {
        "summary": message,
        "mode": mode,
        "ready": ready_for_latex,
        "tasks_completed": sum(1 for s in phase_status.values() if s == "success"),
        "tasks_total": len(phase_status)
    }
    
    # Write files
    pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
    pipeline_status_path.write_text(json.dumps(pipeline_status, indent=2), encoding='utf-8')
    
    tailor_plan_path = OUTPUT_DIR / "tailor_plan.json"
    tailor_plan_path.write_text(json.dumps(tailor_plan, indent=2), encoding='utf-8')
    
    if debug:
        debug_path = OUTPUT_DIR / "pipeline_status_debug.json"
        debug_data = {
            **pipeline_status,
            "debug_info": {
                "timestamp": datetime.now().isoformat(),
                "required_files_checked": list(required_files.keys()),
                "optional_files_checked": list(optional_files.keys())
            }
        }
        debug_path.write_text(json.dumps(debug_data, indent=2), encoding='utf-8')
    
    return pipeline_status, tailor_plan


def run_ats_rules_audit(tex_path: str) -> Dict[str, Any]:
    """Run ATS rules audit - pure Python, no LLM."""
    tool = ATSRulesTool()
    result_str = tool._run(tex_path=str(tex_path))
    result = json.loads(result_str)
    
    # Write to file
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
    
    # Write to file
    output_path = OUTPUT_DIR / "privacy_validation_report.json"
    output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    
    return result


def create_compact_profile_view(profile_path: str) -> Dict[str, Any]:
    """Create compact profile view for LLM tasks - reduces token usage."""
    tool = ProfileReaderTool()
    profile_str = tool._run(profile_path=profile_path)
    profile_data = json.loads(profile_str)
    
    # ProfileReaderTool returns {"success": True, "profile": {...}, "profile_path": "..."}
    if not profile_data.get('success', False):
        raise ValueError(profile_data.get('error', 'Failed to read profile'))
    
    profile = profile_data.get('profile', {})
    identity = profile.get('identity', {})
    experiences = profile.get('experiences', [])
    skills = profile.get('skills', [])
    
    # Extract minimal info
    compact = {
        "name": f"{identity.get('first', '')} {identity.get('last', '')}".strip(),
        "current_title": experiences[0].get('title', '') if experiences else '',
        "location": identity.get('address', ''),
        "skills": skills[:20],  # Top 20 skills
        "key_experiences": [
            {
                "title": exp.get('title', ''),
                "organization": exp.get('organization', ''),
                "dates": exp.get('dates', '')
            }
            for exp in experiences[:2]  # Just 2 most recent
        ]
    }
    
    # Write to file
    output_path = OUTPUT_DIR / "profile_llm_view.json"
    output_path.write_text(json.dumps(compact, indent=2), encoding='utf-8')
    
    return compact

