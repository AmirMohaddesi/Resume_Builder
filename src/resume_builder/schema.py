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
    location: Optional[str]
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
# LLM JSON Edit Schemas
# ============================================================================

class LLMJsonEditResult(TypedDict, total=False):
    """Result of LLM-based JSON section edit."""
    status: Literal["ok", "error"]
    section: str
    message: str
    updated_json: Optional[Dict[str, Any]]  # Full replacement JSON for that section (if successful)
    warnings: List[str]  # Human-readable warnings (may include formatted diff)
    diff_meta: Optional[Dict[str, Any]]  # Structured diff summary for UI (added_count, removed_count, etc.)



