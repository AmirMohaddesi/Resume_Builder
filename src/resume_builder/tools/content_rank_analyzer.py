"""
Content Rank Analyzer Tool

Analyzes resume content and ranks items by importance, providing suggestions
on what to remove to fit within a 2-page limit.
"""

from __future__ import annotations

import json
import logging
from typing import Type, List, Dict, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ContentRankAnalyzerInput(BaseModel):
    """Input schema for ContentRankAnalyzerTool."""
    experiences_path: str = Field(..., description="Path to selected_experiences.json")
    projects_path: Optional[str] = Field(default=None, description="Path to selected_projects.json")
    skills_path: str = Field(..., description="Path to selected_skills.json")
    summary_path: str = Field(..., description="Path to summary.json")
    education_path: Optional[str] = Field(default=None, description="Path to education.json")
    jd_path: str = Field(..., description="Path to parsed_jd.json for relevance scoring")
    estimated_pages: float = Field(..., description="Current estimated page count")
    target_pages: float = Field(default=2.0, description="Target page count (default: 2.0)")
    model_config = ConfigDict(extra="ignore")


class ContentRankAnalyzerTool(BaseTool):
    """
    Analyzes resume content and ranks items by importance.
    
    Provides ranked suggestions on what to remove to fit within page budget.
    Ranks experiences, projects, bullets, and skills by:
    - Relevance to job description
    - Impact/achievements
    - Recency
    - Uniqueness
    """
    name: str = "content_rank_analyzer"
    description: str = (
        "Analyze resume content and rank items by importance. "
        "Provides suggestions on what to remove to fit within 2-page limit. "
        "Ranks experiences, projects, bullets, and skills by relevance, impact, and recency. "
        "Use this when resume exceeds page budget to get intelligent removal suggestions."
    )
    args_schema: Type[BaseModel] = ContentRankAnalyzerInput

    def _run(
        self,
        experiences_path: str,
        skills_path: str,
        summary_path: str,
        jd_path: str,
        projects_path: Optional[str] = None,
        education_path: Optional[str] = None,
        estimated_pages: float = 2.0,
        target_pages: float = 2.0
    ) -> str:
        """
        Analyze content and provide ranked removal suggestions.
        
        Returns JSON with:
        - ranked_experiences: List of experiences ranked by importance
        - ranked_projects: List of projects ranked by importance
        - ranked_bullets: List of bullets (with parent context) ranked by importance
        - ranked_skills: List of skills ranked by importance
        - removal_suggestions: Prioritized list of what to remove
        """
        try:
            from pathlib import Path
            from resume_builder.paths import OUTPUT_DIR
            from resume_builder.json_loaders import (
                load_selected_experiences,
                load_selected_skills,
                load_summary_block,
                load_selected_projects,
                load_education_block
            )
            
            # Resolve paths
            base_dir = OUTPUT_DIR
            exp_path = base_dir / experiences_path if not Path(experiences_path).is_absolute() else Path(experiences_path)
            skills_file = base_dir / skills_path if not Path(skills_path).is_absolute() else Path(skills_path)
            summary_file = base_dir / summary_path if not Path(summary_path).is_absolute() else Path(summary_path)
            jd_file = base_dir / jd_path if not Path(jd_path).is_absolute() else Path(jd_path)
            
            # Load JSON files
            exp_data = load_selected_experiences(exp_path)
            experiences = exp_data.get('selected_experiences', [])
            
            skills_data = load_selected_skills(skills_file)
            skills = skills_data.get('skills', [])
            
            summary_data = load_summary_block(summary_file)
            summary = summary_data.get('summary', '')
            
            # Load JD for relevance scoring
            try:
                jd_content = Path(jd_file).read_text(encoding='utf-8')
                jd_json = json.loads(jd_content)
                jd_keywords = jd_json.get('keywords', [])
                jd_skills = jd_json.get('skills', [])
            except Exception as e:
                logger.warning(f"Could not load JD for ranking: {e}")
                jd_keywords = []
                jd_skills = []
            
            projects = []
            if projects_path:
                proj_file = base_dir / projects_path if not Path(projects_path).is_absolute() else Path(projects_path)
                if proj_file.exists():
                    proj_data = load_selected_projects(proj_file)
                    projects = proj_data.get('selected_projects', [])
            
            education = []
            if education_path:
                edu_file = base_dir / education_path if not Path(education_path).is_absolute() else Path(education_path)
                if edu_file.exists():
                    edu_data = load_education_block(edu_file)
                    education = edu_data.get('education', [])
            
            # Get LLM client
            try:
                from openai import OpenAI
                client = OpenAI()
            except ImportError:
                logger.error("OpenAI client not available")
                return json.dumps({
                    "status": "error",
                    "message": "OpenAI client not available",
                    "rankings": {}
                })
            
            import os
            model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
            
            # Build concise, fast analysis prompt
            pages_over = estimated_pages - target_pages
            
            # Truncate JD keywords/skills for speed
            jd_kw_str = ', '.join(jd_keywords[:8]) if jd_keywords else "N/A"
            jd_skills_str = ', '.join(jd_skills[:8]) if jd_skills else "N/A"
            
            # Build minimal content list (just titles/names, no full descriptions)
            exp_list = [f"{i}:{exp.get('title', 'Unknown')[:40]}" for i, exp in enumerate(experiences)]
            proj_list = [f"{i}:{proj.get('name', 'Unknown')[:40]}" for i, proj in enumerate(projects)]
            skills_list = skills[:15]  # Limit to 15 skills
            
            prompt = f"""Resume: {estimated_pages:.1f} pages, target: {target_pages} ({pages_over:.1f} over). Rank items by JD relevance, impact, recency. Mark lowest priority for removal.

JD Keywords: {jd_kw_str}
JD Skills: {jd_skills_str}

Content:
Exp: {', '.join(exp_list) if exp_list else 'None'}
Proj: {', '.join(proj_list) if proj_list else 'None'}
Skills: {', '.join(skills_list)}

Return JSON:
{{
  "ranked_skills": [{{"skill": "X", "priority_score": 0-100, "suggest_remove": true/false, "reason": "..."}}],
  "ranked_experiences": [{{"index": 0, "title": "...", "priority_score": 0-100, "suggest_remove": true/false}}],
  "ranked_projects": [{{"index": 0, "name": "...", "priority_score": 0-100, "suggest_remove": true/false}}],
  "removal_suggestions": [{{"type": "skill|experience|project", "index": 0, "reason": "...", "estimated_savings_lines": 1-8}}]
}}

Focus on removal_suggestions: list items to remove (lowest priority first). Keep it short."""

            # Use faster model for ranking (gpt-4o-mini is already fast, but reduce tokens)
            # Force faster response by using shorter system message and lower max_tokens
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Resume optimizer. Rank items by JD relevance. Suggest removals."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=1000,  # Limit response size for speed
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            
            rankings = json.loads(result_text)
            
            # Ensure removal_suggestions list exists
            if "removal_suggestions" not in rankings:
                rankings["removal_suggestions"] = []
            
            # If no removal suggestions but we're over budget, generate fallback suggestions
            if not rankings.get("removal_suggestions") and estimated_pages > target_pages:
                logger.warning("LLM did not generate removal suggestions, creating fallback suggestions")
                
                # Fallback: Extract from ranked items with suggest_remove=True
                removal_suggestions = []
                
                # Skills (easiest to remove, least impact)
                ranked_skills = rankings.get("ranked_skills", [])
                for skill in ranked_skills:
                    if skill.get("suggest_remove", False):
                        skill_index = ranked_skills.index(skill)
                        removal_suggestions.append({
                            "type": "skill",
                            "index": skill_index,
                            "skill": skill.get("skill", "Unknown"),
                            "reason": skill.get("reason", "Low priority"),
                            "estimated_savings_lines": 1
                        })
                
                # Bullets (moderate impact)
                ranked_bullets = rankings.get("ranked_bullets", [])
                for bullet in ranked_bullets:
                    if bullet.get("suggest_remove", False):
                        removal_suggestions.append({
                            "type": "bullet",
                            "item_index": bullet.get("parent_index", -1),
                            "bullet_index": bullet.get("bullet_index", -1),
                            "text": bullet.get("text", "Unknown")[:50],
                            "reason": bullet.get("reason", "Low priority"),
                            "estimated_savings_lines": 2
                        })
                
                # Projects (higher impact)
                ranked_projects = rankings.get("ranked_projects", [])
                for proj in ranked_projects:
                    if proj.get("suggest_remove", False):
                        removal_suggestions.append({
                            "type": "project",
                            "index": proj.get("index", -1),
                            "name": proj.get("name", "Unknown"),
                            "reason": proj.get("reason", "Low priority"),
                            "estimated_savings_lines": 6
                        })
                
                # Experiences (highest impact, last resort)
                ranked_experiences = rankings.get("ranked_experiences", [])
                for exp in ranked_experiences:
                    if exp.get("suggest_remove", False):
                        removal_suggestions.append({
                            "type": "experience",
                            "index": exp.get("index", -1),
                            "title": exp.get("title", "Unknown"),
                            "reason": exp.get("reason", "Low priority"),
                            "estimated_savings_lines": 8
                        })
                
                # If still no suggestions, create aggressive fallback (remove items to meet target)
                if not removal_suggestions:
                    # Calculate how much we need to remove
                    from resume_builder.length_budget import TARGET_LINES_PER_PAGE
                    lines_to_remove = int((estimated_pages - target_pages) * TARGET_LINES_PER_PAGE)
                    
                    # Priority: skills (easiest), then projects, then experience bullets, then summary
                    if len(skills) > 5:  # Keep at least 5 skills
                        # Remove multiple skills
                        skills_to_remove = min(len(skills) - 5, max(1, lines_to_remove))
                        for i in range(skills_to_remove):
                            removal_suggestions.append({
                                "type": "skill",
                                "index": len(skills) - 1 - i,
                                "skill": skills[len(skills) - 1 - i] if isinstance(skills[len(skills) - 1 - i], str) else "Unknown",
                                "reason": f"Fallback: remove skill to reduce pages (need {lines_to_remove} lines)",
                                "estimated_savings_lines": 1
                            })
                    elif projects and len(projects) > 0:
                        # Remove projects
                        for i, proj in enumerate(projects):
                            if len(removal_suggestions) >= 3:  # Limit to 3 at a time
                                break
                            removal_suggestions.append({
                                "type": "project",
                                "index": i,
                                "name": proj.get('name', 'Unknown'),
                                "reason": f"Fallback: remove project to reduce pages",
                                "estimated_savings_lines": 6
                            })
                    elif experiences:
                        # Remove bullets from experiences
                        for exp_idx, exp in enumerate(experiences):
                            bullets = exp.get('bullets', [])
                            if len(bullets) > 2:  # Keep at least 2 bullets
                                for bullet_idx in range(len(bullets) - 1, 1, -1):  # Remove from end, keep first 2
                                    if len(removal_suggestions) >= 3:
                                        break
                                    removal_suggestions.append({
                                        "type": "bullet",
                                        "item_index": exp_idx,
                                        "bullet_index": bullet_idx,
                                        "text": bullets[bullet_idx][:50] if isinstance(bullets[bullet_idx], str) else "Unknown",
                                        "reason": f"Fallback: remove bullet to reduce pages",
                                        "estimated_savings_lines": 2
                                    })
                                if len(removal_suggestions) >= 3:
                                    break
                    elif summary and len(summary.split()) > 50:  # Remove summary words if everything else is minimal
                        words_to_remove = min(20, len(summary.split()) - 50)
                        removal_suggestions.append({
                            "type": "summary_words",
                            "words_to_remove": words_to_remove,
                            "reason": "Fallback: reduce summary length",
                            "estimated_savings_lines": max(1, words_to_remove // 8)
                        })
                
                rankings["removal_suggestions"] = removal_suggestions
                logger.info(f"Generated {len(removal_suggestions)} fallback removal suggestions")
            
            # Add metadata
            rankings["status"] = "success"
            rankings["estimated_pages"] = estimated_pages
            rankings["target_pages"] = target_pages
            rankings["pages_over_budget"] = pages_over
            rankings["message"] = f"Content ranked. {len(rankings.get('removal_suggestions', []))} removal suggestions provided."
            
            logger.info(f"Content ranking completed: {len(rankings.get('removal_suggestions', []))} removal suggestions")
            
            return json.dumps(rankings, indent=2)
            
        except Exception as e:
            logger.error(f"Content rank analyzer failed: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e),
                "rankings": {}
            })

