"""
Length Budget Enforcement for Resume Builder

This module provides deterministic trimming of resume JSON content to ensure
the final resume fits within a 2-page limit. It works directly on JSON files
before LaTeX generation, keeping the pipeline simple and transparent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR

logger = get_logger("length_budget")

# Configuration constants for length limits
MAX_EXPERIENCES = 4
MAX_EXPERIENCE_BULLETS = 3
MAX_PROJECTS = 3
MAX_PROJECT_BULLETS = 2
MAX_SKILLS = 16
MAX_SUMMARY_WORDS = 100
MAX_EDUCATION_ENTRIES = 2

# Line estimation constants (conservative to account for text wrapping and formatting)
TARGET_LINES_PER_PAGE = 25  # Reduced from 55 - actual resumes with wrapping use fewer lines
MAX_PAGES = 2
MAX_TOTAL_LINES = TARGET_LINES_PER_PAGE * MAX_PAGES


def truncate_bullets(bullets: List[str], max_bullets: int, max_words_per_bullet: Optional[int] = None) -> Tuple[List[str], int]:
    """
    Truncate a list of bullet points.
    
    Args:
        bullets: List of bullet point strings
        max_bullets: Maximum number of bullets to keep
        max_words_per_bullet: Optional maximum words per bullet (truncates long bullets)
        
    Returns:
        Tuple of (truncated_bullets, num_removed)
    """
    if not bullets:
        return [], 0
    
    original_count = len(bullets)
    truncated = list(bullets[:max_bullets])
    
    # Optionally truncate individual bullets if they're too long
    if max_words_per_bullet:
        for i, bullet in enumerate(truncated):
            words = bullet.split()
            if len(words) > max_words_per_bullet:
                truncated[i] = ' '.join(words[:max_words_per_bullet]) + '...'
    
    num_removed = original_count - len(truncated)
    return truncated, num_removed


def truncate_list(items: List[Any], max_items: int, sort_key: Optional[callable] = None) -> Tuple[List[Any], int]:
    """
    Truncate a list to a maximum number of items.
    
    Args:
        items: List of items
        max_items: Maximum number of items to keep
        sort_key: Optional function to sort items before truncation (keeps highest priority)
        
    Returns:
        Tuple of (truncated_list, num_removed)
    """
    if not items:
        return [], 0
    
    original_count = len(items)
    
    # Sort by priority if sort_key provided, otherwise keep first N (assumed already ordered)
    if sort_key and len(items) > max_items:
        sorted_items = sorted(items, key=sort_key, reverse=True)
        truncated = sorted_items[:max_items]
    else:
        truncated = list(items[:max_items])
    
    num_removed = original_count - len(truncated)
    return truncated, num_removed


def truncate_summary(text: str, max_words: int) -> Tuple[str, int]:
    """
    Truncate summary text to a maximum word count.
    
    Args:
        text: Summary text
        max_words: Maximum number of words
        
    Returns:
        Tuple of (truncated_text, words_removed)
    """
    if not text:
        return "", 0
    
    words = text.split()
    original_word_count = len(words)
    
    if len(words) <= max_words:
        return text, 0
    
    truncated_words = words[:max_words]
    truncated_text = ' '.join(truncated_words) + '...'
    words_removed = original_word_count - max_words
    
    return truncated_text, words_removed


def estimate_lines(
    summary: str,
    experiences: List[Dict[str, Any]],
    projects: List[Dict[str, Any]],
    skills: List[str],
    education: List[Dict[str, Any]]
) -> int:
    """
    Estimate total lines used by resume content.
    
    Args:
        summary: Summary text
        experiences: List of experience dicts
        projects: List of project dicts
        skills: List of skill strings
        education: List of education dicts
        
    Returns:
        Estimated total lines
    """
    total = 0
    
    # Header + summary: ~12-15 lines (accounts for formatting and spacing)
    summary_words = len(summary.split()) if summary else 0
    summary_lines = max(2, int(summary_words / 8))  # ~8 words per line (conservative)
    total += 14 + summary_lines
    
    # Experiences: base 6 lines + estimate based on actual text length
    for exp in experiences:
        total += 6  # Title, company, dates, spacing
        bullets = exp.get('bullets', [])
        for bullet in bullets:
            if isinstance(bullet, str):
                # Estimate lines based on text length: account for wrapping
                words = len(bullet.split())
                bullet_lines = max(1, int(words / 10) + 1)  # ~10 words per line, +1 for spacing
                total += bullet_lines
            else:
                total += 1.5  # Fallback
    
    # Projects: more compact format - base 3 lines per project (reduced from 5)
    # Projects now use inline bullets instead of itemize lists, saving ~2 lines per project
    for proj in projects:
        total += 3  # Name, description, spacing (reduced from 5 due to compact formatting)
        bullets = proj.get('bullets', [])
        if bullets:
            # Inline bullets take less space - estimate ~0.5 lines per bullet (was 1+ lines)
            for bullet in bullets:
                if isinstance(bullet, str):
                    words = len(bullet.split())
                    # Inline format is more compact - ~15 words per line instead of 10
                    bullet_lines = max(0.5, int(words / 15) + 0.5)  # At least 0.5 lines
                    total += bullet_lines
                else:
                    total += 0.5  # Reduced from 1.5
        elif proj.get('description'):
            # Single description line - estimate based on words
            desc = str(proj.get('description', ''))
            words = len(desc.split())
            total += max(0.5, int(words / 15) + 0.5)  # More compact inline format
    
    # Skills: ~8 lines if <= 15 skills, else ~12+ lines (accounts for wrapping)
    if len(skills) <= 15:
        total += 8
    else:
        total += 12 + int((len(skills) - 15) / 5)  # Extra line per 5 skills
    
    # Education: ~5 lines per entry (accounts for spacing and formatting)
    total += len(education) * 5
    
    # Section headers and spacing: ~3 lines per section (headers take more space)
    section_count = 1  # Summary
    if experiences:
        section_count += 1  # Experience
    if projects:
        section_count += 1  # Projects
    if skills:
        section_count += 1  # Skills
    if education:
        section_count += 1  # Education
    total += section_count * 3
    
    return int(total)


def enforce_length_budget_on_json_files(
    summary_path: Path,
    experience_path: Path,
    skills_path: Path,
    projects_path: Optional[Path] = None,
    education_path: Optional[Path] = None,
    max_pages: int = MAX_PAGES
) -> Dict[str, Any]:
    """
    Enforce length budget by modifying JSON files directly.
    
    This function reads JSON files, trims content deterministically, and writes
    them back. It returns metadata about what was trimmed.
    
    Args:
        summary_path: Path to summary.json
        experience_path: Path to selected_experiences.json
        skills_path: Path to selected_skills.json
        projects_path: Optional path to selected_projects.json
        education_path: Optional path to education.json
        max_pages: Maximum number of pages (default: 2)
        
    Returns:
        Dictionary with trimming metadata:
        {
            "trimmed_experiences": int,
            "trimmed_experience_bullets": int,
            "trimmed_projects": int,
            "trimmed_project_bullets": int,
            "trimmed_skills": int,
            "trimmed_summary_words": int,
            "trimmed_education": int,
            "estimated_lines_before": int,
            "estimated_lines_after": int,
            "estimated_pages_before": float,
            "estimated_pages_after": float
        }
    """
    metadata = {
        "trimmed_experiences": 0,
        "trimmed_experience_bullets": 0,
        "trimmed_projects": 0,
        "trimmed_project_bullets": 0,
        "trimmed_skills": 0,
        "trimmed_summary_words": 0,
        "trimmed_education": 0,
        "estimated_lines_before": 0,
        "estimated_lines_after": 0,
        "estimated_pages_before": 0.0,
        "estimated_pages_after": 0.0
    }
    
    try:
        # Load JSON files
        from resume_builder.json_loaders import (
            load_summary_block,
            load_selected_experiences,
            load_selected_skills,
            load_selected_projects,
            load_education_block
        )
        
        # Load summary
        summary_data = load_summary_block(summary_path)
        summary = summary_data.get('summary', '')
        
        # Load experiences
        exp_data = load_selected_experiences(experience_path)
        experiences = exp_data.get('selected_experiences', [])
        
        # Load skills
        skills_data = load_selected_skills(skills_path)
        skills = skills_data.get('skills', skills_data.get('selected_skills', []))
        
        # Load projects (optional)
        projects = []
        proj_data = None
        if projects_path and projects_path.exists():
            proj_data = load_selected_projects(projects_path)
            projects = proj_data.get('selected_projects', [])
        
        # Load education (optional)
        education = []
        edu_data = None
        if education_path and education_path.exists():
            edu_data = load_education_block(education_path)
            education = edu_data.get('education', [])
        
        # Estimate initial lines
        estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
        estimated_pages = estimated_lines / TARGET_LINES_PER_PAGE
        metadata["estimated_lines_before"] = estimated_lines
        metadata["estimated_pages_before"] = estimated_pages
        
        logger.info(f"Initial length estimate: {estimated_lines} lines (~{estimated_pages:.1f} pages)")
        
        max_total_lines = TARGET_LINES_PER_PAGE * max_pages
        
        # If already within budget, return early
        if estimated_lines <= max_total_lines:
            logger.info("Content already within length budget, no trimming needed")
            metadata["estimated_lines_after"] = estimated_lines
            metadata["estimated_pages_after"] = estimated_pages
            return metadata
        
        # Trimming strategy: trim in priority order until within budget
        original_estimated = estimated_lines
        
        # 1. Truncate summary if too long
        if summary:
            words = summary.split()
            if len(words) > MAX_SUMMARY_WORDS:
                truncated_summary, words_removed = truncate_summary(summary, MAX_SUMMARY_WORDS)
                summary = truncated_summary
                metadata["trimmed_summary_words"] = words_removed
                logger.info(f"Truncated summary from {len(words)} to {MAX_SUMMARY_WORDS} words")
                # Update estimate
                estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
                if estimated_lines <= max_total_lines:
                    metadata["estimated_lines_after"] = estimated_lines
                    metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                    # Save trimmed summary
                    summary_data['summary'] = summary
                    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    # Also save other files (they may have been modified in-place)
                    exp_data['selected_experiences'] = experiences
                    experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    skills_data['skills'] = skills
                    if 'selected_skills' in skills_data:
                        skills_data['selected_skills'] = skills
                    skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    return metadata
        
        # 2. Trim experience bullets first (keep first N bullets, truncate longest if needed)
        for exp in experiences:
            bullets = exp.get('bullets', [])
            if len(bullets) > MAX_EXPERIENCE_BULLETS:
                original_bullet_count = len(bullets)
                # Keep first N bullets (assumed already ordered by importance)
                exp['bullets'] = bullets[:MAX_EXPERIENCE_BULLETS]
                removed = original_bullet_count - len(exp['bullets'])
                metadata["trimmed_experience_bullets"] += removed
                logger.info(f"Truncated experience '{exp.get('title', 'Unknown')}' bullets from {original_bullet_count} to {MAX_EXPERIENCE_BULLETS}")
                estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
                if estimated_lines <= max_total_lines:
                    # Save all files and return early
                    if summary != summary_data.get('summary', ''):
                        summary_data['summary'] = summary
                        summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    exp_data['selected_experiences'] = experiences
                    experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    skills_data['skills'] = skills
                    if 'selected_skills' in skills_data:
                        skills_data['selected_skills'] = skills
                    skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    if projects_path and projects_path.exists() and proj_data is not None:
                        proj_data['selected_projects'] = projects
                        projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    metadata["estimated_lines_after"] = estimated_lines
                    metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                    return metadata
        
        # 3. Trim project bullets
        for proj in projects:
            bullets = proj.get('bullets', [])
            if len(bullets) > MAX_PROJECT_BULLETS:
                original_bullet_count = len(bullets)
                truncated_bullets, removed = truncate_bullets(bullets, MAX_PROJECT_BULLETS)
                proj['bullets'] = truncated_bullets
                metadata["trimmed_project_bullets"] += removed
                logger.info(f"Truncated project '{proj.get('name', 'Unknown')}' bullets from {original_bullet_count} to {MAX_PROJECT_BULLETS}")
                estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
                if estimated_lines <= max_total_lines:
                    # Save all files and return early
                    if summary != summary_data.get('summary', ''):
                        summary_data['summary'] = summary
                        summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    exp_data['selected_experiences'] = experiences
                    experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    skills_data['skills'] = skills
                    if 'selected_skills' in skills_data:
                        skills_data['selected_skills'] = skills
                    skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    if projects_path and projects_path.exists() and proj_data is not None:
                        proj_data['selected_projects'] = projects
                        projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    metadata["estimated_lines_after"] = estimated_lines
                    metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                    return metadata
        
        # 4. Trim experiences list (keep highest priority, or first N if no priority)
        if len(experiences) > MAX_EXPERIENCES:
            original_count = len(experiences)
            # Sort by priority if available (lower priority number = higher priority)
            sort_key = lambda exp: exp.get('priority', 999) if isinstance(exp.get('priority'), (int, float)) else 999
            truncated_experiences, removed = truncate_list(experiences, MAX_EXPERIENCES, sort_key)
            experiences = truncated_experiences
            metadata["trimmed_experiences"] = removed
            logger.info(f"Truncated experiences from {original_count} to {MAX_EXPERIENCES}")
            estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
            if estimated_lines <= max_total_lines:
                metadata["estimated_lines_after"] = estimated_lines
                metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                # Save all modified files
                if summary != summary_data.get('summary', ''):
                    summary_data['summary'] = summary
                    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                exp_data['selected_experiences'] = experiences
                experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                skills_data['skills'] = skills
                if 'selected_skills' in skills_data:
                    skills_data['selected_skills'] = skills
                skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                if projects_path and projects_path.exists() and proj_data is not None:
                    proj_data['selected_projects'] = projects
                    projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
                return metadata
        
        # 5. Trim projects list
        if projects and len(projects) > MAX_PROJECTS:
            original_count = len(projects)
            sort_key = lambda proj: proj.get('priority', 999) if isinstance(proj.get('priority'), (int, float)) else 999
            truncated_projects, removed = truncate_list(projects, MAX_PROJECTS, sort_key)
            projects = truncated_projects
            metadata["trimmed_projects"] = removed
            logger.info(f"Truncated projects from {original_count} to {MAX_PROJECTS}")
            estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
            if estimated_lines <= max_total_lines:
                metadata["estimated_lines_after"] = estimated_lines
                metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                # Save all modified files
                if summary != summary_data.get('summary', ''):
                    summary_data['summary'] = summary
                    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                exp_data['selected_experiences'] = experiences
                experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                skills_data['skills'] = skills
                if 'selected_skills' in skills_data:
                    skills_data['selected_skills'] = skills
                skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                if projects_path and projects_path.exists() and proj_data is not None:
                    proj_data['selected_projects'] = projects
                    projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
                return metadata
        
        # 6. Trim skills list
        if len(skills) > MAX_SKILLS:
            original_count = len(skills)
            truncated_skills, removed = truncate_list(skills, MAX_SKILLS)
            skills = truncated_skills
            metadata["trimmed_skills"] = removed
            logger.info(f"Truncated skills from {original_count} to {MAX_SKILLS}")
            estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
            if estimated_lines <= max_total_lines:
                metadata["estimated_lines_after"] = estimated_lines
                metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
                # Save all modified files
                if summary != summary_data.get('summary', ''):
                    summary_data['summary'] = summary
                    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
                exp_data['selected_experiences'] = experiences
                experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
                skills_data['skills'] = skills
                if 'selected_skills' in skills_data:
                    skills_data['selected_skills'] = skills
                skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
                if projects_path and projects_path.exists() and proj_data is not None:
                    proj_data['selected_projects'] = projects
                    projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
                if education_path and education_path.exists() and edu_data is not None:
                    edu_data['education'] = education
                    education_path.write_text(json.dumps(edu_data, indent=2, ensure_ascii=False), encoding='utf-8')
                return metadata
        
        # 7. Trim education list
        if education and len(education) > MAX_EDUCATION_ENTRIES:
            original_count = len(education)
            truncated_education, removed = truncate_list(education, MAX_EDUCATION_ENTRIES)
            education = truncated_education
            metadata["trimmed_education"] = removed
            logger.info(f"Truncated education from {original_count} to {MAX_EDUCATION_ENTRIES}")
            estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
        
        # Final estimate after standard trimming
        estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
        metadata["estimated_lines_after"] = estimated_lines
        metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
        
        # If still over budget after all trimming, apply aggressive final pass
        # Apply aggressive trimming if estimated pages > max_pages OR if we're close (within 0.2 pages)
        if metadata["estimated_pages_after"] > max_pages or metadata["estimated_pages_after"] > (max_pages - 0.2):
            logger.warning(f"⚠️ Content exceeds or is close to {max_pages}-page budget: {metadata['estimated_pages_after']:.1f} pages")
            logger.info("Applying aggressive final trimming pass to ensure ≤2 pages...")
            
            # Aggressive: Keep only top 2 experiences, 1 project, max 1 bullet each
            if len(experiences) > 2:
                original_count = len(experiences)
                logger.info(f"Aggressively reducing experiences from {original_count} to 2")
                experiences = experiences[:2]
                metadata["trimmed_experiences"] += original_count - 2
            
            if projects and len(projects) > 1:
                original_proj_count = len(projects)
                logger.info(f"Aggressively reducing projects from {original_proj_count} to 1")
                projects = projects[:1]
                metadata["trimmed_projects"] += original_proj_count - 1
            
            # Reduce all bullets to 1
            for exp in experiences:
                bullets = exp.get('bullets', [])
                if len(bullets) > 1:
                    removed = len(bullets) - 1
                    exp['bullets'] = bullets[:1]
                    metadata["trimmed_experience_bullets"] += removed
                    logger.info(f"Aggressively reducing experience '{exp.get('title', 'Unknown')}' bullets to 1")
            
            for proj in projects:
                bullets = proj.get('bullets', [])
                if len(bullets) > 1:
                    removed = len(bullets) - 1
                    proj['bullets'] = bullets[:1]
                    metadata["trimmed_project_bullets"] += removed
                    logger.info(f"Aggressively reducing project '{proj.get('name', 'Unknown')}' bullets to 1")
            
            # Aggressively trim skills if still over (reduce to 10 for more aggressive trimming)
            if len(skills) > 10:
                original_skill_count = len(skills)
                skills = skills[:10]
                metadata["trimmed_skills"] += original_skill_count - 10
                logger.info(f"Aggressively reducing skills from {original_skill_count} to 10")
            
            # Aggressively trim summary if still over (reduce to 50 words)
            if summary:
                words = summary.split()
                if len(words) > 50:
                    truncated_summary, words_removed = truncate_summary(summary, 50)
                    summary = truncated_summary
                    metadata["trimmed_summary_words"] += words_removed
                    logger.info(f"Aggressively reducing summary from {len(words)} to 50 words")
            
            # Aggressively trim education if still over (keep only 1 entry)
            if education and len(education) > 1:
                original_edu_count = len(education)
                education = education[:1]
                metadata["trimmed_education"] += original_edu_count - 1
                logger.info(f"Aggressively reducing education from {original_edu_count} to 1")
            
            # Re-estimate after aggressive trimming
            estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
            metadata["estimated_lines_after"] = estimated_lines
            metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
            logger.info(f"After aggressive trimming: {estimated_lines} lines (~{metadata['estimated_pages_after']:.1f} pages)")
            
            # If STILL over budget after aggressive trimming, apply ultra-aggressive measures
            if metadata["estimated_pages_after"] > max_pages:
                logger.warning(f"⚠️ Still over budget after aggressive trimming ({metadata['estimated_pages_after']:.1f} pages), applying ultra-aggressive measures...")
                
                # Ultra-aggressive: Keep only top 1 experience, 0 projects, max 1 bullet
                if len(experiences) > 1:
                    original_count = len(experiences)
                    logger.info(f"Ultra-aggressively reducing experiences from {original_count} to 1")
                    experiences = experiences[:1]
                    metadata["trimmed_experiences"] += original_count - 1
                
                # Remove all projects
                if projects:
                    original_proj_count = len(projects)
                    logger.info(f"Ultra-aggressively removing all {original_proj_count} projects")
                    projects = []
                    metadata["trimmed_projects"] += original_proj_count
                
                # Reduce skills to 8
                if len(skills) > 8:
                    original_skill_count = len(skills)
                    skills = skills[:8]
                    metadata["trimmed_skills"] += original_skill_count - 8
                    logger.info(f"Ultra-aggressively reducing skills from {original_skill_count} to 8")
                
                # Reduce summary to 40 words
                if summary:
                    words = summary.split()
                    if len(words) > 40:
                        truncated_summary, words_removed = truncate_summary(summary, 40)
                        summary = truncated_summary
                        metadata["trimmed_summary_words"] += words_removed
                        logger.info(f"Ultra-aggressively reducing summary from {len(words)} to 40 words")
                
                # Final re-estimate
                estimated_lines = estimate_lines(summary, experiences, projects, skills, education)
                metadata["estimated_lines_after"] = estimated_lines
                metadata["estimated_pages_after"] = estimated_lines / TARGET_LINES_PER_PAGE
            
            # Save aggressively trimmed files
            if summary != summary_data.get('summary', ''):
                summary_data['summary'] = summary
                summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            exp_data['selected_experiences'] = experiences
            experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            skills_data['skills'] = skills
            if 'selected_skills' in skills_data:
                skills_data['selected_skills'] = skills
            skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            if projects_path and projects_path.exists() and proj_data is not None:
                proj_data['selected_projects'] = projects
                projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            if education_path and education_path.exists() and edu_data is not None:
                edu_data['education'] = education
                education_path.write_text(json.dumps(edu_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
            if metadata["estimated_pages_after"] > max_pages:
                logger.warning(f"⚠️ Resume still exceeds {max_pages}-page budget after ultra-aggressive trimming: {metadata['estimated_pages_after']:.1f} pages")
            else:
                logger.info(f"✅ Ultra-aggressive trimming successful: {metadata['estimated_pages_after']:.1f} pages (within {max_pages}-page limit)")
        else:
            # Aggressive trimming was sufficient
            logger.info(f"✅ Aggressive trimming successful: {metadata['estimated_pages_after']:.1f} pages (within {max_pages}-page limit)")
        
        logger.info(f"Final length estimate: {estimated_lines} lines (~{metadata['estimated_pages_after']:.1f} pages)")
        
        # Save all modified JSON files
        if summary != summary_data.get('summary', ''):
            summary_data['summary'] = summary
            summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        exp_data['selected_experiences'] = experiences
        experience_path.write_text(json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        skills_data['skills'] = skills
        if 'selected_skills' in skills_data:
            skills_data['selected_skills'] = skills
        skills_path.write_text(json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        if projects_path and projects_path.exists() and proj_data is not None:
            proj_data['selected_projects'] = projects
            projects_path.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        if education_path and education_path.exists() and edu_data is not None:
            edu_data['education'] = education
            education_path.write_text(json.dumps(edu_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error enforcing length budget: {e}", exc_info=True)
        # Return metadata with zeros - don't break the pipeline
        return metadata


def format_trimming_summary(metadata: Dict[str, Any]) -> str:
    """
    Format trimming metadata into a user-friendly summary string.
    
    Args:
        metadata: Trimming metadata from enforce_length_budget_on_json_files
        
    Returns:
        Formatted summary string
    """
    parts = []
    
    if metadata.get("trimmed_experiences", 0) > 0:
        parts.append(f"Experiences: {metadata['trimmed_experiences']} removed")
    
    if metadata.get("trimmed_experience_bullets", 0) > 0:
        parts.append(f"Experience bullets: {metadata['trimmed_experience_bullets']} removed")
    
    if metadata.get("trimmed_projects", 0) > 0:
        parts.append(f"Projects: {metadata['trimmed_projects']} removed")
    
    if metadata.get("trimmed_project_bullets", 0) > 0:
        parts.append(f"Project bullets: {metadata['trimmed_project_bullets']} removed")
    
    if metadata.get("trimmed_skills", 0) > 0:
        parts.append(f"Skills: {metadata['trimmed_skills']} removed")
    
    if metadata.get("trimmed_summary_words", 0) > 0:
        parts.append(f"Summary: {metadata['trimmed_summary_words']} words removed")
    
    if metadata.get("trimmed_education", 0) > 0:
        parts.append(f"Education: {metadata['trimmed_education']} entries removed")
    
    if parts:
        before_pages = metadata.get("estimated_pages_before", 0)
        after_pages = metadata.get("estimated_pages_after", 0)
        summary = f"Applied length guard (target: ≤{MAX_PAGES} pages):\n"
        summary += " – " + "\n – ".join(parts)
        summary += f"\nEstimated pages: {before_pages:.1f} → {after_pages:.1f}"
        return summary
    
    return ""

