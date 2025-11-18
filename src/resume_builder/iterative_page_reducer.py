"""
Iterative Page Reduction System

Continuously detects least important content and removes it until resume fits in ≤2 pages.
Uses LaTeX gap analysis and content ranking to intelligently remove content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR
from resume_builder.length_budget import estimate_lines, TARGET_LINES_PER_PAGE
from resume_builder.tools.content_rank_analyzer import ContentRankAnalyzerTool
from resume_builder.tools.content_removal_tool import ContentRemovalTool

logger = get_logger("iterative_page_reducer")

MAX_ITERATIONS = 5  # Maximum iterations to avoid infinite loops


def iteratively_reduce_pages(
    summary_path: Path,
    experience_path: Path,
    skills_path: Path,
    projects_path: Optional[Path] = None,
    education_path: Optional[Path] = None,
    jd_path: Path = OUTPUT_DIR / "parsed_jd.json",
    target_pages: float = 2.0,
    max_iterations: int = MAX_ITERATIONS
) -> Dict[str, Any]:
    """
    Iteratively remove least important content until resume fits in ≤2 pages.
    
    Process:
    1. Estimate current pages
    2. If > target_pages:
       a. Rank content by importance
       b. Remove lowest priority item
       c. Re-estimate pages
       d. Repeat until ≤ target_pages or max_iterations reached
    
    Args:
        summary_path: Path to summary.json
        experience_path: Path to selected_experiences.json
        skills_path: Path to selected_skills.json
        projects_path: Optional path to selected_projects.json
        education_path: Optional path to education.json
        jd_path: Path to parsed_jd.json for relevance scoring
        target_pages: Target page count (default: 2.0)
        max_iterations: Maximum iterations (default: 5)
        
    Returns:
        Dictionary with reduction log:
        {
            "status": "success" | "partial" | "error",
            "message": str,
            "iterations": int,
            "items_removed": List[Dict],
            "initial_estimated_pages": float,
            "final_estimated_pages": float,
            "target_met": bool
        }
    """
    reduction_log = {
        "status": "success",
        "message": "",
        "iterations": 0,
        "items_removed": [],
        "initial_estimated_pages": 0.0,
        "final_estimated_pages": 0.0,
        "target_met": False
    }
    
    try:
        # Load JSON files to estimate initial pages
        from resume_builder.json_loaders import (
            load_summary_block,
            load_selected_experiences,
            load_selected_skills,
            load_selected_projects,
            load_education_block
        )
        
        # Initial estimate
        summary_data = load_summary_block(summary_path)
        summary = summary_data.get('summary', '')
        
        exp_data = load_selected_experiences(experience_path)
        experiences = exp_data.get('selected_experiences', [])
        
        skills_data = load_selected_skills(skills_path)
        skills = skills_data.get('skills', skills_data.get('selected_skills', []))
        
        projects = []
        if projects_path and projects_path.exists():
            proj_data = load_selected_projects(projects_path)
            projects = proj_data.get('selected_projects', [])
        
        education = []
        if education_path and education_path.exists():
            edu_data = load_education_block(education_path)
            education = edu_data.get('education', [])
        
        # Store initial state for comparison
        initial_summary = summary
        initial_experiences_count = len(experiences)
        initial_projects_count = len(projects)
        initial_skills_count = len(skills)
        initial_education_count = len(education)
        
        estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
        estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
        reduction_log["initial_estimated_pages"] = estimated_pages
        
        logger.info(f"Initial state: {initial_experiences_count} exp, {initial_projects_count} proj, {initial_skills_count} skills, {initial_education_count} edu")
        
        logger.info(f"Starting iterative page reduction: {estimated_pages:.1f} pages (target: ≤{target_pages})")
        
        if estimated_pages <= target_pages:
            reduction_log["target_met"] = True
            reduction_log["final_estimated_pages"] = estimated_pages
            reduction_log["message"] = f"Resume already within target ({estimated_pages:.1f} pages)"
            return reduction_log
        
        # Initialize tools
        rank_analyzer = ContentRankAnalyzerTool()
        removal_tool = ContentRemovalTool()
        
        logger.info("Using LLM-powered content ranking for fast, intelligent removal suggestions")
        
        # Iterative removal loop
        iteration = 0
        while estimated_pages > target_pages and iteration < max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{max_iterations}: Current pages: {estimated_pages:.1f}, Target: ≤{target_pages}")
            
            # Get ranked removal suggestions
            try:
                # Convert absolute paths to relative paths for tools
                def to_relative_path(p: Path) -> str:
                    if p.is_relative_to(OUTPUT_DIR):
                        return str(p.relative_to(OUTPUT_DIR))
                    elif p.is_absolute():
                        # If absolute but not under OUTPUT_DIR, use just the filename
                        return p.name
                    else:
                        return str(p)
                
                suggestions_json = rank_analyzer._run(
                    experiences_path=to_relative_path(experience_path),
                    skills_path=to_relative_path(skills_path),
                    summary_path=to_relative_path(summary_path),
                    jd_path=to_relative_path(jd_path),
                    projects_path=to_relative_path(projects_path) if projects_path else None,
                    education_path=to_relative_path(education_path) if education_path else None,
                    estimated_pages=estimated_pages,
                    target_pages=target_pages
                )
                
                suggestions_data = json.loads(suggestions_json)
                removal_suggestions = suggestions_data.get('removal_suggestions', [])
                
                # Also check ranked items with suggest_remove=True
                if not removal_suggestions:
                    # Fallback: extract from ranked items
                    ranked_skills = suggestions_data.get('ranked_skills', [])
                    for skill in ranked_skills:
                        if skill.get('suggest_remove', False):
                            removal_suggestions.append({
                                'type': 'skill',
                                'index': ranked_skills.index(skill),
                                'skill': skill.get('skill', 'Unknown'),
                                'reason': skill.get('reason', 'Low priority'),
                                'estimated_savings_lines': 1
                            })
                    
                    ranked_experiences = suggestions_data.get('ranked_experiences', [])
                    for exp in ranked_experiences:
                        if exp.get('suggest_remove', False):
                            removal_suggestions.append({
                                'type': 'experience',
                                'index': exp.get('index', -1),
                                'title': exp.get('title', 'Unknown'),
                                'reason': exp.get('reason', 'Low priority'),
                                'estimated_savings_lines': 8
                            })
                    
                    ranked_projects = suggestions_data.get('ranked_projects', [])
                    for proj in ranked_projects:
                        if proj.get('suggest_remove', False):
                            removal_suggestions.append({
                                'type': 'project',
                                'index': proj.get('index', -1),
                                'name': proj.get('name', 'Unknown'),
                                'reason': proj.get('reason', 'Low priority'),
                                'estimated_savings_lines': 6
                            })
                    
                    ranked_bullets = suggestions_data.get('ranked_bullets', [])
                    for bullet in ranked_bullets:
                        if bullet.get('suggest_remove', False):
                            removal_suggestions.append({
                                'type': 'bullet',
                                'item_index': bullet.get('parent_index', -1),
                                'bullet_index': bullet.get('bullet_index', -1),
                                'text': bullet.get('text', 'Unknown')[:50],
                                'reason': bullet.get('reason', 'Low priority'),
                                'estimated_savings_lines': 2
                            })
                
                if not removal_suggestions:
                    logger.warning(f"No removal suggestions available at iteration {iteration}")
                    break
                
                # Calculate how much we still need to remove
                lines_still_needed = int((estimated_pages - target_pages) * TARGET_LINES_PER_PAGE)
                
                # If we have multiple suggestions, try to remove multiple items in one iteration
                # (to reduce LLM calls for large reductions)
                items_to_remove_this_iteration = []
                total_savings = 0
                
                for suggestion in removal_suggestions:
                    if total_savings >= lines_still_needed:
                        break
                    items_to_remove_this_iteration.append(suggestion)
                    total_savings += suggestion.get('estimated_savings_lines', 1)
                
                # If we need a lot of reduction, remove multiple items per iteration
                # Otherwise, remove one at a time for precision
                if lines_still_needed > 10:  # Need more than 10 lines (0.4 pages)
                    # Remove up to 3 items per iteration for speed
                    items_to_remove_this_iteration = removal_suggestions[:min(3, len(removal_suggestions))]
                else:
                    # Remove one at a time for precision
                    items_to_remove_this_iteration = removal_suggestions[:1]
                
                logger.info(f"Removing {len(items_to_remove_this_iteration)} item(s) this iteration (need ~{lines_still_needed} lines)")
                
                # Remove all selected items in this iteration
                removed_any = False
                for top_removal in items_to_remove_this_iteration:
                    removal_type = top_removal.get('type', '')
                    removal_index = top_removal.get('index', -1)
                    removal_reason = top_removal.get('reason', 'Low priority')
                    
                    logger.info(f"Removing {removal_type} at index {removal_index}: {removal_reason}")
                    
                    # Remove the item
                    removal_result_json = None
                    if removal_type == "experience":
                        removal_result_json = removal_tool._run(
                            removal_type="experience",
                            target_index=removal_index
                        )
                    elif removal_type == "project":
                        removal_result_json = removal_tool._run(
                            removal_type="project",
                            target_index=removal_index
                        )
                    elif removal_type == "skill":
                        removal_result_json = removal_tool._run(
                            removal_type="skill",
                            target_index=removal_index
                        )
                    elif removal_type == "summary_words":
                        words_to_remove = top_removal.get('words_to_remove', 10)
                        removal_result_json = removal_tool._run(
                            removal_type="summary_words",
                            words_to_remove=words_to_remove
                        )
                    elif removal_type == "bullet":
                        # Content rank analyzer uses different field names
                        parent_index = top_removal.get('item_index', top_removal.get('parent_index', -1))
                        bullet_index = top_removal.get('bullet_index', -1)
                        if parent_index == -1 or bullet_index == -1:
                            logger.warning(f"Invalid bullet removal indices: parent={parent_index}, bullet={bullet_index}")
                            continue
                        removal_result_json = removal_tool._run(
                            removal_type="bullet",
                            parent_index=parent_index,
                            bullet_index=bullet_index
                        )
                    else:
                        logger.warning(f"Unknown removal type: {removal_type}")
                        continue
                    
                    if removal_result_json:
                        removal_result = json.loads(removal_result_json)
                        if removal_result.get('status') == 'success':
                            removed_item = removal_result.get('removed_item', 'Unknown')
                            reduction_log["items_removed"].append({
                                "iteration": iteration,
                                "type": removal_type,
                                "item": removed_item,
                                "reason": removal_reason,
                                "index": removal_index
                            })
                            logger.info(f"✅ Removed {removal_type}: {removed_item}")
                            removed_any = True
                        else:
                            logger.warning(f"Failed to remove {removal_type}: {removal_result.get('message', 'Unknown error')}")
                            continue
                
                if not removed_any:
                    logger.warning(f"No items were successfully removed in iteration {iteration}")
                    break
                
                # Reload data and re-estimate (CRITICAL: reload education too)
                summary_data = load_summary_block(summary_path)
                summary = summary_data.get('summary', '')
                
                exp_data = load_selected_experiences(experience_path)
                experiences = exp_data.get('selected_experiences', [])
                
                skills_data = load_selected_skills(skills_path)
                skills = skills_data.get('skills', skills_data.get('selected_skills', []))
                
                if projects_path and projects_path.exists():
                    proj_data = load_selected_projects(projects_path)
                    projects = proj_data.get('selected_projects', [])
                else:
                    projects = []
                
                # Reload education (it might have changed)
                if education_path and education_path.exists():
                    edu_data = load_education_block(education_path)
                    education = edu_data.get('education', [])
                else:
                    education = []
                
                estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
                estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
                
                logger.info(f"After iteration {iteration}: {estimated_pages:.1f} pages (exp:{len(experiences)}, proj:{len(projects)}, skills:{len(skills)})")
                
                if estimated_pages <= target_pages:
                    reduction_log["target_met"] = True
                    logger.info(f"✅ Target met after {iteration} iterations: {estimated_pages:.1f} pages")
                    break
                    
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}", exc_info=True)
                break
        
        reduction_log["iterations"] = iteration
        reduction_log["final_estimated_pages"] = estimated_pages
        
        if reduction_log["target_met"]:
            reduction_log["status"] = "success"
            reduction_log["message"] = f"Successfully reduced to {estimated_pages:.1f} pages in {iteration} iterations"
        elif iteration >= max_iterations:
            reduction_log["status"] = "partial"
            reduction_log["message"] = f"Reached max iterations ({max_iterations}). Final: {estimated_pages:.1f} pages (target: ≤{target_pages})"
        else:
            reduction_log["status"] = "partial"
            reduction_log["message"] = f"Stopped early. Final: {estimated_pages:.1f} pages (target: ≤{target_pages})"
        
        return reduction_log
        
    except Exception as e:
        logger.error(f"Error in iterative page reduction: {e}", exc_info=True)
        reduction_log["status"] = "error"
        reduction_log["message"] = f"Error during iterative page reduction: {str(e)}"
        return reduction_log

