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
import threading
import time as time_module
import traceback
from pathlib import Path
from datetime import datetime
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
    create_compact_profile_view,
    compute_pipeline_status,
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
        website = identity.get('website', '')
        
        # Build header
        name = f"{first_name} {last_name}".strip()
        contact_lines = []
        if email:
            contact_lines.append(email)
        if phone:
            contact_lines.append(phone)
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
    fast_mode: bool = True  # Default to fast mode for cost/speed optimization
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
    logger.info(f"Starting resume generation pipeline at {datetime.now()}")
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
    
    if progress_callback:
        progress_callback(0.05, desc="Running preflight checks...")
    
    # Preflight
    try:
        preflight_result = run_preflight()
        if not preflight_result.get('ok'):
            error_msg = preflight_result.get('error', 'Preflight check failed')
            logger.error(f"Preflight failed: {error_msg}")
            return None, f"[error] Preflight check failed: {error_msg}", None
        logger.info("✅ Preflight checks passed")
    except Exception as e:
        logger.error(f"Preflight error: {e}", exc_info=True)
        return None, f"[error] Preflight check error: {str(e)}", None
    
    if progress_callback:
        progress_callback(0.1, desc="Validating profile...")
    
    # Profile validation
    try:
        validation_result = validate_profile(profile_path)
        if not validation_result.get('ok'):
            error_msg = validation_result.get('message', 'Profile validation failed')
            logger.error(f"Profile validation failed: {error_msg}")
            return None, f"[error] {error_msg}", None
        logger.info("✅ Profile validation passed")
    except Exception as e:
        logger.error(f"Profile validation error: {e}", exc_info=True)
        return None, f"[error] Profile validation error: {str(e)}", None
    
    if progress_callback:
        progress_callback(0.12, desc="Collecting file information...")
    
    # File collection
    try:
        file_collection_result = collect_file_info(profile_path, custom_template_path)
        if file_collection_result.get('status') == 'error':
            error_msg = file_collection_result.get('message', 'File collection failed')
            logger.error(f"File collection failed: {error_msg}")
            return None, f"[error] {error_msg}", None
        logger.info("✅ File collection completed")
    except Exception as e:
        logger.error(f"File collection error: {e}", exc_info=True)
        return None, f"[error] File collection error: {str(e)}", None
    
    # Template validation
    try:
        validate_template(custom_template_path)
        logger.info("✅ Template validation completed")
    except Exception as e:
        logger.warning(f"Template validation error: {e}")
    
    # Create compact profile view for LLM tasks
    try:
        create_compact_profile_view(profile_path)
        logger.info("✅ Compact profile view created")
    except Exception as e:
        logger.warning(f"Could not create compact profile view: {e}")
    
    # Create crew instance
    try:
        team = ResumeTeam(fast_mode=fast_mode)
    except Exception as e:
        logger.error(f"Failed to create ResumeTeam: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] Failed to initialize crew: {str(e)}", None
    
    # Prepare inputs for crew
    # Deterministic pipeline functions handle validation and mode detection
    inputs = {
        "job_description": jd_text,
        "profile_path": str(profile_path),
        "template_path": str(template_path),
        "has_custom_template": custom_template_path is not None,
        "has_reference_pdfs": has_reference_pdfs,
        "reference_pdf_count": len(reference_pdf_paths) if has_reference_pdfs else 0,
        "debug": debug,  # Enable debug mode to produce pipeline_status_debug.json
        "enable_ats": enable_ats,  # Control ATS check task execution
        "enable_privacy": enable_privacy,  # Control privacy validation task execution
        "fast_mode": fast_mode  # Fast mode flag for optimization
    }
    
    if has_reference_pdfs:
        inputs["reference_pdf_paths"] = reference_pdf_paths
    
    logger.info(f"Pipeline configuration: ATS={enable_ats}, Privacy={enable_privacy}, FastMode={fast_mode}")
    
    # Execute crew (agents output JSON, no LaTeX yet)
    try:
        logger.info("Launching crew...")
        
        # Clear any existing progress file
        progress_file = OUTPUT_DIR / "progress.json"
        if progress_file.exists():
            progress_file.unlink()
        
        # Start progress monitoring thread if callback is provided
        progress_monitor_active = threading.Event()
        progress_monitor_active.set()
        
        def monitor_progress():
            """Monitor progress file and update callback with time-based steady growth."""
            # Time-based progress: grow steadily from 20% to 60% over ~7 minutes (420 seconds)
            CREW_EXECUTION_TIME = 420  # 7 minutes in seconds
            CREW_START_PROGRESS = 0.2  # 20%
            CREW_END_PROGRESS = 0.6    # 60%
            CREW_PROGRESS_RANGE = CREW_END_PROGRESS - CREW_START_PROGRESS  # 0.4 (40%)
            
            start_time = datetime.now()
            last_progress = CREW_START_PROGRESS
            agent_reported_progress = CREW_START_PROGRESS
            last_description = "Initializing AI agents..."
            
            if progress_callback:
                progress_callback(CREW_START_PROGRESS, desc=last_description)
            
            while progress_monitor_active.is_set():
                try:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    
                    # Calculate time-based progress (grows steadily)
                    if elapsed < CREW_EXECUTION_TIME:
                        time_based_progress = CREW_START_PROGRESS + (elapsed / CREW_EXECUTION_TIME) * CREW_PROGRESS_RANGE
                    else:
                        time_based_progress = CREW_END_PROGRESS
                    
                    # Also check agent-reported progress
                    if progress_file.exists():
                        try:
                            with open(progress_file, 'r', encoding='utf-8') as f:
                                progress_data = json.load(f)
                                agent_reported = float(progress_data.get("progress", CREW_START_PROGRESS))
                                description = progress_data.get("description", "Processing...")
                                
                                # Only update agent progress if it increased
                                if agent_reported > agent_reported_progress:
                                    agent_reported_progress = agent_reported
                                    last_description = description
                        except Exception:
                            pass  # Ignore errors reading progress file
                    
                    # Use the higher of time-based or agent-reported progress
                    # This ensures steady growth but respects agent milestones
                    target_progress = max(time_based_progress, agent_reported_progress)
                    
                    # Smooth interpolation towards target
                    if last_progress < target_progress:
                        # Increment by small steps for smooth animation
                        step_size = 0.005  # 0.5% increments for smoother animation
                        current_progress = min(last_progress + step_size, target_progress)
                        if progress_callback:
                            progress_callback(current_progress, desc=last_description)
                        last_progress = current_progress
                    elif last_progress > target_progress:
                        # Don't go backwards, but allow small corrections
                        if last_progress - target_progress > 0.01:
                            current_progress = max(target_progress, last_progress - step_size)
                            if progress_callback:
                                progress_callback(current_progress, desc=last_description)
                            last_progress = current_progress
                    
                except Exception:
                    pass  # Ignore errors in progress monitoring
                
                time_module.sleep(0.1)  # Check every 100ms for smoother updates
        
        # Start progress monitor
        monitor_thread = None
        if progress_callback:
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()
        
        try:
            crew_start_time = time_module.time()
            
            crew_instance = team.crew()
            
            # Filter tasks based on conditional flags
            if not enable_ats or not enable_privacy:
                original_tasks = list(crew_instance.tasks)
                filtered_tasks = []
                for task in original_tasks:
                    # Check if this is ATS or Privacy task
                    task_desc = str(getattr(task, 'description', '')).lower()
                    task_key = getattr(task, '_key', None)
                    
                    should_include = True
                    if not enable_ats:
                        if task_key == 'ats_check_task' or 'ats compatibility' in task_desc or 'ats_check' in task_desc:
                            should_include = False
                            logger.info(f"⏭️ Skipping ATS check task (disabled)")
                    if not enable_privacy:
                        if task_key == 'privacy_validation_task' or 'privacy' in task_desc and 'validation' in task_desc:
                            should_include = False
                            logger.info(f"⏭️ Skipping Privacy validation task (disabled)")
                    
                    if should_include:
                        filtered_tasks.append(task)
                
                # Update crew tasks (CrewAI allows this)
                crew_instance.tasks = filtered_tasks
                logger.info(f"Filtered tasks: {len(original_tasks)} → {len(filtered_tasks)} (ATS={enable_ats}, Privacy={enable_privacy})")
            
            # Note: Fast mode optimizations are applied in crew.py when creating the Crew
            # max_iter and max_execution_time are set during Crew creation, not after
            if fast_mode:
                logger.info("[FAST MODE] Fast mode enabled - optimizations applied in crew creation")
            
            # Add timing wrapper for telemetry
            logger.info("[TIMING] Starting crew execution...")
            logger.info(f"[TIMING] Configuration: fast_mode={fast_mode}, enable_ats={enable_ats}, enable_privacy={enable_privacy}")
            result = crew_instance.kickoff(inputs=inputs)
            crew_end_time = time_module.time()
            crew_duration = crew_end_time - crew_start_time
            logger.info(f"[TIMING] Crew execution completed in {crew_duration:.2f}s ({crew_duration/60:.2f} min)")
            
            # Save timing information to file for analysis
            try:
                timing_file = OUTPUT_DIR / "timings.json"
                timing_data = {
                    "crew_duration_seconds": crew_duration,
                    "crew_duration_minutes": crew_duration / 60,
                    "fast_mode": fast_mode,
                    "enable_ats": enable_ats,
                    "enable_privacy": enable_privacy,
                    "timestamp": datetime.now().isoformat(),
                    "tasks_count": len(crew_instance.tasks) if hasattr(crew_instance, 'tasks') else None
                }
                with open(timing_file, 'w', encoding='utf-8') as f:
                    json.dump(timing_data, f, indent=2)
                logger.info(f"[TIMING] Saved timing data to {timing_file}")
            except Exception as e:
                logger.warning(f"[TIMING] Could not save timing data: {e}")
            logger.info(f"Crew execution completed")
            logger.info(f"Result type: {type(result)}")
            
            # Capture detailed execution information for debugging
            execution_info = {
                "crew_completed": True,
                "result_type": str(type(result)),
                "result_str": str(result)[:500] if result else None,  # First 500 chars
            }
            
            # Try to extract task execution details from CrewAI result
            try:
                # CrewAI result may have tasks_completed, tasks_failed, etc.
                if hasattr(result, 'tasks_completed'):
                    execution_info["tasks_completed"] = [str(t) for t in result.tasks_completed] if result.tasks_completed else []
                    logger.info(f"Tasks completed: {len(execution_info.get('tasks_completed', []))}")
                if hasattr(result, 'tasks_failed'):
                    execution_info["tasks_failed"] = [str(t) for t in result.tasks_failed] if result.tasks_failed else []
                    if execution_info["tasks_failed"]:
                        logger.warning(f"Tasks failed: {execution_info['tasks_failed']}")
                if hasattr(result, 'tasks'):
                    execution_info["all_tasks"] = [str(t) for t in result.tasks] if result.tasks else []
                    logger.info(f"Total tasks in result: {len(execution_info.get('all_tasks', []))}")
                if hasattr(result, 'raw'):
                    execution_info["raw_output"] = str(result.raw)[:1000] if result.raw else None
                
                # Check if write_summary_task was executed
                all_tasks_str = ' '.join(execution_info.get("all_tasks", []))
                tasks_completed_str = ' '.join(execution_info.get("tasks_completed", []))
                if 'write_summary' not in all_tasks_str.lower() and 'write_summary' not in tasks_completed_str.lower():
                    logger.warning("⚠️ write_summary_task does not appear in executed tasks - this may indicate a task execution issue")
                
                # Check crew instance for task execution details
                if hasattr(crew_instance, 'tasks'):
                    task_details = []
                    for task in crew_instance.tasks:
                        task_info = {
                            "task_name": getattr(task, 'description', 'unknown')[:100] if hasattr(task, 'description') else 'unknown',
                            "agent": getattr(task, 'agent', None),
                            "output": None,
                        }
                        # Try to get task output if available
                        if hasattr(task, 'output'):
                            task_info["output"] = str(task.output)[:500] if task.output else None
                        task_details.append(task_info)
                    execution_info["task_details"] = task_details
                    
            except Exception as e:
                logger.warning(f"Could not extract detailed execution info: {e}")
                execution_info["extraction_error"] = str(e)
            
            # Save execution info for debugging
            if debug:
                execution_debug_path = OUTPUT_DIR / "crew_execution_debug.json"
                try:
                    with open(execution_debug_path, 'w', encoding='utf-8') as f:
                        json.dump(execution_info, f, indent=2, default=str)
                    logger.info(f"Saved crew execution debug info to: {execution_debug_path}")
                except Exception as e:
                    logger.warning(f"Could not save execution debug info: {e}")
            
            # Log summary of execution
            if execution_info.get("tasks_failed"):
                logger.error(f"⚠️ {len(execution_info['tasks_failed'])} tasks failed: {execution_info['tasks_failed']}")
            if execution_info.get("tasks_completed"):
                logger.info(f"✅ {len(execution_info['tasks_completed'])} tasks completed")
                
        except Exception as crew_error:
            logger.error(f"❌ Crew execution failed: {crew_error}", exc_info=True)
            execution_info = {
                "crew_completed": False,
                "error": str(crew_error),
                "error_type": type(crew_error).__name__,
            }
            if debug:
                execution_debug_path = OUTPUT_DIR / "crew_execution_debug.json"
                try:
                    with open(execution_debug_path, 'w', encoding='utf-8') as f:
                        json.dump(execution_info, f, indent=2, default=str)
                except Exception:
                    pass
            raise  # Re-raise to be handled by outer try/except
        finally:
            # Stop progress monitoring
            progress_monitor_active.clear()
            if monitor_thread:
                monitor_thread.join(timeout=1.0)
        
        # Compute pipeline status (pure Python, no LLM)
        if progress_callback:
            progress_callback(0.55, desc="Computing pipeline status...")
        
        try:
            pipeline_status, tailor_plan = compute_pipeline_status(
                has_reference_pdfs=has_reference_pdfs,
                debug=debug
            )
            logger.info("✅ Pipeline status computed")
        except Exception as e:
            logger.error(f"Pipeline status computation error: {e}", exc_info=True)
            return None, f"[error] Pipeline status computation failed: {str(e)}", None
        
        # Check pipeline status - SINGLE SOURCE OF TRUTH
        pipeline_status_path = OUTPUT_DIR / "pipeline_status.json"
        
        if not pipeline_status_path.exists():
            error_msg = "pipeline_status.json not found - status computation failed"
            logger.error(error_msg)
            if progress_callback:
                progress_callback(0.6, desc="Pipeline status computation failed")
            return None, f"[error] {error_msg}", None
        
        try:
            # Read file content first to check if it's valid JSON
            with open(pipeline_status_path, 'r', encoding='utf-8') as f:
                file_content = f.read().strip()
            
            # Check if file contains non-JSON text (likely CrewAI debug output)
            if not file_content or not (file_content.startswith('{') or file_content.startswith('[')):
                # File doesn't start with JSON structure - likely contains text output
                # Try to identify which agent/tool might have failed
                agent_hint = ""
                tool_hint = ""
                
                # Check for common patterns that indicate which agent/tool ran
                if "orchestrator" in file_content.lower() or "pipeline" in file_content.lower():
                    agent_hint = " (likely from pipeline_orchestrator agent)"
                if "write_json_file" in file_content.lower():
                    tool_hint = " - write_json_file tool may have failed or not been called"
                elif "tool" in file_content.lower():
                    tool_hint = " - a tool may have failed"
                
                # Check for crew execution debug file
                crew_debug_path = OUTPUT_DIR / "crew_execution_debug.json"
                debug_hint = ""
                if crew_debug_path.exists():
                    try:
                        with open(crew_debug_path, 'r', encoding='utf-8') as f:
                            crew_debug = json.load(f)
                        if crew_debug.get("tasks_failed"):
                            debug_hint = f"\n\nCrew execution debug shows failed tasks: {crew_debug.get('tasks_failed')}"
                        elif crew_debug.get("task_details"):
                            # Find orchestrator task
                            for task in crew_debug.get("task_details", []):
                                if "orchestrator" in str(task.get("task_name", "")).lower():
                                    debug_hint = f"\n\nOrchestrator task output: {task.get('output', 'N/A')[:200]}"
                                    break
                    except Exception:
                        pass
                
                error_msg = (
                    f"pipeline_status.json contains non-JSON content (likely debug output from orchestrator){agent_hint}. "
                    f"File content preview: {file_content[:200]}...\n\n"
                    f"This can happen when debug mode is enabled and CrewAI writes the agent's text response "
                    f"to the output_file instead of the JSON written by write_json_file tool.{tool_hint}"
                    f"{debug_hint}\n\n"
                    f"Check crew_execution_debug.json for detailed task execution info, or try running without debug mode."
                )
                logger.error(error_msg)
                logger.error(f"Full file content:\n{file_content}")
                if progress_callback:
                    progress_callback(0.6, desc="Invalid pipeline status file (contains debug text)")
                return None, f"[error] {error_msg}", None
            
            # Try to parse as JSON
            try:
                pipeline_status_raw = json.loads(file_content)
            except json.JSONDecodeError as parse_error:
                # File looks like JSON but failed to parse
                # Try to identify which agent/tool might have failed
                agent_hint = ""
                tool_hint = ""
                
                # Check for common patterns
                if "orchestrator" in file_content.lower():
                    agent_hint = " (likely from pipeline_orchestrator agent)"
                if "write_json_file" in file_content.lower():
                    tool_hint = " - write_json_file tool may have produced invalid JSON"
                
                # Check for crew execution debug file
                crew_debug_path = OUTPUT_DIR / "crew_execution_debug.json"
                debug_hint = ""
                if crew_debug_path.exists():
                    try:
                        with open(crew_debug_path, 'r', encoding='utf-8') as f:
                            crew_debug = json.load(f)
                        if crew_debug.get("tasks_failed"):
                            debug_hint = f"\n\nCrew execution debug shows failed tasks: {crew_debug.get('tasks_failed')}"
                    except Exception:
                        pass
                
                error_msg = (
                    f"pipeline_status.json is invalid JSON: {parse_error}{agent_hint}. "
                    f"File content preview: {file_content[:500]}...\n\n"
                    f"This may indicate the orchestrator agent output text instead of using write_json_file tool.{tool_hint}"
                    f"{debug_hint}\n\n"
                    f"If debug mode was enabled, CrewAI may have written the agent's response text to this file. "
                    f"Check crew_execution_debug.json for detailed task execution info."
                )
                logger.error(error_msg)
                logger.error(f"Full file content:\n{file_content}")
                if progress_callback:
                    progress_callback(0.6, desc="Invalid pipeline status file (JSON parse error)")
                return None, f"[error] {error_msg}", None
            
            # Handle nested structure: orchestrator may write {"pipeline_status.json": {...}}
            # or flat structure: {"ok": true, ...}
            if "pipeline_status.json" in pipeline_status_raw:
                pipeline_status = pipeline_status_raw["pipeline_status.json"]
            else:
                pipeline_status = pipeline_status_raw
            
            # Validate that pipeline_status.json has all required fields
            required_fields = [
                "ok", "status", "ready_for_latex", "message", "blocking_errors",
                "warnings", "phase_status", "what_was_skipped_and_why", "mode", "self_test"
            ]
            missing_fields = [field for field in required_fields if field not in pipeline_status]
            
            if missing_fields:
                error_msg = (
                    f"pipeline_status.json is incomplete - missing required fields: {', '.join(missing_fields)}. "
                    f"Orchestrator agent did not write complete schema.\n\n"
                    f"Current fields present: {', '.join(pipeline_status.keys())}\n\n"
                    f"This indicates the orchestrator agent failed to follow the complete schema. "
                    f"Check orchestrator task configuration and ensure all required fields are included."
                )
                logger.error("="*80)
                logger.error("❌ INCOMPLETE PIPELINE STATUS FILE")
                logger.error("="*80)
                logger.error(error_msg)
                logger.error(f"\nCurrent pipeline_status.json content:\n{json.dumps(pipeline_status, indent=2)}")
                
                # Check if orchestrator reported missing files that actually exist
                blocking_errors = pipeline_status.get("blocking_errors", [])
                if blocking_errors and "missing" in str(blocking_errors).lower():
                    # Check if files actually exist
                    required_file_names = [
                        "validated_profile.json", "file_collection_report.json",
                        "selected_experiences.json", "selected_skills.json",
                        "summary_block.json", "education_block.json"
                    ]
                    existing_files = []
                    missing_files = []
                    for file_name in required_file_names:
                        file_path = OUTPUT_DIR / file_name
                        if file_path.exists():
                            existing_files.append(file_name)
                        else:
                            missing_files.append(file_name)
                    
                    if existing_files:
                        logger.warning(f"\n⚠️ DIAGNOSTIC: Some required files actually exist but orchestrator reported them missing:")
                        logger.warning(f"  Existing files: {', '.join(existing_files)}")
                        if missing_files:
                            logger.warning(f"  Actually missing: {', '.join(missing_files)}")
                        logger.warning(f"\nThis suggests the orchestrator used incorrect file paths when calling read_json_file.")
                        logger.warning(f"Orchestrator should use: read_json_file('output/{file_name}')")
                
                # Try to provide helpful recovery information
                recovery_hint = ""
                if "ok" in pipeline_status and not pipeline_status.get("ok"):
                    # If ok=false but we have blocking_errors, show them
                    if blocking_errors:
                        recovery_hint = f"\n\nBlocking errors reported: {blocking_errors}"
                    elif "message" in pipeline_status:
                        recovery_hint = f"\n\nMessage: {pipeline_status.get('message')}"
                
                if progress_callback:
                    progress_callback(0.6, desc="Incomplete pipeline status file")
                return None, f"[error] {error_msg}{recovery_hint}", None
            
            # Validate field types
            validation_errors = []
            if not isinstance(pipeline_status.get("ok"), bool):
                validation_errors.append("'ok' must be boolean")
            if not isinstance(pipeline_status.get("ready_for_latex"), bool):
                validation_errors.append("'ready_for_latex' must be boolean")
            if not isinstance(pipeline_status.get("blocking_errors"), list):
                validation_errors.append("'blocking_errors' must be an array")
            if not isinstance(pipeline_status.get("warnings"), list):
                validation_errors.append("'warnings' must be an array")
            if not isinstance(pipeline_status.get("phase_status"), dict):
                validation_errors.append("'phase_status' must be an object")
            if not isinstance(pipeline_status.get("what_was_skipped_and_why"), list):
                validation_errors.append("'what_was_skipped_and_why' must be an array")
            
            if validation_errors:
                error_msg = (
                    f"pipeline_status.json has invalid field types: {', '.join(validation_errors)}. "
                    f"Orchestrator agent wrote incorrect schema.\n\n"
                    f"Current content:\n{json.dumps(pipeline_status, indent=2)}"
                )
                logger.error("="*80)
                logger.error("❌ INVALID PIPELINE STATUS SCHEMA")
                logger.error("="*80)
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(0.6, desc="Invalid pipeline status schema")
                return None, f"[error] {error_msg}", None
            
            # Fail fast if pipeline status indicates errors
            if not pipeline_status.get("ok", False):
                blocking_errors = pipeline_status.get("blocking_errors", [])
                error_msg = "; ".join(blocking_errors) if blocking_errors else "Pipeline blocked by errors"
                
                # Enhanced error logging
                logger.error("="*80)
                logger.error("❌ PIPELINE BLOCKED BY ERRORS")
                logger.error("="*80)
                logger.error(f"Overall status: {pipeline_status.get('status', 'unknown')}")
                logger.error(f"Self-test: {pipeline_status.get('self_test', 'unknown')}")
                
                if blocking_errors:
                    logger.error("\nBlocking errors:")
                    for i, err in enumerate(blocking_errors, 1):
                        logger.error(f"  {i}. {err}")
                
                # Show non-success phases
                phase_status = pipeline_status.get("phase_status", {})
                if phase_status:
                    failed_phases = {p: s for p, s in phase_status.items() if s != "success"}
                    if failed_phases:
                        logger.error("\nFailed/warning phases:")
                        for phase, status in sorted(failed_phases.items()):
                            logger.error(f"  - {phase}: {status}")
                
                if progress_callback:
                    progress_callback(0.6, desc="Pipeline blocked by errors")
                return None, f"[error] Pipeline blocked: {error_msg}", None
            
            # Fail fast if pipeline status indicates not ready for LaTeX
            if not pipeline_status.get("ready_for_latex", False):
                error_msg = pipeline_status.get("message", "Pipeline not ready for LaTeX generation")
                
                # Enhanced error logging
                logger.error("="*80)
                logger.error("❌ PIPELINE NOT READY FOR LATEX")
                logger.error("="*80)
                logger.error(f"Overall status: {pipeline_status.get('status', 'unknown')}")
                logger.error(f"Message: {error_msg}")
                
                blocking_errors = pipeline_status.get("blocking_errors", [])
                if blocking_errors:
                    logger.error("\nBlocking errors:")
                    for i, err in enumerate(blocking_errors, 1):
                        logger.error(f"  {i}. {err}")
                
                # Show non-success phases
                phase_status = pipeline_status.get("phase_status", {})
                if phase_status:
                    failed_phases = {p: s for p, s in phase_status.items() if s != "success"}
                    if failed_phases:
                        logger.error("\nFailed/warning phases:")
                        for phase, status in sorted(failed_phases.items()):
                            logger.error(f"  - {phase}: {status}")
                
                if progress_callback:
                    progress_callback(0.6, desc="Pipeline not ready for LaTeX generation")
                return None, f"[error] {error_msg}", None
            
            # Log phase status in readable format (only non-success phases for brevity)
            phase_status = pipeline_status.get("phase_status", {})
            if phase_status:
                non_success = {p: s for p, s in phase_status.items() if s != "success"}
                if non_success:
                    logger.info("Phase status (non-success only):")
                    for phase, status in sorted(non_success.items()):
                        logger.info(f"  - {phase}: {status}")
                else:
                    logger.info("✅ All phases completed successfully")
            
            # Log warnings if any
            warnings = pipeline_status.get("warnings", [])
            if warnings:
                logger.warning("Pipeline warnings:")
                for warning in warnings:
                    logger.warning(f"  ⚠️ {warning}")
            
            # Log what was skipped
            skipped = pipeline_status.get("what_was_skipped_and_why", [])
            if skipped:
                logger.info("Skipped phases:")
                for item in skipped:
                    phase = item.get("phase", "unknown")
                    reason = item.get("reason", "unknown reason")
                    logger.info(f"  - {phase}: {reason}")
            
            logger.info(f"✅ Pipeline status: {pipeline_status.get('status', 'unknown')} - Ready for LaTeX generation")
            
            # Store mode for later use in success message
            detected_mode = pipeline_status.get("mode", "standard")
            
            # Handle debug mode output
            if debug:
                debug_file = OUTPUT_DIR / "pipeline_status_debug.json"
                if debug_file.exists():
                    try:
                        with open(debug_file, 'r', encoding='utf-8') as f:
                            debug_data = json.load(f)
                        
                        logger.info("="*80)
                        logger.info("🐛 DEBUG MODE OUTPUT")
                        logger.info("="*80)
                        
                        # Print orchestration trace summary
                        trace = debug_data.get("orchestration_trace", [])
                        if trace:
                            logger.info(f"\nOrchestration trace ({len(trace)} steps):")
                            for step in trace[:10]:  # Show first 10 steps
                                step_name = step.get("step", "unknown")
                                file_name = step.get("file", "").split("/")[-1] if step.get("file") else ""
                                exists = step.get("exists", False)
                                status = step.get("status", "unknown")
                                logger.info(f"  [{step_name}] {file_name}: exists={exists}, status={status}")
                            if len(trace) > 10:
                                logger.info(f"  ... and {len(trace) - 10} more steps")
                        
                        # Print ready_for_latex reasoning
                        reasoning = debug_data.get("ready_for_latex_reasoning", "")
                        if reasoning:
                            logger.info(f"\nReady for LaTeX reasoning:\n  {reasoning}")
                        
                        logger.info(f"\nFull debug trace saved to: {debug_file}")
                        logger.info("="*80)
                    except Exception as e:
                        logger.warning(f"Could not read debug file: {e}")
            
        except json.JSONDecodeError as e:
            error_msg = f"pipeline_status.json is invalid JSON: {e}"
            logger.error(error_msg)
            if progress_callback:
                progress_callback(0.6, desc="Invalid pipeline status file")
            return None, f"[error] {error_msg}", None
        except Exception as e:
            error_msg = f"Could not read pipeline status: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            if progress_callback:
                progress_callback(0.6, desc="Failed to read pipeline status")
            return None, f"[error] {error_msg}", None
        
        if progress_callback:
            progress_callback(0.6, desc="AI agents completed analysis. Generating LaTeX...")
        
    except Exception as e:
        logger.error(f"Crew execution failed: {e}")
        logger.error(traceback.format_exc())
        if progress_callback:
            progress_callback(0.6, desc="Error during AI agent execution")
        return None, f"[error] Crew execution failed:\n{str(e)}\n\n{traceback.format_exc()}", None
    
    # All orchestration logic is now in the orchestrator agent
    # Python only checks pipeline_status.json and proceeds with LaTeX generation
    
    # Step 2: Generate LaTeX using Python builder (no agents involved)
    try:
        logger.info("="*80)
        logger.info("Building LaTeX resume from JSON data...")
        logger.info("="*80)
        if progress_callback:
            progress_callback(0.7, desc="Building LaTeX resume from AI-generated content...")
        
        from resume_builder.latex_builder import build_resume_from_json_files
        
        # Load JSON outputs from agents
        # The orchestrator has already verified readiness, but we double-check physical file existence
        # as a safety measure before attempting LaTeX generation
        identity_json = OUTPUT_DIR / "user_profile.json"
        summary_json = OUTPUT_DIR / "summary_block.json"
        experience_json = OUTPUT_DIR / "selected_experiences.json"
        education_json = OUTPUT_DIR / "education_block.json"
        skills_json = OUTPUT_DIR / "selected_skills.json"
        projects_json = OUTPUT_DIR / "selected_projects.json"  # Optional - orchestrator may have skipped this
        header_json = OUTPUT_DIR / "header_block.json"  # Optional - tailored header with keywords
        rendered_tex = RENDERED_TEX
        
        # Verify required files exist (pipeline status should have caught this, but we verify physically)
        required_files = {
            "user_profile.json": identity_json,
            "summary_block.json": summary_json,
            "selected_experiences.json": experience_json,
            "selected_skills.json": skills_json,
        }
        
        # Education is optional - builder can handle empty list
        optional_files = {
            "education_block.json": education_json,
        }
        
        missing_files = []
        for name, file_path in required_files.items():
            if not file_path.exists():
                missing_files.append(name)
        
        # Fallback: Generate summary_block.json if missing (workaround for write_summary_task not executing)
        if "summary_block.json" in missing_files:
            logger.warning("summary_block.json is missing - generating fallback summary from selected experiences and skills")
            try:
                # Read selected experiences and skills to generate a basic summary
                exp_data = load_selected_experiences(experience_json)
                skills_data = load_selected_skills(skills_json)
                
                # Extract key information
                experiences = exp_data.get('selected_experiences', [])
                skills = skills_data.get('selected_skills', [])
                
                # Generate a simple summary
                if experiences:
                    first_exp = experiences[0]
                    org = first_exp.get('organization', '')
                    title = first_exp.get('title', '')
                    summary_text = f"Experienced {title} with expertise in {', '.join(skills[:3]) if skills else 'software development'}. "
                    if len(experiences) > 1:
                        summary_text += f"Proven track record in {len(experiences)} key roles with focus on technical excellence and innovation."
                    else:
                        summary_text += "Demonstrated ability to deliver high-quality solutions in research and development environments."
                else:
                    summary_text = f"Skilled professional with expertise in {', '.join(skills[:5]) if skills else 'software development'}."
                
                # Create summary_block.json
                summary_data = {
                    "status": "success",
                    "message": "Fallback summary generated (write_summary_task did not execute)",
                    "summary": summary_text
                }
                summary_json.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                logger.info(f"✅ Generated fallback summary_block.json: {summary_text[:100]}...")
                missing_files.remove("summary_block.json")
            except Exception as e:
                logger.error(f"Failed to generate fallback summary_block.json: {e}")
        
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
            logger.info("Optional file found: header_block.json")
        else:
            logger.info("Optional file not found: header_block.json (will use default header)")
        
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
            validation_errors.append(f"summary_block.json: {summary_data.get('message', 'Missing summary field')}")
        
        exp_data = load_selected_experiences(experience_json)
        if exp_data.get("status") != "success" or "selected_experiences" not in exp_data:
            validation_errors.append(f"selected_experiences.json: {exp_data.get('message', 'Missing selected_experiences field')}")
        elif not isinstance(exp_data.get("selected_experiences", []), list):
            validation_errors.append(f"selected_experiences.json: Expected list, got {type(exp_data.get('selected_experiences')).__name__}")
        
        skills_data = load_selected_skills(skills_json)
        if skills_data.get("status") != "success" or "selected_skills" not in skills_data:
            validation_errors.append(f"selected_skills.json: {skills_data.get('message', 'Missing selected_skills field')}")
        elif not isinstance(skills_data.get("selected_skills", []), list):
            validation_errors.append(f"selected_skills.json: Expected list, got {type(skills_data.get('selected_skills')).__name__}")
        
        # Validate optional files if they exist
        if education_json.exists():
            edu_data = load_education_block(education_json)
            if edu_data.get("status") != "success" or "education" not in edu_data:
                validation_errors.append(f"education_block.json: {edu_data.get('message', 'Missing education field')}")
        
        if projects_json.exists():
            proj_data = load_selected_projects(projects_json)
            if proj_data.get("status") != "success" or "selected_projects" not in proj_data:
                validation_errors.append(f"selected_projects.json: {proj_data.get('message', 'Missing selected_projects field')}")
        
        if header_json.exists():
            header_data = load_header_block(header_json)
            if header_data.get("status") != "success" or "title_line" not in header_data or "contact_info" not in header_data:
                validation_errors.append(f"header_block.json: {header_data.get('message', 'Missing title_line or contact_info field')}")
        
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
            logger.info("education_block.json not found, using empty education list")
            temp_edu = OUTPUT_DIR / "education_block_temp.json"
            temp_edu.write_text(json.dumps({"status": "success", "message": "No education data", "education": []}), encoding='utf-8')
            education_json = temp_edu
        
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
            output_path=rendered_tex
        )
        
        logger.info(f"✅ LaTeX generated: {rendered_tex}")
        
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
        if progress_callback:
            progress_callback(0.80, desc="Repairing LaTeX file...")
        
        from resume_builder.latex_builder import repair_latex_file
        
        # Read the generated LaTeX
        original_latex = rendered_tex.read_text(encoding='utf-8')
        
        # Only run repair_latex_file() on imported/legacy TeX files, not on resumecv output
        # repair_latex_file() converts to article class, which would break resumecv files
        is_resumecv = bool(re.search(r'\\documentclass[^\n]*\{resumecv\}', original_latex))
        
        if is_resumecv:
            logger.info("Skipping repair_latex_file() for resumecv class (builder output is already correct)")
            repaired_latex = original_latex
        else:
            # Apply repairs (for imported/legacy files that need conversion)
            repaired_latex = repair_latex_file(original_latex)
        
        # Write repaired version back
        rendered_tex.write_text(repaired_latex, encoding='utf-8')
        
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
        if progress_callback:
            progress_callback(0.85, desc="Compiling LaTeX to PDF...")
        
        from resume_builder.tools.latex_compile import LatexCompileTool
        
        compiler = LatexCompileTool()
        compile_result = compiler._run(
            tex_path=str(rendered_tex),
            out_name="final_resume.pdf",
            workdir=".",
            engine="pdflatex"
        )
        
        logger.info(f"Compilation result: {compile_result}")
        
        # Check if PDF was created
        if FINAL_PDF.exists():
            pdf_size = FINAL_PDF.stat().st_size
            logger.info(f"✅ PDF generated successfully: {FINAL_PDF} ({pdf_size} bytes)")
            if progress_callback:
                progress_callback(0.95, desc="✅ PDF compiled successfully!")
            
            # Generate cover letter PDF if available
            cover_letter_pdf_path = None
            cover_letter_path = OUTPUT_DIR / "cover_letter.json"
            if cover_letter_path.exists():
                try:
                    cover_letter_data = load_cover_letter(cover_letter_path)
                    # Check both 'ok' and 'status' fields (cover letter uses 'ok' for orchestrator validation)
                    if cover_letter_data.get("ok") is True or cover_letter_data.get("status") == "success":
                        word_count = cover_letter_data.get("meta", {}).get("word_count", "unknown")
                        logger.info(f"📄 Cover letter generated at output/cover_letter.json (word_count: {word_count})")
                        
                        # Generate cover letter PDF
                        try:
                            cover_letter_pdf_path = _generate_cover_letter_pdf(cover_letter_data, OUTPUT_DIR)
                            if cover_letter_pdf_path:
                                logger.info(f"✅ Cover letter PDF generated: {cover_letter_pdf_path}")
                        except Exception as e:
                            logger.warning(f"Failed to generate cover letter PDF: {e}")
                            cover_letter_pdf_path = None
                    else:
                        error_msg = cover_letter_data.get("message", "Unknown error")
                        logger.warning(f"Cover letter generation failed: {error_msg}")
                except Exception as e:
                    logger.debug(f"Could not read cover letter metadata: {e}")
            
            # Step 4: Quality check the PDF
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
        team = ResumeTeam(fast_mode=fast_mode)
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

