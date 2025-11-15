"""
Centralized JSON schema definitions and validation helpers.

This module defines the expected structure of all JSON files produced by agents
and provides validation functions to ensure consistency.
"""
from __future__ import annotations

from typing import TypedDict, List, Optional, Dict, Any, Literal
from pathlib import Path


# ============================================================================
# Profile Schema
# ============================================================================

class ProfileIdentity(TypedDict, total=False):
    """User profile identity section."""
    first: str
    last: str
    email: str
    phone: Optional[str]
    website: Optional[str]
    linkedin: Optional[str]
    github: Optional[str]
    education: List[Dict[str, Any]]


class Profile(TypedDict, total=False):
    """User profile structure (user_profile.json)."""
    identity: ProfileIdentity
    experience: List[Dict[str, Any]]
    skills: List[str]
    projects: List[Dict[str, Any]]


# ============================================================================
# Phase Output Schemas
# ============================================================================

class ValidatedProfile(TypedDict, total=False):
    """Profile validation output (validated_profile.json)."""
    ok: bool
    status: Literal["success", "error"]
    message: str
    validation_status: Literal["success", "failed"]
    missing_fields: List[str]
    error_type: Optional[str]
    hint: Optional[str]


class FileCollectionReport(TypedDict, total=False):
    """File collection report (file_collection_report.json)."""
    ok: bool
    status: Literal["enhanced", "normalized", "skipped", "warning"]
    message: str
    tex_file_found: bool
    fields_updated: List[str]
    validation: Dict[str, Any]
    recommendations: Optional[str]


class ParsedJD(TypedDict, total=False):
    """Parsed job description (parsed_jd.json)."""
    status: Literal["success", "error"]
    message: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    skills: List[str]
    keywords: List[str]
    cleaned_text: str


class SelectedExperiences(TypedDict, total=False):
    """Selected experiences (selected_experiences.json)."""
    status: Literal["success", "error"]
    message: str
    selected_experiences: List[Dict[str, Any]]
    reasoning: str


class SelectedProjects(TypedDict, total=False):
    """Selected projects (selected_projects.json)."""
    status: Literal["success", "error"]
    message: str
    selected_projects: List[Dict[str, Any]]
    reasoning: str


class SelectedSkills(TypedDict, total=False):
    """Selected skills (selected_skills.json)."""
    status: Literal["success", "error"]
    message: str
    selected_skills: List[str]
    reasoning: str


class SummaryBlock(TypedDict, total=False):
    """Summary block (summary_block.json)."""
    status: Literal["success", "error"]
    message: str
    summary: str


class EducationBlock(TypedDict, total=False):
    """Education block (education_block.json)."""
    status: Literal["success", "error"]
    message: str
    education: List[Dict[str, Any]]


class ATSReport(TypedDict, total=False):
    """ATS compatibility report (ats_report.json)."""
    status: Literal["success", "error", "degraded"]
    message: str
    coverage_score: Optional[int]
    present_keywords: List[str]
    missing_keywords: List[str]
    recommendations: Optional[str]
    error_type: Optional[str]
    hint: Optional[str]


class PrivacyReport(TypedDict, total=False):
    """Privacy validation report (privacy_validation_report.json)."""
    status: Literal["success", "error"]
    message: str
    validation_status: Literal["pass", "fail"]
    issues: List[str]
    error_type: Optional[str]
    hint: Optional[str]


class CoverLetter(TypedDict, total=False):
    """Cover letter (cover_letter.json)."""
    ok: bool
    status: Literal["success", "error", "degraded"]
    message: str
    cover_letter_md: str
    keywords_used: List[str]
    skills_alignment: List[str]
    red_flags: List[str]
    meta: Dict[str, Any]
    error_type: Optional[str]
    hint: Optional[str]


class TemplateValidation(TypedDict, total=False):
    """Template validation (template_validation.json)."""
    status: Literal["success", "warning", "skipped"]
    message: str
    template_provided: bool
    missing_packages: List[str]
    critical_missing: List[str]
    microtype_warning: bool
    recommendations: Optional[str]
    error_type: Optional[str]
    hint: Optional[str]


# ============================================================================
# Orchestrator Output Schemas
# ============================================================================

PhaseStatus = Literal["success", "error", "warning", "degraded", "skipped"]


class PhaseStatusMap(TypedDict, total=False):
    """Phase status mapping."""
    preflight_task: PhaseStatus
    profile_validation_task: PhaseStatus
    collect_file_info_task: PhaseStatus
    template_validation_task: PhaseStatus
    parse_job_description_task: PhaseStatus
    select_experiences_task: PhaseStatus
    select_projects_task: PhaseStatus
    select_skills_task: PhaseStatus
    write_summary_task: PhaseStatus
    write_education_section_task: PhaseStatus
    ats_check_task: PhaseStatus
    privacy_validation_task: PhaseStatus
    write_cover_letter_task: PhaseStatus


class SkippedPhase(TypedDict):
    """Skipped phase entry."""
    phase: str
    reason: str


class PipelineStatus(TypedDict, total=False):
    """Pipeline status (pipeline_status.json) - SINGLE SOURCE OF TRUTH."""
    ok: bool
    status: Literal["ready", "blocked", "degraded"]
    ready_for_latex: bool
    message: str
    blocking_errors: List[str]
    warnings: List[str]
    phase_status: PhaseStatusMap
    what_was_skipped_and_why: List[SkippedPhase]
    mode: Literal["standard", "custom_template", "with_reference", "custom_with_reference"]
    self_test: Literal["passed", "failed"]


class TailorPlan(TypedDict, total=False):
    """Tailor plan (tailor_plan.json) - Human-readable summary."""
    ok: bool
    status: Literal["success", "error"]
    message: str
    plan: Dict[str, Any]
    mode: Literal["standard", "custom_template", "with_reference", "custom_with_reference"]


class DebugTraceStep(TypedDict, total=False):
    """Debug trace step."""
    step: str
    file: str
    exists: bool
    status: str
    reasoning: str


class InputFileDetected(TypedDict, total=False):
    """Input file detection entry."""
    file: str
    exists: bool
    size: Optional[int]
    schema_valid: Optional[bool]
    reason: Optional[str]


class PhaseStateExplanation(TypedDict, total=False):
    """Phase state explanation."""
    status: str
    reasoning: str


class PipelineStatusDebug(TypedDict, total=False):
    """Pipeline status debug (pipeline_status_debug.json)."""
    debug_mode: bool
    orchestration_trace: List[DebugTraceStep]
    input_files_detected: List[InputFileDetected]
    phase_state_explanations: Dict[str, PhaseStateExplanation]
    ready_for_latex_reasoning: str


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_required_fields(data: dict, required_fields: list[str], schema_name: str) -> tuple[bool, list[str]]:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        schema_name: Name of schema for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    for field in required_fields:
        if field not in data:
            errors.append(f"{schema_name}: Missing required field '{field}'")
    return len(errors) == 0, errors


def validate_status_field(data: dict, schema_name: str) -> tuple[bool, list[str]]:
    """
    Validate that status field is present and has valid value.
    
    Args:
        data: Dictionary to validate
        schema_name: Name of schema for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    if "status" not in data:
        errors.append(f"{schema_name}: Missing required field 'status'")
    else:
        valid_statuses = ["success", "error", "warning", "degraded", "skipped"]
        if data["status"] not in valid_statuses:
            errors.append(f"{schema_name}: Invalid status '{data['status']}', must be one of {valid_statuses}")
    return len(errors) == 0, errors


def validate_message_field(data: dict, schema_name: str) -> tuple[bool, list[str]]:
    """
    Validate that message field is present and non-empty.
    
    Args:
        data: Dictionary to validate
        schema_name: Name of schema for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    if "message" not in data:
        errors.append(f"{schema_name}: Missing required field 'message'")
    elif not isinstance(data["message"], str) or len(data["message"].strip()) == 0:
        errors.append(f"{schema_name}: Field 'message' must be a non-empty string")
    return len(errors) == 0, errors


def validate_pipeline_status(data: dict) -> tuple[bool, list[str]]:
    """
    Validate pipeline_status.json structure.
    
    Args:
        data: Dictionary to validate
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Required top-level fields
    required = ["ok", "status", "ready_for_latex", "message", "blocking_errors", "warnings", 
                "phase_status", "what_was_skipped_and_why", "mode", "self_test"]
    is_valid, field_errors = validate_required_fields(data, required, "pipeline_status")
    errors.extend(field_errors)
    
    if not is_valid:
        return False, errors
    
    # Validate types
    if not isinstance(data["ok"], bool):
        errors.append("pipeline_status: Field 'ok' must be a boolean")
    
    if data["status"] not in ["ready", "blocked", "degraded"]:
        errors.append(f"pipeline_status: Invalid status '{data['status']}', must be 'ready', 'blocked', or 'degraded'")
    
    if not isinstance(data["ready_for_latex"], bool):
        errors.append("pipeline_status: Field 'ready_for_latex' must be a boolean")
    
    if not isinstance(data["blocking_errors"], list):
        errors.append("pipeline_status: Field 'blocking_errors' must be a list")
    
    if not isinstance(data["warnings"], list):
        errors.append("pipeline_status: Field 'warnings' must be a list")
    
    if not isinstance(data["phase_status"], dict):
        errors.append("pipeline_status: Field 'phase_status' must be a dict")
    
    if not isinstance(data["what_was_skipped_and_why"], list):
        errors.append("pipeline_status: Field 'what_was_skipped_and_why' must be a list")
    
    if data["mode"] not in ["standard", "custom_template", "with_reference", "custom_with_reference"]:
        errors.append(f"pipeline_status: Invalid mode '{data['mode']}'")
    
    if data["self_test"] not in ["passed", "failed"]:
        errors.append(f"pipeline_status: Invalid self_test '{data['self_test']}', must be 'passed' or 'failed'")
    
    # Validate phase_status values
    if isinstance(data.get("phase_status"), dict):
        valid_phase_statuses = ["success", "error", "warning", "degraded", "skipped"]
        for phase, status in data["phase_status"].items():
            if status not in valid_phase_statuses:
                errors.append(f"pipeline_status.phase_status: Invalid status '{status}' for phase '{phase}'")
    
    return len(errors) == 0, errors


def validate_task_output(data: dict, task_name: str, required_fields: list[str]) -> tuple[bool, list[str]]:
    """
    Validate a task output JSON against its expected schema.
    
    Args:
        data: Dictionary to validate
        task_name: Name of task for error messages
        required_fields: List of required field names (in addition to status, message)
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # All tasks must have status and message
    is_valid, status_errors = validate_status_field(data, task_name)
    errors.extend(status_errors)
    
    is_valid, message_errors = validate_message_field(data, task_name)
    errors.extend(message_errors)
    
    # Validate required task-specific fields
    is_valid, field_errors = validate_required_fields(data, required_fields, task_name)
    errors.extend(field_errors)
    
    return len(errors) == 0, errors


def validate_parsed_jd(data: dict) -> tuple[bool, list[str]]:
    """Validate parsed_jd.json."""
    return validate_task_output(data, "parsed_jd", ["title", "company", "skills", "keywords", "cleaned_text"])


def validate_selected_experiences(data: dict) -> tuple[bool, list[str]]:
    """Validate selected_experiences.json."""
    return validate_task_output(data, "selected_experiences", ["selected_experiences", "reasoning"])


def validate_selected_projects(data: dict) -> tuple[bool, list[str]]:
    """Validate selected_projects.json."""
    return validate_task_output(data, "selected_projects", ["selected_projects", "reasoning"])


def validate_selected_skills(data: dict) -> tuple[bool, list[str]]:
    """Validate selected_skills.json."""
    return validate_task_output(data, "selected_skills", ["selected_skills", "reasoning"])


def validate_summary_block(data: dict) -> tuple[bool, list[str]]:
    """Validate summary_block.json."""
    return validate_task_output(data, "summary_block", ["summary"])


def validate_education_block(data: dict) -> tuple[bool, list[str]]:
    """Validate education_block.json."""
    return validate_task_output(data, "education_block", ["education"])


def validate_ats_report(data: dict) -> tuple[bool, list[str]]:
    """Validate ats_report.json."""
    errors = []
    is_valid, base_errors = validate_task_output(data, "ats_report", [])
    errors.extend(base_errors)
    
    # ATS report should have coverage_score if status is success
    if data.get("status") == "success" and "coverage_score" not in data:
        errors.append("ats_report: Missing 'coverage_score' field when status is 'success'")
    
    return len(errors) == 0, errors


def validate_cover_letter(data: dict) -> tuple[bool, list[str]]:
    """Validate cover_letter.json."""
    errors = []
    
    # Cover letter uses 'ok' instead of just 'status'
    if "ok" not in data:
        errors.append("cover_letter: Missing required field 'ok'")
    elif not isinstance(data["ok"], bool):
        errors.append("cover_letter: Field 'ok' must be a boolean")
    
    is_valid, base_errors = validate_task_output(data, "cover_letter", ["cover_letter_md"])
    errors.extend(base_errors)
    
    return len(errors) == 0, errors

