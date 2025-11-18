"""LLM-powered tool to refine and shorten summary text."""
from __future__ import annotations

import json
import logging
from typing import Type, Optional, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class SummaryEditorInput(BaseModel):
    """Input schema for SummaryEditorTool."""
    summary: str = Field(..., description="Current summary text to refine")
    jd_keywords: Optional[List[str]] = Field(default=None, description="Job description keywords for alignment")
    target_sentences: int = Field(default=2, description="Target number of sentences (default: 2)")
    max_words: int = Field(default=90, description="Maximum total words (default: 90)")
    model_config = ConfigDict(extra="ignore")


class SummaryEditorTool(BaseTool):
    """Refine and shorten summary text using LLM.
    
    Creates a crisp, impactful summary that:
    - Fits within word/sentence limits
    - Emphasizes JD-relevant keywords
    - Preserves quantifiable achievements
    - Maintains professional tone
    """
    name: str = "summary_editor"
    description: str = (
        "Refine and shorten summary text to be crisp and impactful. "
        "Creates 1-2 sentence summaries that emphasize JD keywords and preserve achievements. "
        "Use this to improve summaries after initial generation."
    )
    args_schema: Type[BaseModel] = SummaryEditorInput

    def _run(
        self,
        summary: str,
        jd_keywords: Optional[List[str]] = None,
        target_sentences: int = 2,
        max_words: int = 90
    ) -> str:
        """Refine summary using LLM."""
        try:
            if not summary or not summary.strip():
                return json.dumps({"status": "error", "message": "Empty summary provided", "refined_summary": ""})
            
            # Get LLM client
            try:
                from openai import OpenAI
                client = OpenAI()
            except ImportError:
                logger.error("OpenAI client not available")
                return json.dumps({"status": "error", "message": "OpenAI client not available", "refined_summary": summary})
            
            # Get model from environment
            import os
            model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
            
            # Build prompt
            jd_context = ""
            if jd_keywords:
                jd_context = f"\n\nJob Description Keywords to emphasize: {', '.join(jd_keywords[:15])}"
            
            prompt = f"""You are refining a professional summary for a resume. Make it crisp, impactful, and JD-aligned.

Current summary:
{summary}{jd_context}

Requirements:
- Exactly {target_sentences} sentences
- Maximum {max_words} words total
- Emphasize JD keywords naturally
- Preserve quantifiable achievements (years of experience, metrics)
- Maintain professional tone
- Remove redundancy
- Make every word count

Return ONLY the refined summary text, no markdown, no explanations, no quotes."""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a resume expert that creates crisp, impactful professional summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=200
            )
            
            refined_summary = response.choices[0].message.content.strip()
            # Remove markdown fences and quotes if present
            refined_summary = refined_summary.replace("```", "").strip()
            if refined_summary.startswith('"') and refined_summary.endswith('"'):
                refined_summary = refined_summary[1:-1]
            if refined_summary.startswith("'") and refined_summary.endswith("'"):
                refined_summary = refined_summary[1:-1]
            
            # Count words
            word_count = len(refined_summary.split())
            sentence_count = len([s for s in refined_summary.split('.') if s.strip()])
            
            logger.info(f"Refined summary: {word_count} words, {sentence_count} sentences")
            
            return json.dumps({
                "status": "success",
                "message": f"Refined summary to {word_count} words, {sentence_count} sentences",
                "refined_summary": refined_summary,
                "word_count": word_count,
                "sentence_count": sentence_count
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Summary editor failed: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e),
                "refined_summary": summary  # Fallback to original
            })

