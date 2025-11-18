"""LLM-powered tool to intelligently summarize project bullet points."""
from __future__ import annotations

import json
import logging
from typing import Type, List, Dict, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ProjectSummarizerInput(BaseModel):
    """Input schema for ProjectSummarizerTool."""
    bullets: List[str] = Field(..., description="List of raw project bullet points to summarize")
    jd_keywords: Optional[List[str]] = Field(default=None, description="Job description keywords for alignment")
    max_bullets: int = Field(default=3, description="Maximum number of bullets to return (default: 3)")
    max_words_per_bullet: int = Field(default=25, description="Maximum words per bullet (default: 25)")
    model_config = ConfigDict(extra="ignore")


class ProjectSummarizerTool(BaseTool):
    """Intelligently summarize project bullet points using LLM.
    
    This tool condenses project bullets while preserving:
    - Quantifiable impact and achievements
    - Technologies and skills mentioned in JD
    - Key technical details
    - Action-oriented language
    
    Returns 2-3 condensed bullets that are concise but impactful.
    """
    name: str = "project_summarizer"
    description: str = (
        "Intelligently summarize project bullet points to fit within 1-2 page resume constraints. "
        "Preserves impact, technical details, and JD-relevant information while condensing to 2-3 bullets "
        "with ~20-25 words each. Use this to refine project descriptions before writing to selected_projects.json."
    )
    args_schema: Type[BaseModel] = ProjectSummarizerInput

    def _run(
        self,
        bullets: List[str],
        jd_keywords: Optional[List[str]] = None,
        max_bullets: int = 3,
        max_words_per_bullet: int = 25
    ) -> str:
        """Summarize project bullets using LLM."""
        try:
            if not bullets:
                return json.dumps({"status": "error", "message": "No bullets provided", "summarized_bullets": []})
            
            # Get LLM client
            try:
                from openai import OpenAI
                client = OpenAI()
            except ImportError:
                logger.error("OpenAI client not available")
                return json.dumps({"status": "error", "message": "OpenAI client not available", "summarized_bullets": bullets})
            
            # Get model from environment
            import os
            model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
            
            # Build prompt
            bullets_text = "\n".join(f"- {bullet}" for bullet in bullets)
            jd_context = ""
            if jd_keywords:
                jd_context = f"\n\nJob Description Keywords: {', '.join(jd_keywords[:10])}"
            
            # Determine target count (never exceed input count)
            target_count = min(max_bullets, len(bullets))
            
            prompt = f"""You are CONDENSING project bullet points for a resume. Your goal is to REDUCE {len(bullets)} bullet points to {target_count} concise, impactful bullets.

CRITICAL: You must return FEWER or EQUAL bullets than the input. Do NOT expand or add new bullets.

Original bullets ({len(bullets)} total):
{bullets_text}{jd_context}

Requirements:
- Return EXACTLY {target_count} bullets (NEVER more than {len(bullets)})
- Each bullet: maximum {max_words_per_bullet} words
- CONDENSE by merging related points, removing redundancy
- Preserve quantifiable achievements (numbers, percentages, metrics)
- Keep technologies and skills that match JD keywords
- Maintain action-oriented language
- DO NOT add new information or expand on details
- DO NOT split one bullet into multiple bullets

Return ONLY a JSON array of strings with {target_count} or fewer bullets, no markdown, no explanations:
["condensed bullet 1", "condensed bullet 2"]"""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a resume expert that summarizes project descriptions concisely while preserving impact."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            # Remove markdown fences if present
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            summarized_bullets = json.loads(result_text)
            if not isinstance(summarized_bullets, list):
                raise ValueError("LLM did not return a list")
            
            # CRITICAL: Never allow expansion - if LLM returned more bullets, truncate
            original_count = len(bullets)
            if len(summarized_bullets) > original_count:
                logger.warning(f"LLM expanded bullets from {original_count} to {len(summarized_bullets)} - truncating to {original_count}")
                summarized_bullets = summarized_bullets[:original_count]
            
            # Also respect max_bullets limit
            if len(summarized_bullets) > max_bullets:
                summarized_bullets = summarized_bullets[:max_bullets]
            
            # Log the result
            if len(summarized_bullets) < original_count:
                logger.info(f"Condensed {original_count} bullets to {len(summarized_bullets)} bullets")
            elif len(summarized_bullets) == original_count:
                logger.info(f"Kept {original_count} bullets (no condensation needed)")
            else:
                logger.warning(f"Unexpected: {len(summarized_bullets)} bullets from {original_count} input")
            
            # Build appropriate message based on what happened
            if len(summarized_bullets) < original_count:
                message = f"Condensed {original_count} bullets to {len(summarized_bullets)} bullets"
            elif len(summarized_bullets) == original_count:
                message = f"Kept {original_count} bullets (no condensation needed)"
            else:
                message = f"Warning: {len(summarized_bullets)} bullets returned from {original_count} input (truncated)"
            
            return json.dumps({
                "status": "success",
                "message": message,
                "summarized_bullets": summarized_bullets,
                "original_count": len(bullets),
                "final_count": len(summarized_bullets)
            }, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse LLM response: {e}",
                "summarized_bullets": bullets[:max_bullets]  # Fallback to first N bullets
            })
        except Exception as e:
            logger.error(f"Project summarizer failed: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e),
                "summarized_bullets": bullets[:max_bullets]  # Fallback
            })

