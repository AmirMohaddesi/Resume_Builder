"""
Content Removal Tool

Removes specific content from JSON files based on priority rankings.
Used iteratively to reduce resume length until it fits within page budget.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR
from resume_builder.json_loaders import (
    load_selected_experiences,
    load_selected_skills,
    load_selected_projects,
    load_summary_block,
    load_education_block
)

logger = get_logger("content_removal_tool")


class ContentRemovalInput(BaseModel):
    """Input schema for ContentRemovalTool."""
    removal_type: str = Field(..., description="Type of removal: 'experience', 'project', 'skill', 'bullet', 'summary_words'")
    target_index: Optional[int] = Field(None, description="Index of item to remove (for lists)")
    parent_index: Optional[int] = Field(None, description="Parent index (for bullets within experiences/projects)")
    bullet_index: Optional[int] = Field(None, description="Bullet index within parent (for bullet removal)")
    words_to_remove: Optional[int] = Field(None, description="Number of words to remove from summary")
    
    model_config = ConfigDict(extra="ignore")


class ContentRemovalTool(BaseTool):
    """
    Removes specific content from JSON files to reduce resume length.
    Used iteratively by agents to remove least important content until page budget is met.
    """
    name: str = "content_removal_tool"
    description: str = (
        "Removes specific content from resume JSON files based on priority rankings. "
        "Use this tool iteratively to remove least important content until the resume fits within 2 pages. "
        "Supports removing: experiences, projects, skills, bullets, and summary words."
    )
    args_schema: Type[BaseModel] = ContentRemovalInput

    def _run(
        self,
        removal_type: str,
        target_index: Optional[int] = None,
        parent_index: Optional[int] = None,
        bullet_index: Optional[int] = None,
        words_to_remove: Optional[int] = None
    ) -> str:
        """
        Remove content from JSON files.
        
        Args:
            removal_type: 'experience', 'project', 'skill', 'bullet', 'summary_words'
            target_index: Index of item to remove (for experiences, projects, skills)
            parent_index: Parent index (for bullets within experiences/projects)
            bullet_index: Bullet index within parent
            words_to_remove: Number of words to remove from summary
        """
        try:
            removal_type = removal_type.lower()
            
            if removal_type == "experience":
                if target_index is None:
                    return json.dumps({"status": "error", "message": "target_index required for experience removal"})
                
                exp_data = load_selected_experiences(OUTPUT_DIR / "selected_experiences.json")
                experiences = exp_data.get('selected_experiences', [])
                
                if target_index >= len(experiences):
                    return json.dumps({"status": "error", "message": f"Invalid experience index: {target_index}"})
                
                removed_exp = experiences.pop(target_index)
                exp_data['selected_experiences'] = experiences
                (OUTPUT_DIR / "selected_experiences.json").write_text(
                    json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8'
                )
                
                logger.info(f"Removed experience at index {target_index}: {removed_exp.get('title', 'Unknown')}")
                return json.dumps({
                    "status": "success",
                    "message": f"Removed experience: {removed_exp.get('title', 'Unknown')}",
                    "removed_item": removed_exp.get('title', 'Unknown'),
                    "estimated_savings_lines": 8
                })
            
            elif removal_type == "project":
                if target_index is None:
                    return json.dumps({"status": "error", "message": "target_index required for project removal"})
                
                proj_data = load_selected_projects(OUTPUT_DIR / "selected_projects.json")
                projects = proj_data.get('selected_projects', [])
                
                if target_index >= len(projects):
                    return json.dumps({"status": "error", "message": f"Invalid project index: {target_index}"})
                
                removed_proj = projects.pop(target_index)
                proj_data['selected_projects'] = projects
                (OUTPUT_DIR / "selected_projects.json").write_text(
                    json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8'
                )
                
                logger.info(f"Removed project at index {target_index}: {removed_proj.get('name', 'Unknown')}")
                return json.dumps({
                    "status": "success",
                    "message": f"Removed project: {removed_proj.get('name', 'Unknown')}",
                    "removed_item": removed_proj.get('name', 'Unknown'),
                    "estimated_savings_lines": 6
                })
            
            elif removal_type == "skill":
                if target_index is None:
                    return json.dumps({"status": "error", "message": "target_index required for skill removal"})
                
                skills_data = load_selected_skills(OUTPUT_DIR / "selected_skills.json")
                skills = skills_data.get('skills', skills_data.get('selected_skills', []))
                
                if target_index >= len(skills):
                    return json.dumps({"status": "error", "message": f"Invalid skill index: {target_index}"})
                
                removed_skill = skills.pop(target_index)
                skills_data['skills'] = skills
                if 'selected_skills' in skills_data:
                    skills_data['selected_skills'] = skills
                # Ensure we write the updated skills list
                skills_path = OUTPUT_DIR / "selected_skills.json"
                skills_path.write_text(
                    json.dumps(skills_data, indent=2, ensure_ascii=False), encoding='utf-8'
                )
                logger.debug(f"Saved updated skills to {skills_path}: {len(skills)} skills remaining")
                
                logger.info(f"Removed skill at index {target_index}: {removed_skill}")
                return json.dumps({
                    "status": "success",
                    "message": f"Removed skill: {removed_skill}",
                    "removed_item": removed_skill,
                    "estimated_savings_lines": 1
                })
            
            elif removal_type == "bullet":
                if parent_index is None or bullet_index is None:
                    return json.dumps({"status": "error", "message": "parent_index and bullet_index required for bullet removal"})
                
                # Try experience first
                exp_data = load_selected_experiences(OUTPUT_DIR / "selected_experiences.json")
                experiences = exp_data.get('selected_experiences', [])
                
                if parent_index < len(experiences):
                    exp = experiences[parent_index]
                    bullets = exp.get('bullets', [])
                    if bullet_index < len(bullets):
                        removed_bullet = bullets.pop(bullet_index)
                        exp['bullets'] = bullets
                        exp_data['selected_experiences'] = experiences
                        (OUTPUT_DIR / "selected_experiences.json").write_text(
                            json.dumps(exp_data, indent=2, ensure_ascii=False), encoding='utf-8'
                        )
                        logger.info(f"Removed bullet {bullet_index} from experience {parent_index}")
                        return json.dumps({
                            "status": "success",
                            "message": f"Removed bullet from experience: {exp.get('title', 'Unknown')}",
                            "removed_item": removed_bullet[:50] + "..." if len(removed_bullet) > 50 else removed_bullet,
                            "estimated_savings_lines": 2
                        })
                
                # Try projects
                proj_data = load_selected_projects(OUTPUT_DIR / "selected_projects.json")
                projects = proj_data.get('selected_projects', [])
                
                if parent_index < len(projects):
                    proj = projects[parent_index]
                    bullets = proj.get('bullets', [])
                    if bullet_index < len(bullets):
                        removed_bullet = bullets.pop(bullet_index)
                        proj['bullets'] = bullets
                        proj_data['selected_projects'] = projects
                        (OUTPUT_DIR / "selected_projects.json").write_text(
                            json.dumps(proj_data, indent=2, ensure_ascii=False), encoding='utf-8'
                        )
                        logger.info(f"Removed bullet {bullet_index} from project {parent_index}")
                        return json.dumps({
                            "status": "success",
                            "message": f"Removed bullet from project: {proj.get('name', 'Unknown')}",
                            "removed_item": removed_bullet[:50] + "..." if len(removed_bullet) > 50 else removed_bullet,
                            "estimated_savings_lines": 2
                        })
                
                return json.dumps({"status": "error", "message": f"Invalid parent_index or bullet_index"})
            
            elif removal_type == "summary_words":
                if words_to_remove is None or words_to_remove <= 0:
                    return json.dumps({"status": "error", "message": "words_to_remove must be > 0"})
                
                summary_data = load_summary_block(OUTPUT_DIR / "summary.json")
                summary = summary_data.get('summary', '')
                words = summary.split()
                
                if len(words) <= words_to_remove:
                    return json.dumps({"status": "error", "message": f"Cannot remove {words_to_remove} words from {len(words)} word summary"})
                
                new_words = words[:-words_to_remove]
                summary_data['summary'] = ' '.join(new_words)
                (OUTPUT_DIR / "summary.json").write_text(
                    json.dumps(summary_data, indent=2, ensure_ascii=False), encoding='utf-8'
                )
                
                logger.info(f"Removed {words_to_remove} words from summary")
                return json.dumps({
                    "status": "success",
                    "message": f"Removed {words_to_remove} words from summary",
                    "estimated_savings_lines": max(1, words_to_remove // 8)
                })
            
            else:
                return json.dumps({"status": "error", "message": f"Unknown removal_type: {removal_type}"})
                
        except Exception as e:
            logger.error(f"Error in ContentRemovalTool: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to remove content: {str(e)}"
            })

