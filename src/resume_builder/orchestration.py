"""
Pipeline orchestration functions.

This module contains the high-level orchestration logic for running the resume generation pipeline.
It handles:
- CrewAI agent execution
- Pipeline status computation
- LaTeX generation and compilation
- PDF generation
- Template matching

All orchestration logic is separated from CLI/UI concerns.
"""

from __future__ import annotations

import os
import sys
import json
import re
import traceback
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Import paths and constants
from resume_builder.paths import (
    PROJECT_ROOT, OUTPUT_DIR, GENERATED_DIR, LOG_DIR, TEMPLATES, ensure_dirs
)
from resume_builder.logger import get_logger

# Import crew and deterministic pipeline
from resume_builder.crew import ResumeTeam
from resume_builder.deterministic_pipeline import (
    run_preflight,
    validate_profile,
    collect_file_info,
    validate_template,
)

# Import JSON loaders
from resume_builder.json_loaders import (
    load_summary_block,
    load_selected_experiences,
    load_selected_skills,
    load_education_block,
    load_selected_projects,
    load_header_block,
    load_cover_letter,
)

# Path constants
FINAL_PDF = GENERATED_DIR / "final_resume.pdf"
RENDERED_TEX = GENERATED_DIR / "rendered_resume.tex"
COVER_LETTER_PDF = GENERATED_DIR / "cover_letter.pdf"
COVER_LETTER_TEX = GENERATED_DIR / "cover_letter.tex"

# Default paths
DEFAULT_TEMPLATE_PATH = Path(
    os.getenv("TEMPLATE_PATH", TEMPLATES / "main.tex")
)
DEFAULT_PROFILE_PATH = Path(
    os.getenv("PROFILE_PATH", PROJECT_ROOT / "src" / "resume_builder" / "data" / "profile.json")
)


# COMMENTED OUT: Replaced by project_summarizer LLM tool in agents
# The project_selector agent now uses project_summarizer tool to intelligently summarize bullets
# def _summarize_project_bullets_if_needed(projects: list) -> list:
#     """
#     Post-process project bullets to ensure they're concise and fit within 1-2 page resume.
#     This is a safety net in case the agent didn't fully summarize bullets.
#     
#     Args:
#         projects: List of project dicts with 'bullets' field
#         
#     Returns:
#         List of projects with summarized bullets if needed
#     """
#     logger = get_logger()
#     summarized_projects = []
#     
#     for proj in projects:
#         bullets = proj.get('bullets', [])
#         if not bullets:
#             summarized_projects.append(proj)
#             continue
#         
#         summarized_bullets = []
#         for bullet in bullets:
#             if not bullet or not isinstance(bullet, str):
#                 continue
#             
#             # Count words in bullet
#             word_count = len(bullet.split())
#             
#             # If bullet is too long (>30 words), try to summarize it
#             if word_count > 30:
#                 # Simple heuristic: take first sentence or first 20 words
#                 # This is a fallback - the agent should have done better summarization
#                 sentences = bullet.split('. ')
#                 if sentences and len(sentences[0].split()) <= 25:
#                     # Use first sentence if it's reasonable length
#                     summarized = sentences[0].rstrip('.') + '.'
#                 else:
#                     # Take first 20 words
#                     words = bullet.split()[:20]
#                     summarized = ' '.join(words)
#                     if not summarized.endswith(('.', '!', '?')):
#                         summarized += '.'
#                 
#                 logger.debug(f"Summarized bullet from {word_count} to {len(summarized.split())} words: {summarized[:50]}...")
#                 summarized_bullets.append(summarized)
#             else:
#                 summarized_bullets.append(bullet)
#         
#         # If project has too many bullets (>3), keep only top 3
#         if len(summarized_bullets) > 3:
#             logger.debug(f"Reducing bullets from {len(summarized_bullets)} to 3 for project: {proj.get('name', 'Unknown')}")
#             summarized_bullets = summarized_bullets[:3]
#         
#         # Create updated project dict
#         updated_proj = proj.copy()
#         updated_proj['bullets'] = summarized_bullets
#         summarized_projects.append(updated_proj)
#     
#     return summarized_projects


def _generate_cover_letter_pdf(cover_letter_data: Dict[str, Any], output_dir: Path) -> Optional[Path]:
    """Generate cover letter PDF from JSON data."""
    logger = get_logger()
    try:
        from resume_builder.latex_builder import LaTeXBuilder
        from resume_builder.tools.latex_compile import LatexCompileTool
        
        # Load user profile for contact info
        profile_path = output_dir / "user_profile.json"
        identity = {}
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                    identity = profile.get('identity', {})
            except Exception:
                pass
        
        # Get cover letter content
        cover_letter_md = cover_letter_data.get("cover_letter_md", "")
        if not cover_letter_md:
            logger.warning("Cover letter JSON missing cover_letter_md field")
            return None
        
        # Load template
        template_path = TEMPLATES / "cover_letter.tex"
        if not template_path.exists():
            logger.error(f"Cover letter template not found: {template_path}")
            return None
        
        template = template_path.read_text(encoding='utf-8')
        
        # Build LaTeX content
        builder = LaTeXBuilder()
        
        # Extract contact info
        first_name = identity.get('first', '')
        last_name = identity.get('last', '')
        email = identity.get('email', '')
        phone = identity.get('phone', '')
        location = identity.get('location', '')
        website = identity.get('website', '')
        
        # Build header
        name = f"{first_name} {last_name}".strip()
        contact_lines = []
        if email:
            contact_lines.append(email)
        if phone:
            contact_lines.append(phone)
        if location:
            contact_lines.append(location)
        if website:
            contact_lines.append(website)
        
        # Build header LaTeX with name bold and contact info below
        header_parts = []
        if name:
            header_parts.append(f'\\textbf{{{builder.escape_latex(name)}}}')
        for contact in contact_lines:
            header_parts.append(builder.escape_latex(contact))
        header = '\\\\\n        '.join(header_parts) if header_parts else ''
        
        # Parse cover letter markdown to extract recipient and body
        lines = cover_letter_md.split('\n')
        recipient = ""
        greeting = "Dear Hiring Manager,"
        body_lines = []
        closing = "Sincerely,\n[Your Name]"
        
        # Simple parsing: look for "Dear" line, then body, then closing
        in_body = False
        greeting_found = False
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if in_body:
                    body_lines.append('')
                continue
            
            if not greeting_found and line.lower().startswith('dear'):
                greeting = line
                greeting_found = True
                in_body = True
            elif in_body and (line.lower().startswith('sincerely') or line.lower().startswith('best regards') or line.lower().startswith('regards')):
                closing = '\n'.join(lines[i:])
                break
            elif in_body:
                body_lines.append(line)
        
        # If no greeting found, use entire content as body (might already include greeting)
        if not greeting_found:
            body = cover_letter_md
        else:
            body = '\n\n'.join(body_lines) if body_lines else cover_letter_md
        
        # Escape LaTeX (header is already escaped above)
        recipient_escaped = builder.escape_latex(recipient) if recipient else ''
        greeting_escaped = builder.escape_latex(greeting) if greeting else 'Dear Hiring Manager,'
        body_escaped = builder.escape_latex(body, keep_commands=True)  # Allow some formatting
        closing_escaped = builder.escape_latex(closing) if closing else 'Sincerely,\n[Your Name]'
        
        # Replace name placeholder
        if '[Your Name]' in closing_escaped:
            closing_escaped = closing_escaped.replace('[Your Name]', name if name else '[Your Name]')
        
        # Replace template markers
        if header:
            header_latex = f'\\begin{{flushright}}\n        {header}\n    \\end{{flushright}}\n    \\vspace{{0.5cm}}'
        else:
            header_latex = ''
        latex_content = template.replace('% === AUTO:HEADER ===', header_latex)
        latex_content = latex_content.replace('% === AUTO:RECIPIENT ===', recipient_escaped)
        latex_content = latex_content.replace('% === AUTO:GREETING ===', greeting_escaped)
        latex_content = latex_content.replace('% === AUTO:BODY ===', body_escaped)
        latex_content = latex_content.replace('% === AUTO:CLOSING ===', closing_escaped)
        
        # Write LaTeX file
        COVER_LETTER_TEX.write_text(latex_content, encoding='utf-8')
        logger.info(f"Cover letter LaTeX written to: {COVER_LETTER_TEX}")
        
        # Compile to PDF
        compiler = LatexCompileTool()
        result = compiler._run(
            tex_path=str(COVER_LETTER_TEX),
            out_name="cover_letter.pdf",
            engine="auto"
        )
        
        if result.get("success") and COVER_LETTER_PDF.exists():
            return COVER_LETTER_PDF
        else:
            logger.error(f"Cover letter PDF compilation failed: {result.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        logger.exception(f"Error generating cover letter PDF: {e}")
        return None


def run_pipeline(
    jd_text: str,
    profile_path: Optional[str],
    custom_template_path: Optional[str] = None,
    reference_pdf_paths: Optional[list] = None,
    progress_callback=None,
    debug: bool = False,
    enable_ats: bool = True,
    enable_privacy: bool = True,
    enable_cover_letter: bool = True,
    fast_mode: bool = True,  # Default to fast mode for cost/speed optimization
    enforce_2_page_limit: bool = True  # Default to enforcing 2-page limit
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Run the full resume generation pipeline.
    
    Args:
        jd_text: Job description text
        profile_path: Path to user profile JSON
        custom_template_path: Optional custom LaTeX template path
        reference_pdf_paths: Optional list of reference PDF paths for style matching
        progress_callback: Optional callback function(progress: float, desc: str)
        debug: If True, enables debug mode (produces pipeline_status_debug.json)
        enable_ats: If False, skip ATS check task (default: True)
        enable_privacy: If False, skip privacy validation task (default: True)
        enable_cover_letter: If False, skip cover letter generation (default: True)
        fast_mode: If True, use optimized settings for speed (default: False)
    
    Returns:
        Tuple of (pdf_path, status_message, cover_letter_pdf_path)
    """
    ensure_dirs()
    logger = get_logger()
    
    if not jd_text or not jd_text.strip():
        return None, "[error] Job description cannot be empty.", None
    
    # Use provided profile path or default
    if profile_path is None:
        profile_path = str(DEFAULT_PROFILE_PATH)
    
    profile_path_obj = Path(profile_path)
    if not profile_path_obj.exists():
        return None, f"[error] Profile not found at: {profile_path}", None
    
    # Use provided template or default
    if custom_template_path:
        template_path = Path(custom_template_path)
        if not template_path.exists():
            logger.warning(f"Custom template not found: {custom_template_path}, using default")
            template_path = DEFAULT_TEMPLATE_PATH
    else:
        template_path = DEFAULT_TEMPLATE_PATH
    
    # Mode detection is handled by deterministic_pipeline.compute_pipeline_status() based on template_validation.json
    has_reference_pdfs = reference_pdf_paths and len(reference_pdf_paths) > 0
    
    logger.info("="*80)
    logger.info(f"Starting resume generation pipeline")
    logger.info(f"Profile: {profile_path}")
    logger.info(f"Template: {template_path}")
    if custom_template_path:
        logger.info(f"Custom template: {custom_template_path}")
    if has_reference_pdfs:
        logger.info(f"Reference PDFs: {len(reference_pdf_paths)} file(s)")
        for i, pdf_path in enumerate(reference_pdf_paths, 1):
            logger.info(f"  - PDF {i}: {pdf_path}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("="*80)
    
    # ============================================
    # PHASE 0 & 1: Run deterministic tasks (pure Python, no LLM)
    # ============================================
    
    def update_progress(p, desc):
        """Helper for stable progress milestones."""
        if progress_callback:
            progress_callback(p, desc=desc)
    
    update_progress(0.0, "Starting pipeline...")
    
    # Preflight
    try:
        preflight_result = run_preflight()
        if not preflight_result.get('ok'):
            error_msg = preflight_result.get('error', 'Preflight check failed')
            logger.error(f"Preflight failed: {error_msg}")
            return None, f"[error] Preflight check failed: {error_msg}", None
        logger.info("✅ Preflight checks passed")
        update_progress(0.05, "Preflight checks passed")
    except Exception as e:
        logger.error(f"Preflight error: {e}", exc_info=True)
        return None, f"[error] Preflight check error: {str(e)}", None
    
    # Profile validation
    try:
        validation_result = validate_profile(profile_path)
        if not validation_result.get('ok'):
            error_msg = validation_result.get('message', 'Profile validation failed')
            logger.error(f"Profile validation failed: {error_msg}")
            return None, f"[error] {error_msg}", None
        logger.info("✅ Profile validation passed")
        update_progress(0.10, "Profile validated")
    except Exception as e:
        logger.error(f"Profile validation error: {e}", exc_info=True)
        return None, f"[error] Profile validation error: {str(e)}", None
    
    # File collection
    try:
        file_collection_result = collect_file_info(profile_path, custom_template_path)
        if file_collection_result.get('status') == 'error':
            error_msg = file_collection_result.get('message', 'File collection failed')
            logger.error(f"File collection failed: {error_msg}")
            return None, f"[error] {error_msg}", None
        logger.info("✅ File collection completed")
        update_progress(0.15, "Profile & files validated")
    except Exception as e:
        logger.error(f"File collection error: {e}", exc_info=True)
        return None, f"[error] File collection error: {str(e)}", None
    
    # Template validation
    try:
        validate_template(custom_template_path)
        logger.info("✅ Template validation completed")
        update_progress(0.20, "Template validation completed")
    except Exception as e:
        logger.warning(f"Template validation error: {e}")
    
    # Privacy guard (before Crew execution)
    if enable_privacy:
        try:
            from resume_builder.deterministic_pipeline import run_privacy_guard
            privacy_result = run_privacy_guard(profile_path=profile_path, jd_text=jd_text)
            if privacy_result.get('high_risk'):
                logger.warning(f"⚠️ Privacy guard detected high-risk issues: {privacy_result.get('high_risk')}")
            logger.info("✅ Privacy guard completed")
        except Exception as e:
            logger.warning(f"Privacy guard error (continuing anyway): {e}")
    
    # Create crew instance with flags (task filtering happens in crew() method)
    try:
        team = ResumeTeam(
            fast_mode=fast_mode,
            enable_cover_letter=enable_cover_letter,
            enable_ats=enable_ats,
            enable_privacy=enable_privacy,
        )
    except Exception as e:
        logger.error(f"Failed to create ResumeTeam: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] Failed to initialize crew: {str(e)}", None
    
    # Prepare inputs for crew
    # Deterministic pipeline functions handle validation and mode detection
    # In fast mode, truncate JD and profile to reduce prompt size
    jd_for_crew = jd_text
    if fast_mode and len(jd_text) > 1024:
        # Truncate JD to first 1024 chars in fast mode (keep most important info)
        jd_for_crew = jd_text[:1024] + "\n\n[Truncated for fast mode - using first 1024 characters]"
        logger.info(f"[FAST MODE] Truncated JD from {len(jd_text)} to {len(jd_for_crew)} characters")
    
    inputs = {
        "job_description": jd_for_crew,
        "profile_path": str(profile_path),
        "template_path": str(template_path),
        "has_custom_template": custom_template_path is not None,
        "has_reference_pdfs": has_reference_pdfs,
        "reference_pdf_count": len(reference_pdf_paths) if has_reference_pdfs else 0,
        "debug": debug,  # Enable debug mode to produce pipeline_status_debug.json
        "enable_ats": enable_ats,  # Passed to agents for context (filtering already done in crew())
        "enable_privacy": enable_privacy,  # Passed to agents for context (filtering already done in crew())
        "enable_cover_letter": enable_cover_letter,  # Passed to agents for context (filtering already done in crew())
        "fast_mode": fast_mode  # Fast mode flag for optimization
    }
    
    if has_reference_pdfs:
        inputs["reference_pdf_paths"] = reference_pdf_paths
    
    logger.info(f"Pipeline configuration: ATS={enable_ats}, Privacy={enable_privacy}, CoverLetter={enable_cover_letter}, FastMode={fast_mode}")
    
    # Execute crew (agents output JSON, no LaTeX yet)
    # Task filtering is done in team.crew() BEFORE Crew construction
    update_progress(0.25, "Initializing AI agents...")
    
    # Track real wall-clock timing for crew execution
    import time
    crew_start_time = time.time()
    
    try:
        logger.info("Launching crew...")
        crew_instance = team.crew()
        
        # No post-creation filtering - all filtering happens in crew() method
        result = crew_instance.kickoff(inputs=inputs)
        crew_end_time = time.time()
        crew_duration = crew_end_time - crew_start_time
        logger.info(f"✅ Crew execution completed in {crew_duration:.1f}s ({crew_duration/60:.1f} min)")
        
        # Record real crew execution time to progress.json for timeline display
        try:
            from resume_builder.tools.progress_reporter import ProgressReporterTool
            progress_tool = ProgressReporterTool()
            progress_tool._run(
                progress=0.65,
                description="AI agents completed",
                task_name="crew_execution",
                task_duration_seconds=crew_duration
            )
        except Exception as e:
            logger.debug(f"Could not record crew execution time: {e}")
        
        update_progress(0.65, "AI agents completed. Preparing LaTeX...")
    except Exception as e:
        logger.error(f"❌ Crew execution failed: {e}", exc_info=True)
        update_progress(0.6, "Error during AI agent execution")
        return None, f"[error] Crew execution failed:\n{str(e)}\n\n{traceback.format_exc()}", None
    
    # All orchestration logic is now in the orchestrator agent
    # Python only checks pipeline_status.json and proceeds with LaTeX generation
    
    # Step 2: Generate LaTeX using Python builder (no agents involved)
    update_progress(0.75, "Validating AI output JSON...")
    try:
        logger.info("="*80)
        logger.info("Building LaTeX resume from JSON data...")
        logger.info("="*80)
        
        from resume_builder.latex_builder import build_resume_from_json_files
        
        # Load JSON outputs from agents
        # The orchestrator has already verified readiness, but we double-check physical file existence
        # as a safety measure before attempting LaTeX generation
        identity_json = OUTPUT_DIR / "user_profile.json"
        summary_json = OUTPUT_DIR / "summary.json"
        experience_json = OUTPUT_DIR / "selected_experiences.json"
        education_json = OUTPUT_DIR / "education.json"
        skills_json = OUTPUT_DIR / "selected_skills.json"
        projects_json = OUTPUT_DIR / "selected_projects.json"  # Optional - orchestrator may have skipped this
        header_json = OUTPUT_DIR / "header.json"  # Optional - tailored header with keywords
        rendered_tex = RENDERED_TEX
        
        # Verify required files exist (pipeline status should have caught this, but we verify physically)
        required_files = {
            "user_profile.json": identity_json,
            "summary.json": summary_json,
            "selected_experiences.json": experience_json,
            "selected_skills.json": skills_json,
        }
        
        # Education is optional - builder can handle empty list
        optional_files = {
            "education.json": education_json,
        }
        
        missing_files = []
        for name, file_path in required_files.items():
            if not file_path.exists():
                missing_files.append(name)
        
        # Fallback: Generate summary.json if missing (workaround for write_summary_task not executing)
        if "summary.json" in missing_files:
            logger.warning("summary.json is missing - generating fallback summary from selected experiences and skills")
            try:
                # Read selected experiences and skills to generate a basic summary
                exp_data = load_selected_experiences(experience_json)
                skills_data = load_selected_skills(skills_json)
                
                # Extract key information
                experiences = exp_data.get('selected_experiences', [])
                # Support both new format (skills) and old format (selected_skills)
                skills = skills_data.get('skills', skills_data.get('selected_skills', []))
                
                # Generate a simple summary
                if experiences:
                    first_exp = experiences[0]
                    # Support both new format (company) and old format (organization)
                    org = first_exp.get('company', first_exp.get('organization', ''))
                    title = first_exp.get('title', '')
                    summary_text = f"Experienced {title} with expertise in {', '.join(skills[:3]) if skills else 'software development'}. "
                    if len(experiences) > 1:
                        summary_text += f"Proven track record in {len(experiences)} key roles with focus on technical excellence and innovation."
                    else:
                        summary_text += "Demonstrated ability to deliver high-quality solutions in research and development environments."
                else:
                    summary_text = f"Skilled professional with expertise in {', '.join(skills[:5]) if skills else 'software development'}."
                
                # Create summary.json
                summary_data = {
                    "status": "success",
                    "message": "Fallback summary generated (write_summary_task did not execute)",
                    "summary": summary_text
                }
                summary_json.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                logger.info(f"✅ Generated fallback summary.json: {summary_text[:100]}...")
                missing_files.remove("summary.json")
            except Exception as e:
                logger.error(f"Failed to generate fallback summary.json: {e}")
        
        if missing_files:
            error_msg = f"Required JSON files missing (pipeline status should have caught this): {', '.join(missing_files)}"
            logger.error(error_msg)
            return None, f"[error] {error_msg}", None
        
        # Log optional files status
        for name, file_path in optional_files.items():
            if not file_path.exists():
                logger.info(f"Optional file missing: {name} (will use empty data)")
        
        if projects_json.exists():
            logger.info("Optional file found: selected_projects.json")
        else:
            logger.info("Optional file not found: selected_projects.json (orchestrator may have skipped project selection)")
        
        if header_json.exists():
            logger.info("Optional file found: header.json")
        else:
            logger.info("Optional file not found: header.json (will use default header)")
        
        # Early validation: Check JSON file structure before LaTeX generation
        # This catches issues early and saves API calls
        logger.info("Validating JSON file structures...")
        validation_errors = []
        
        # Validate identity JSON (user_profile.json has different structure)
        try:
            with open(identity_json, 'r', encoding='utf-8') as f:
                identity_data = json.load(f)
                if 'identity' not in identity_data and not all(k in identity_data for k in ['first', 'last', 'email']):
                    # Check if it's a flat structure
                    if not isinstance(identity_data, dict):
                        validation_errors.append(f"user_profile.json: Expected dict, got {type(identity_data).__name__}")
        except json.JSONDecodeError as e:
            validation_errors.append(f"user_profile.json: Invalid JSON - {e}")
        except Exception as e:
            validation_errors.append(f"user_profile.json: Error reading file - {e}")
        
        # Validate required JSON files using helper functions
        summary_data = load_summary_block(summary_json)
        if summary_data.get("status") != "success" or "summary" not in summary_data:
            validation_errors.append(f"summary.json: {summary_data.get('message', 'Missing summary field')}")
        
        exp_data = load_selected_experiences(experience_json)
        if exp_data.get("status") != "success" or "selected_experiences" not in exp_data:
            validation_errors.append(f"selected_experiences.json: {exp_data.get('message', 'Missing selected_experiences field')}")
        elif not isinstance(exp_data.get("selected_experiences", []), list):
            validation_errors.append(f"selected_experiences.json: Expected list, got {type(exp_data.get('selected_experiences')).__name__}")
        
        skills_data = load_selected_skills(skills_json)
        # Check for new format (skills) or old format (selected_skills) for backward compatibility
        has_skills = "skills" in skills_data
        has_selected_skills = "selected_skills" in skills_data
        if skills_data.get("status") != "success" or (not has_skills and not has_selected_skills):
            validation_errors.append(f"selected_skills.json: {skills_data.get('message', 'Missing skills field')}")
        elif has_skills and not isinstance(skills_data.get("skills", []), list):
            validation_errors.append(f"selected_skills.json: Expected skills to be a list, got {type(skills_data.get('skills')).__name__}")
        elif has_selected_skills and not isinstance(skills_data.get("selected_skills", []), list):
            validation_errors.append(f"selected_skills.json: Expected selected_skills to be a list, got {type(skills_data.get('selected_skills')).__name__}")
        
        # Validate optional files if they exist
        if education_json.exists():
            edu_data = load_education_block(education_json)
            if edu_data.get("status") != "success" or "education" not in edu_data:
                validation_errors.append(f"education.json: {edu_data.get('message', 'Missing education field')}")
        
        if projects_json.exists():
            proj_data = load_selected_projects(projects_json)
            if proj_data.get("status") != "success" or "selected_projects" not in proj_data:
                validation_errors.append(f"selected_projects.json: {proj_data.get('message', 'Missing selected_projects field')}")
            # COMMENTED OUT: Post-processing replaced by project_summarizer LLM tool
            # The project_selector agent now uses project_summarizer tool during task execution
            # else:
            #     # Post-process projects to ensure bullets are properly summarized (safety net)
            #     projects = proj_data.get("selected_projects", [])
            #     summarized_projects = _summarize_project_bullets_if_needed(projects)
            #     if summarized_projects != projects:
            #         # Save summarized version back to file
            #         proj_data["selected_projects"] = summarized_projects
            #         original_msg = proj_data.get("message", "")
            #         proj_data["message"] = f"{original_msg} (Post-processed: bullets summarized for optimal length)".strip()
            #         with open(projects_json, 'w', encoding='utf-8') as f:
            #             json.dump(proj_data, f, indent=2, ensure_ascii=False)
            #         logger.info("✅ Post-processed project bullets to ensure concise length for 1-2 page resume")
        
        if header_json.exists():
            header_data = load_header_block(header_json)
            # Check for new format fields (target_title, name, email) or old format (title_line, contact_info)
            has_new_format = header_data.get("target_title") or header_data.get("name") or header_data.get("email")
            has_old_format = header_data.get("title_line") or header_data.get("contact_info")
            if header_data.get("status") != "success" or (not has_new_format and not has_old_format):
                validation_errors.append(f"header.json: {header_data.get('message', 'Missing target_title or name/email field')}")
        
        if validation_errors:
            error_msg = (
                f"JSON file validation failed before LaTeX generation:\n" +
                "\n".join(f"  - {err}" for err in validation_errors) +
                "\n\nThis prevents wasted API calls. Please check the JSON file structures."
            )
            logger.error("="*80)
            logger.error("❌ JSON VALIDATION FAILED")
            logger.error("="*80)
            logger.error(error_msg)
            if progress_callback:
                progress_callback(0.7, desc="JSON validation failed")
            return None, f"[error] {error_msg}", None
        
        logger.info("✅ JSON file structures validated successfully")
        
        # Handle optional education file - create temp file with empty education if missing
        if not education_json.exists():
            logger.info("education.json not found, using empty education list")
            temp_edu = OUTPUT_DIR / "education_temp.json"
            temp_edu.write_text(json.dumps({"status": "success", "message": "No education data", "education": []}), encoding='utf-8')
            education_json = temp_edu
        
        # Enforce length budget before LaTeX generation
        length_trimming_metadata = None
        try:
            from resume_builder.length_budget import enforce_length_budget_on_json_files, format_trimming_summary
            
            if enforce_2_page_limit:
                logger.info("="*80)
                logger.info("Enforcing length budget (target: ≤2 pages)...")
                logger.info("="*80)
            else:
                logger.info("Length budget enforcement disabled (2-page limit not enforced)")
            
            length_trimming_metadata = enforce_length_budget_on_json_files(
                summary_path=summary_json,
                experience_path=experience_json,
                skills_path=skills_json,
                projects_path=projects_json if projects_json.exists() else None,
                education_path=education_json if education_json.exists() else None,
                max_pages=2 if enforce_2_page_limit else 999  # Large limit if disabled
            )
            
            trimming_summary = format_trimming_summary(length_trimming_metadata)
            estimated_pages_after = length_trimming_metadata.get("estimated_pages_after", 0)
            
            # If still over 2 pages, run iterative page reduction (only if enforcement is enabled)
            removal_suggestions = None
            if enforce_2_page_limit and estimated_pages_after > 2.0:
                logger.warning(f"⚠️ Resume still exceeds 2-page budget: {estimated_pages_after:.1f} pages")
                logger.info("Starting iterative page reduction to remove least important content...")
                logger.info(f"Condition check: enforce_2_page_limit={enforce_2_page_limit}, estimated_pages_after={estimated_pages_after:.2f}")
                try:
                    from resume_builder.iterative_page_reducer import iteratively_reduce_pages
                    
                    reduction_log = iteratively_reduce_pages(
                        summary_path=summary_json,
                        experience_path=experience_json,
                        skills_path=skills_json,
                        projects_path=projects_json if projects_json.exists() else None,
                        education_path=education_json if education_json.exists() else None,
                        jd_path=OUTPUT_DIR / "parsed_jd.json",
                        target_pages=2.0,
                        max_iterations=5
                    )
                    
                    # Save reduction log
                    reduction_log_path = OUTPUT_DIR / "page_reduction_log.json"
                    reduction_log_path.write_text(
                        json.dumps(reduction_log, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )
                    logger.info(f"Saved page reduction log to {reduction_log_path}")
                    
                    if reduction_log.get("target_met"):
                        logger.info(f"✅ Iterative reduction successful: {reduction_log.get('final_estimated_pages', 0):.1f} pages")
                        # Re-estimate after reduction
                        from resume_builder.length_budget import estimate_lines, TARGET_LINES_PER_PAGE
                        # Note: load_summary_block, load_selected_experiences, etc. are already imported at top of file
                        summary_data = load_summary_block(summary_json)
                        exp_data = load_selected_experiences(experience_json)
                        skills_data = load_selected_skills(skills_json)
                        projects = []
                        if projects_json.exists():
                            proj_data = load_selected_projects(projects_json)
                            projects = proj_data.get('selected_projects', [])
                        education = []
                        if education_json.exists():
                            edu_data = load_education_block(education_json)
                            education = edu_data.get('education', [])
                        estimated_lines = estimate_lines(
                            summary_data.get('summary', ''),
                            exp_data.get('selected_experiences', []),
                            projects,
                            skills_data.get('skills', skills_data.get('selected_skills', [])),
                            education
                        )
                        estimated_pages_after = estimated_lines / TARGET_LINES_PER_PAGE
                        length_trimming_metadata["estimated_pages_after"] = estimated_pages_after
                        length_trimming_metadata["estimated_lines_after"] = estimated_lines
                    else:
                        logger.warning(f"⚠️ Iterative reduction incomplete: {reduction_log.get('message', 'Unknown')}")
                        # Still generate removal suggestions for manual review
                        from resume_builder.tools.content_rank_analyzer import ContentRankAnalyzerTool
                        rank_analyzer = ContentRankAnalyzerTool()
                        suggestions_json = rank_analyzer._run(
                            experiences_path="selected_experiences.json",
                            skills_path="selected_skills.json",
                            summary_path="summary.json",
                            jd_path="parsed_jd.json",
                            projects_path="selected_projects.json" if projects_json.exists() else None,
                            education_path="education.json" if education_json.exists() else None,
                            estimated_pages=estimated_pages_after,
                            target_pages=2.0
                        )
                        removal_suggestions = json.loads(suggestions_json)
                        suggestions_path = OUTPUT_DIR / "removal_suggestions.json"
                        suggestions_path.write_text(suggestions_json, encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Failed to run iterative page reduction: {e}", exc_info=True)
                    # Fallback: generate removal suggestions
                    try:
                        from resume_builder.tools.content_rank_analyzer import ContentRankAnalyzerTool
                        rank_analyzer = ContentRankAnalyzerTool()
                        suggestions_json = rank_analyzer._run(
                            experiences_path="selected_experiences.json",
                            skills_path="selected_skills.json",
                            summary_path="summary.json",
                            jd_path="parsed_jd.json",
                            projects_path="selected_projects.json" if projects_json.exists() else None,
                            education_path="education.json" if education_json.exists() else None,
                            estimated_pages=estimated_pages_after,
                            target_pages=2.0
                        )
                        removal_suggestions = json.loads(suggestions_json)
                        suggestions_path = OUTPUT_DIR / "removal_suggestions.json"
                        suggestions_path.write_text(suggestions_json, encoding='utf-8')
                    except Exception as e2:
                        logger.warning(f"Failed to generate removal suggestions: {e2}")
            
            if trimming_summary:
                logger.info(f"Length guard applied:\n{trimming_summary}")
                # Save trimming metadata for UI display
                try:
                    trimming_metadata_path = OUTPUT_DIR / "length_trimming_metadata.json"
                    metadata_dict = {
                        "status": "success",
                        "summary": trimming_summary,
                        "metadata": length_trimming_metadata
                    }
                    if removal_suggestions:
                        metadata_dict["removal_suggestions"] = removal_suggestions
                    trimming_metadata_path.write_text(
                        json.dumps(metadata_dict, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )
                except Exception as e:
                    logger.debug(f"Failed to save trimming metadata: {e}")
            else:
                logger.info("Content already within length budget, no trimming needed")
        except Exception as e:
            logger.warning(f"Length budget enforcement failed (continuing anyway): {e}")
            # Don't break the pipeline if length budget fails
        
        # Build LaTeX using Python
        latex_content = build_resume_from_json_files(
            identity_path=identity_json,
            summary_path=summary_json,
            experience_path=experience_json,
            education_path=education_json,
            skills_path=skills_json,
            projects_path=projects_json if projects_json.exists() else None,
            header_path=header_json if header_json.exists() else None,
            template_path=template_path,
            output_path=rendered_tex,
            page_budget_pages=2 if enforce_2_page_limit else 999  # Large limit if disabled
        )
        
        logger.info(f"✅ LaTeX generated: {rendered_tex}")
        update_progress(0.85, "Resume LaTeX generated")
        
        # Clean up temp education file if we created one
        temp_edu = OUTPUT_DIR / "education_block_temp.json"
        if temp_edu.exists():
            try:
                temp_edu.unlink()
                logger.debug(f"Cleaned up temp education file: {temp_edu}")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"LaTeX generation failed: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] LaTeX generation failed:\n{str(e)}\n\n{traceback.format_exc()}", None
    
    # Step 2.5: Repair LaTeX file (apply comprehensive fixes)
    try:
        logger.info("="*80)
        logger.info("Repairing LaTeX file (applying comprehensive fixes)...")
        logger.info("="*80)
        
        from resume_builder.latex_builder import repair_latex_file
        
        # Read the generated LaTeX
        original_latex = rendered_tex.read_text(encoding='utf-8')
        
        # Only run repair_latex_file() on imported/legacy TeX files, not on resumecv output
        # repair_latex_file() converts to article class, which would break resumecv files
        is_resumecv = bool(re.search(r'\\documentclass[^\n]*\{resumecv\}', original_latex))
        
        if is_resumecv:
            logger.info("Skipping repair_latex_file() for resumecv class (builder output is already correct)")
            # But still apply comprehensive backslash fixes for resumecv files (in case of corruption)
            repaired_latex = original_latex
            # Fix common missing backslash issues that can occur even in resumecv files
            fixes_applied = False
            
            # Comprehensive backslash restoration (order matters - fix most specific first)
            # Fix corrupted compact layout commands (missing backslashes)
            if r'ewif\ifcompactresume' in repaired_latex or r'ewif\\ifcompactresume' in repaired_latex:
                repaired_latex = re.sub(r'ewif\s*\\?ifcompactresume', r'\\newif\\ifcompactresume', repaired_latex)
                fixes_applied = True
                logger.debug("Fixed: ewif\\ifcompactresume -> \\newif\\ifcompactresume")
            
            if r'ewcommand{\compactresumelayout}' in repaired_latex or r'ewcommand{\\compactresumelayout}' in repaired_latex:
                repaired_latex = re.sub(r'ewcommand\s*\{\s*\\?compactresumelayout\s*\}', r'\\newcommand{\\compactresumelayout}', repaired_latex)
                fixes_applied = True
                logger.debug("Fixed: ewcommand{\\compactresumelayout} -> \\newcommand{\\compactresumelayout}")
            
            # Fix double backslashes in compactresumelayout call and remove duplicates
            if r'\begin{document}' in repaired_latex:
                doc_start = repaired_latex.find(r'\begin{document}')
                document_body = repaired_latex[doc_start:]
                original_body = document_body
                
                # Fix double backslash (but not in \newcommand definitions)
                fixed_body = re.sub(r'(?<!\\newcommand[^}]*)\\\\compactresumelayout', r'\\compactresumelayout', document_body)
                
                # Remove duplicate compactresumelayout calls (keep only first one after \begin{document})
                # Find all occurrences after \begin{document}
                compact_calls = list(re.finditer(r'(?<!\\newcommand[^}]*)\\compactresumelayout', fixed_body))
                if len(compact_calls) > 1:
                    # Keep first occurrence, remove others
                    first_pos = compact_calls[0].start()
                    for match in compact_calls[1:]:
                        # Remove the duplicate call (including newline if present)
                        pos = match.start()
                        # Remove the call and any preceding newline
                        if pos > 0 and fixed_body[pos-1] == '\n':
                            fixed_body = fixed_body[:pos-1] + fixed_body[match.end():]
                        else:
                            fixed_body = fixed_body[:pos] + fixed_body[match.end():]
                    fixes_applied = True
                    logger.debug(f"Removed {len(compact_calls)-1} duplicate \\compactresumelayout call(s)")
                
                if fixed_body != original_body:
                    repaired_latex = repaired_latex[:doc_start] + fixed_body
                    if r'\\compactresumelayout' in original_body:
                        fixes_applied = True
                        logger.debug("Fixed: \\\\compactresumelayout -> \\compactresumelayout")
            
            # Other backslash fixes
            backslash_fixes = [
                (r'(?<!\\)(?<![a-zA-Z])ewcommand\*', r'\\newcommand*', 'ewcommand*'),
                (r'(?<!\\)(?<![a-zA-Z])ewcommand\b', r'\\newcommand', 'ewcommand'),
                (r'(?<!\\)(?<![a-zA-Z])opagenumbers\b', r'\\nopagenumbers', 'opagenumbers'),
                (r'(?<!\\)(?<![a-zA-Z])ame\s*\{', r'\\name{', 'ame{'),
                (r'(?<!\\)(?<![a-zA-Z])oindent\b', r'\\noindent', 'oindent'),
            ]
            
            for pattern, replacement, description in backslash_fixes:
                if re.search(pattern, repaired_latex):
                    repaired_latex = re.sub(pattern, replacement, repaired_latex)
                    fixes_applied = True
                    logger.debug(f"Fixed backslash corruption: {description}")
            
            # After fixing backslashes, ensure \compactresumelayout is defined and called
            # Check if command is defined (after fixing corruption)
            has_compact_command = (
                r'\newcommand{\compactresumelayout}' in repaired_latex or
                r'\newcommand*{\compactresumelayout}' in repaired_latex or
                r'\def\compactresumelayout' in repaired_latex
            )
            
            # If command is not defined, inject it (needed for 2-page limit enforcement)
            if not has_compact_command and r'\begin{document}' in repaired_latex:
                logger.warning("\\compactresumelayout command not found, injecting definition...")
                doc_start = repaired_latex.find(r'\begin{document}')
                preamble = repaired_latex[:doc_start]
                document_body = repaired_latex[doc_start:]
                
                # Check if enumitem is loaded (required for \setlist)
                has_enumitem = r'\usepackage{enumitem}' in repaired_latex or r'\usepackage[enumitem]' in repaired_latex
                
                # Inject compact layout definition
                compact_definition = "\n% Compact layout toggle for page budget enforcement (auto-injected)\n"
                compact_definition += "\\newif\\ifcompactresume\n"
                compact_definition += "\\compactresumefalse\n"
                
                if not has_enumitem:
                    compact_definition += "\\usepackage{enumitem}\n"
                
                compact_definition += "\n"
                compact_definition += "\\newcommand{\\compactresumelayout}{%\n"
                compact_definition += "  \\compactresumetrue\n"
                compact_definition += "  \\setlength{\\itemsep}{0.2em}\n"
                compact_definition += "  \\setlength{\\parskip}{0.15em}\n"
                compact_definition += "  \\setlist[itemize]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_definition += "  \\setlist[enumerate]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_definition += "}\n"
                
                repaired_latex = preamble + compact_definition + document_body
                fixes_applied = True
                logger.info("Injected \\compactresumelayout definition into resumecv file")
            
            # Ensure the command is called in document body
            if r'\begin{document}' in repaired_latex:
                doc_start_pos = repaired_latex.find(r'\begin{document}')
                document_body = repaired_latex[doc_start_pos:]
                # Check if call exists (not as part of \newcommand definition)
                compact_pos = document_body.find(r'\compactresumelayout')
                if compact_pos >= 0:
                    context_before = document_body[max(0, compact_pos-30):compact_pos]
                    has_compact_call = r'\newcommand' not in context_before and r'\newcommand*' not in context_before
                else:
                    has_compact_call = False
                
                if not has_compact_call:
                    # Inject call after \begin{document}
                    repaired_latex = repaired_latex.replace(
                        r'\begin{document}',
                        r'\begin{document}' + '\n\\compactresumelayout',
                        1
                    )
                    fixes_applied = True
                    logger.info("Injected \\compactresumelayout call after \\begin{document}")
            
            if fixes_applied:
                logger.warning("Applied backslash fixes and/or compact layout injection to resumecv file")
        else:
            # Apply repairs (for imported/legacy files that need conversion)
            repaired_latex = repair_latex_file(original_latex)
        
        # Write repaired version back
        rendered_tex.write_text(repaired_latex, encoding='utf-8')
        
        # Verify \compactresumelayout is defined (critical check)
        final_check = rendered_tex.read_text(encoding='utf-8')
        has_compact_def = (
            r'\newcommand{\compactresumelayout}' in final_check or
            r'\newcommand*{\compactresumelayout}' in final_check or
            r'\def\compactresumelayout' in final_check
        )
        has_compact_call = r'\compactresumelayout' in final_check and r'\newcommand' not in final_check[max(0, final_check.find(r'\compactresumelayout')-30):final_check.find(r'\compactresumelayout')]
        
        if not has_compact_def:
            logger.error("CRITICAL: \\compactresumelayout definition missing after repair! Attempting emergency injection...")
            # Emergency injection
            if r'\begin{document}' in final_check:
                doc_start = final_check.find(r'\begin{document}')
                preamble = final_check[:doc_start]
                document_body = final_check[doc_start:]
                has_enumitem = r'\usepackage{enumitem}' in final_check
                compact_def = "\n% Emergency injection: Compact layout definition\n"
                compact_def += "\\newif\\ifcompactresume\n\\compactresumefalse\n"
                if not has_enumitem:
                    compact_def += "\\usepackage{enumitem}\n"
                compact_def += "\n\\newcommand{\\compactresumelayout}{%\n"
                compact_def += "  \\compactresumetrue\n"
                compact_def += "  \\setlength{\\itemsep}{0.2em}\n"
                compact_def += "  \\setlength{\\parskip}{0.15em}\n"
                compact_def += "  \\setlist[itemize]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_def += "  \\setlist[enumerate]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_def += "}\n"
                final_check = preamble + compact_def + document_body
                if not has_compact_call:
                    final_check = final_check.replace(r'\begin{document}', r'\begin{document}\n\\compactresumelayout', 1)
                rendered_tex.write_text(final_check, encoding='utf-8')
                logger.warning("Emergency injection of \\compactresumelayout completed")
            else:
                logger.error("CRITICAL: Cannot inject \\compactresumelayout - no \\begin{document} found!")
        else:
            logger.info(f"✅ Verified: \\compactresumelayout definition present")
            if not has_compact_call:
                logger.warning("\\compactresumelayout defined but not called - adding call...")
                final_check = final_check.replace(r'\begin{document}', r'\begin{document}\n\\compactresumelayout', 1)
                rendered_tex.write_text(final_check, encoding='utf-8')
        
        logger.info(f"✅ LaTeX repaired: {rendered_tex}")
        
    except Exception as e:
        logger.warning(f"LaTeX repair failed (continuing anyway): {e}")
        logger.warning(traceback.format_exc())
        # Don't fail the pipeline if repair fails - compilation might still work
    
    # Step 3: Compile LaTeX to PDF
    try:
        logger.info("="*80)
        logger.info("Compiling LaTeX to PDF...")
        logger.info("="*80)
        
        from resume_builder.tools.latex_compile import LatexCompileTool
        
        compiler = LatexCompileTool()
        compile_result = compiler._run(
            tex_path=str(rendered_tex),
            out_name="final_resume.pdf",
            workdir=".",
            engine="pdflatex"
        )
        
        # Check if compilation failed - if so, use latex_error_analyzer tool to analyze errors
        # SKIP error analysis in fast mode for speed
        if not compile_result.get("success", False):
            error_log = compile_result.get("log", "") or compile_result.get("error", "")
            if error_log:
                # Save error log to file
                error_log_path = OUTPUT_DIR / "latex_compile_error.log"
                try:
                    error_log_path.write_text(error_log, encoding='utf-8')
                    logger.info(f"Saved LaTeX compilation error log to {error_log_path}")
                    
                    # Skip LLM error analysis in fast mode - just save raw error
                    if fast_mode:
                        logger.info("[FAST MODE] Skipping LaTeX error analysis - saving raw error log only")
                        # Save minimal error info for UI
                        latex_errors_path = OUTPUT_DIR / "latex_errors.json"
                        try:
                            minimal_error = {
                                "status": "error",
                                "message": "LaTeX compilation failed (fast mode - no LLM analysis)",
                                "analysis": {
                                    "root_cause": "See compile log for details",
                                    "error_type": "CompilationError",
                                    "recommended_fix": "Check latex_compile_error.log for full error details"
                                }
                            }
                            latex_errors_path.write_text(json.dumps(minimal_error, indent=2), encoding='utf-8')
                        except Exception as e:
                            logger.warning(f"Failed to save minimal error info: {e}")
                    else:
                        # Use latex_error_analyzer tool to analyze the error (normal mode)
                        try:
                            from resume_builder.tools.latex_error_analyzer import LatexErrorAnalyzerTool
                            error_analyzer = LatexErrorAnalyzerTool()
                            
                            # Read LaTeX source for context
                            tex_content = None
                            if rendered_tex.exists():
                                try:
                                    tex_content = rendered_tex.read_text(encoding='utf-8')
                                except Exception:
                                    pass
                            
                            # Analyze errors
                            analysis_result = error_analyzer._run(
                                log_text=error_log,
                                tex_content=tex_content
                            )
                            
                            # Save analysis to latex_errors.json
                            latex_errors_path = OUTPUT_DIR / "latex_errors.json"
                            try:
                                latex_errors_path.write_text(analysis_result, encoding='utf-8')
                                logger.info(f"✅ LaTeX error analysis saved to {latex_errors_path}")
                            except Exception as e:
                                logger.warning(f"Failed to save error analysis: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to analyze LaTeX errors with LLM tool: {e}")
                except Exception as e:
                    logger.warning(f"Failed to save error log: {e}")
        
        logger.info(f"Compilation result: {compile_result}")
        
        # Check if PDF was created
        if FINAL_PDF.exists():
            pdf_size = FINAL_PDF.stat().st_size
            logger.info(f"✅ PDF generated successfully: {FINAL_PDF} ({pdf_size} bytes)")
            update_progress(0.95, "PDF generated successfully")
            
            # ATS rules audit (after successful PDF compile)
            if enable_ats:
                try:
                    from resume_builder.deterministic_pipeline import run_ats_rules_audit
                    ats_result = run_ats_rules_audit(tex_path=str(rendered_tex))
                    logger.info("✅ ATS rules audit completed")
                except Exception as e:
                    logger.warning(f"ATS rules audit error (continuing anyway): {e}")
            
            # Generate cover letter PDF if enabled and available
            cover_letter_pdf_path = None
            if enable_cover_letter:
                logger.info("Cover letter generation is ENABLED - checking for cover letter data...")
                # Check for refined cover letter first, fallback to regular
                cover_letter_refined_path = OUTPUT_DIR / "cover_letter_refined.json"
                cover_letter_path = OUTPUT_DIR / "cover_letter.json"
                
                cover_letter_data_to_use = None
                if cover_letter_refined_path.exists():
                    try:
                        cover_letter_refined_data = load_cover_letter(cover_letter_refined_path)
                        if cover_letter_refined_data.get("status") == "success" and cover_letter_refined_data.get("refined_cover_letter"):
                            logger.info("Using refined cover letter from cover_letter_refined.json")
                            # Convert refined format to standard format for PDF generation
                            cover_letter_data_to_use = {
                                "status": "success",
                                "cover_letter_md": cover_letter_refined_data.get("refined_cover_letter", ""),
                                "word_count": cover_letter_refined_data.get("word_count", 0)
                            }
                    except Exception as e:
                        logger.warning(f"Failed to load refined cover letter, using regular: {e}")
                
                if not cover_letter_data_to_use and cover_letter_path.exists():
                    try:
                        cover_letter_data = load_cover_letter(cover_letter_path)
                        # Check both 'ok' and 'status' fields (cover letter uses 'ok' for orchestrator validation)
                        if cover_letter_data.get("ok") is True or cover_letter_data.get("status") == "success":
                            cover_letter_data_to_use = cover_letter_data
                    except Exception as e:
                        logger.warning(f"Failed to load cover letter: {e}")
                
                if cover_letter_data_to_use:
                    word_count = cover_letter_data_to_use.get("word_count") or cover_letter_data_to_use.get("meta", {}).get("word_count", "unknown")
                    logger.info(f"📄 Cover letter available (word_count: {word_count})")
                    
                    # Generate cover letter PDF
                    try:
                        cover_letter_pdf_path = _generate_cover_letter_pdf(cover_letter_data_to_use, OUTPUT_DIR)
                        if cover_letter_pdf_path:
                            logger.info(f"✅ Cover letter PDF generated: {cover_letter_pdf_path}")
                    except Exception as e:
                        logger.warning(f"Failed to generate cover letter PDF: {e}")
                        cover_letter_pdf_path = None
                else:
                    logger.info("Cover letter data not found - skipping cover letter PDF generation")
            else:
                logger.info("Cover letter generation is DISABLED (UI checkbox unchecked) - skipping cover letter tasks and PDF generation")
            
            # Step 4: Verify actual PDF page count (CRITICAL for 2-page enforcement)
            actual_page_count = None
            if enforce_2_page_limit and FINAL_PDF.exists():
                try:
                    # Try to get actual page count from PDF
                    try:
                        from pypdf import PdfReader
                        with open(FINAL_PDF, 'rb') as f:
                            pdf_reader = PdfReader(f)
                            actual_page_count = len(pdf_reader.pages)
                            logger.info(f"📄 Actual PDF page count: {actual_page_count} pages")
                            
                            if actual_page_count > 2:
                                logger.warning(f"⚠️ CRITICAL: PDF has {actual_page_count} pages, exceeds 2-page limit!")
                                logger.warning("This indicates the page estimation was inaccurate or enforcement failed.")
                                logger.warning("Consider: 1) Check if compact layout was applied, 2) Verify iterative reduction ran, 3) Manual trimming may be needed")
                            elif actual_page_count == 2:
                                logger.info("✅ PDF is exactly 2 pages - within limit")
                            else:
                                logger.info(f"✅ PDF is {actual_page_count} page(s) - within limit")
                    except ImportError:
                        logger.debug("pypdf not available - cannot verify actual page count")
                    except Exception as e:
                        logger.debug(f"Could not read PDF page count: {e}")
                except Exception as e:
                    logger.debug(f"PDF page count verification failed: {e}")
            
            # Step 5: Quality check the PDF
            try:
                logger.info("="*80)
                logger.info("Checking PDF quality...")
                logger.info("="*80)
                if progress_callback:
                    progress_callback(0.97, desc="Checking PDF quality...")
                
                from resume_builder.tools.pdf_quality_checker import PdfQualityCheckerTool
                quality_checker = PdfQualityCheckerTool()
                quality_report = quality_checker._run(
                    pdf_path=str(FINAL_PDF),
                    check_text=True,
                    check_layout=True
                )
                logger.info("PDF Quality Check Report:\n" + quality_report)
                
                # Extract status from report
                if "❌ FAILED" in quality_report:
                    logger.warning("⚠️ PDF quality check found critical issues")
                elif "⚠️  WARNINGS" in quality_report:
                    logger.info("ℹ️ PDF quality check found warnings (non-critical)")
                else:
                    logger.info("✅ PDF quality check passed!")
            except Exception as e:
                logger.warning(f"PDF quality check failed (non-critical): {e}")
                quality_report = None
            
            # Build success message with warnings if any
            # Get mode from pipeline_status.json (orchestrator determines it)
            try:
                pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
                if pipeline_status_path.exists():
                    with open(pipeline_status_path, 'r', encoding='utf-8') as f:
                        pipeline_status_data = json.load(f)
                    if "pipeline_status.json" in pipeline_status_data:
                        mode = pipeline_status_data["pipeline_status.json"].get("mode", "standard")
                    else:
                        mode = pipeline_status_data.get("mode", "standard")
                else:
                    mode = "standard"
            except Exception:
                mode = "standard"
            
            success_msg = f"[success] Resume generated successfully!\n\nMode: {mode}\nOutput: {FINAL_PDF}\n"
            
            if has_reference_pdfs:
                success_msg += f"\n📄 {len(reference_pdf_paths)} reference PDF(s) analyzed for style insights\n"
            
            # Extract template warnings from template_validation.json if it exists
            template_warnings = []
            try:
                template_validation_path = OUTPUT_DIR / "template_validation.json"
                if template_validation_path.exists():
                    from resume_builder.utils import clean_json_content
                    with open(template_validation_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Clean markdown if present
                    cleaned_content = clean_json_content(content)
                    template_data = json.loads(cleaned_content)
                    
                    # Collect warnings from template validation
                    if template_data.get("status") == "warning":
                        if template_data.get("message"):
                            template_warnings.append(template_data["message"])
                    if template_data.get("critical_missing"):
                        template_warnings.append(f"Missing critical packages: {', '.join(template_data['critical_missing'])}")
                    if template_data.get("missing_packages"):
                        missing = [pkg for pkg in template_data["missing_packages"] if pkg not in (template_data.get("critical_missing") or [])]
                        if missing:
                            template_warnings.append(f"Missing packages: {', '.join(missing)}")
                    if template_data.get("microtype_warning"):
                        template_warnings.append("Microtype detected with resumecv/moderncv - may cause expansion errors")
                    if template_data.get("recommendations"):
                        template_warnings.append(template_data["recommendations"])
            except Exception as e:
                logger.debug(f"Could not read template validation warnings: {e}")
            
            if template_warnings:
                success_msg += "\n⚠️ TEMPLATE WARNINGS:\n" + "\n".join(f"  • {w}" for w in template_warnings)
                success_msg += "\n\nThe resume was generated but may have compilation issues in other LaTeX environments."
            
            if quality_report and ("❌ FAILED" in quality_report or "⚠️  WARNINGS" in quality_report):
                success_msg += "\n\n📋 PDF QUALITY CHECK:\n"
                # Add summary from quality report
                lines = quality_report.split('\n')
                summary_start = None
                for i, line in enumerate(lines):
                    if "SUMMARY" in line:
                        summary_start = i
                        break
                if summary_start:
                    success_msg += '\n'.join(lines[summary_start:summary_start+10]) + "\n"
                else:
                    success_msg += "See full report in logs.\n"
            
            # Return absolute path to PDF and cover letter PDF
            pdf_absolute_path = str(FINAL_PDF.resolve())
            cover_letter_pdf_absolute = None
            if cover_letter_pdf_path:
                try:
                    cover_letter_pdf_path_obj = Path(cover_letter_pdf_path)
                    if cover_letter_pdf_path_obj.exists():
                        cover_letter_pdf_absolute = str(cover_letter_pdf_path_obj.resolve())
                except Exception as e:
                    logger.debug(f"Could not resolve cover letter PDF path: {e}")
            
            update_progress(1.0, "Pipeline completed")
            return pdf_absolute_path, success_msg, cover_letter_pdf_absolute
        else:
            logger.error("Compilation finished but no PDF was found")
            return None, f"[error] PDF compilation failed. Check compile.log for details.\n\nCompiler output: {compile_result}", None
    
    except Exception as e:
        logger.error(f"PDF compilation failed: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] PDF compilation failed:\n{str(e)}\n\n{traceback.format_exc()}", None


def run_template_matching(
    reference_pdf_path: str,
    generated_pdf_path: str,
    template_tex_path: Optional[str] = None,
    fast_mode: bool = False,
) -> Dict[str, Any]:
    """
    Run the fix_template_to_match_reference_task using the template_fixer agent.

    Args:
        reference_pdf_path: Path to the canonical 'good' resume PDF.
        generated_pdf_path: Path to the currently generated resume PDF.
        template_tex_path: Path to the LaTeX template to modify (optional).
                           If None, defaults to output/generated/rendered_resume.tex.
        fast_mode: If True, use faster/cheaper model and reduced iterations.

    Returns:
        A dict with 'ok' (bool), 'message' (str), and 'result' (CrewAI result dict).
    """
    from crewai import Process, Task, Crew
    
    logger = get_logger()
    
    # Normalize paths early so the agent gets clean, absolute paths
    reference_pdf = Path(reference_pdf_path).resolve()
    generated_pdf = Path(generated_pdf_path).resolve()
    
    if not reference_pdf.exists():
        return {
            "ok": False,
            "message": f"Reference PDF not found: {reference_pdf}",
            "result": None
        }
    if not generated_pdf.exists():
        return {
            "ok": False,
            "message": f"Generated PDF not found: {generated_pdf}",
            "result": None
        }
    
    # Default template path if not provided
    if template_tex_path is None:
        template_tex_path = str(RENDERED_TEX)
    template_tex = Path(template_tex_path).resolve()
    
    if not template_tex.exists():
        logger.warning(f"Template not found at {template_tex}, agent will need to locate it")
    
    logger.info("="*80)
    logger.info("Starting template matching task")
    logger.info(f"Reference PDF: {reference_pdf}")
    logger.info(f"Generated PDF: {generated_pdf}")
    logger.info(f"Template: {template_tex}")
    logger.info(f"Fast mode: {fast_mode}")
    logger.info("="*80)
    
    try:
        # Template matching doesn't need cover letter/ATS/privacy - use defaults
        team = ResumeTeam(
            fast_mode=fast_mode,
            enable_cover_letter=False,  # Not needed for template matching
            enable_ats=False,  # Not needed for template matching
            enable_privacy=False,  # Not needed for template matching
        )
    except Exception as e:
        logger.error(f"Failed to create ResumeTeam: {e}")
        logger.error(traceback.format_exc())
        return {
            "ok": False,
            "message": f"Failed to create ResumeTeam: {e}",
            "result": None
        }
    
    # Create a crew with just the template matching task
    # We need to manually create the task since it's not in the default crew
    template_fixer_agent = team.template_fixer()
    
    # Get task config from YAML
    task_config = team.tasks_config.get("fix_template_to_match_reference_task", {})
    if not task_config:
        raise ValueError("fix_template_to_match_reference_task not found in tasks.yaml")
    
    # Create task with inputs
    template_task = Task(
        description=task_config.get("description", "").format(
            reference_pdf_path=str(reference_pdf),
            generated_pdf_path=str(generated_pdf),
            template_tex_path=str(template_tex)
        ),
        agent=template_fixer_agent,
        expected_output=task_config.get("expected_output", ""),
    )
    
    # Read verbose and tracing flags (consistent with main pipeline)
    enable_tracing = os.getenv("CREWAI_TRACING", "false").lower() in ("true", "1", "yes")
    verbose_mode = os.getenv("CREWAI_VERBOSE", "false").lower() in ("true", "1", "yes")
    
    # Import inspect for checking Crew constructor parameters
    import inspect
    
    # Apply fast mode optimizations if enabled
    crew_kwargs = {
        "process": Process.sequential,
        "verbose": verbose_mode,
    }
    
    # Check Crew constructor signature once
    crew_sig = inspect.signature(Crew.__init__)
    
    # Add fast mode settings if enabled
    if fast_mode:
        if "max_iter" in crew_sig.parameters:
            crew_kwargs["max_iter"] = 2
        if "max_execution_time" in crew_sig.parameters:
            crew_kwargs["max_execution_time"] = 600  # 10 minutes
        logger.info("[FAST MODE] Template matching: max_iter=2, max_execution_time=600s")
    
    # Add tracing if enabled
    if enable_tracing and "tracing" in crew_sig.parameters:
        crew_kwargs["tracing"] = True
    
    # Create minimal crew with just this task
    crew = Crew(
        agents=[template_fixer_agent],
        tasks=[template_task],
        **crew_kwargs
    )
    
    # Execute the task
    logger.info("Executing template matching task...")
    try:
        result = crew.kickoff()
        logger.info("Template matching task completed successfully")
        return {
            "ok": True,
            "message": "Template matching completed successfully",
            "result": result
        }
    except Exception as e:
        logger.error(f"Template matching task failed: {e}")
        logger.error(traceback.format_exc())
        return {
            "ok": False,
            "message": f"Template matching failed: {e}",
            "result": None
        }

