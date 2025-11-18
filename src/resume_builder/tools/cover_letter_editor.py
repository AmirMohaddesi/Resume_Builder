"""LLM-powered tool to refine and shorten cover letter."""
from __future__ import annotations

import json
import logging
import os
from typing import Type, Optional, Tuple

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

try:
    from resume_builder.logger import get_logger
    logger = get_logger("cover_letter_editor")
except ImportError:
    logger = logging.getLogger("cover_letter_editor")


def _get_llm_client_and_model() -> Tuple[object, str]:
    """Get OpenAI client and model name from environment."""
    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
        return client, model
    except ImportError:
        raise ImportError("OpenAI client not available")


class CoverLetterEditorInput(BaseModel):
    """Input schema for CoverLetterEditorTool."""
    cover_letter_md: str = Field(..., description="Current cover letter markdown to refine")
    jd_text: Optional[str] = Field(default=None, description="Job description text for alignment")
    max_words: int = Field(default=400, description="Maximum total words (default: 400)")
    model_config = ConfigDict(extra="ignore")


class CoverLetterEditorTool(BaseTool):
    """Refine and shorten cover letter using LLM.
    
    Creates a polished cover letter that:
    - Fits within word limits
    - Maintains persuasive structure (intro → body → closing)
    - Emphasizes JD alignment
    - Preserves key selling points
    """
    name: str = "cover_letter_editor"
    description: str = (
        "Refine and shorten cover letter to be polished and impactful. "
        "Maintains persuasive structure while condensing to fit word limits. "
        "Use this to improve cover letters after initial generation."
    )
    args_schema: Type[BaseModel] = CoverLetterEditorInput

    def _run(
        self,
        cover_letter_md: str,
        jd_text: Optional[str] = None,
        max_words: int = 400
    ) -> str:
        """Refine cover letter using LLM.
        
        Preserves semantic facts (employment, dates, companies) while condensing.
        Strictly respects max_words with ~5-10 word tolerance.
        """
        # Input validation
        if not cover_letter_md or not cover_letter_md.strip():
            return json.dumps({
                "status": "error",
                "message": "Empty cover letter provided",
                "refined_cover_letter": ""
            })
        
        if max_words < 50:
            max_words = 50  # Minimum reasonable limit
        
        try:
            client, model = _get_llm_client_and_model()
        except ImportError:
            logger.error("OpenAI client not available", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": "OpenAI client not available",
                "refined_cover_letter": cover_letter_md
            })
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to initialize LLM client: {str(e)}",
                "refined_cover_letter": cover_letter_md
            })
        
        # Build prompt with JD context (truncated)
        jd_context = ""
        if jd_text and jd_text.strip():
            jd_preview = jd_text[:500] + "..." if len(jd_text) > 500 else jd_text
            jd_context = f"\n\nJob Description (for alignment):\n{jd_preview}"
        
        prompt = f"""You are refining a cover letter for a resume. Make it polished, persuasive, and JD-aligned.

Current cover letter:
{cover_letter_md}{jd_context}

Requirements:
- Maximum {max_words} words total (strict limit, allow ~5-10 word tolerance)
- Maintain structure: greeting → intro → 2-3 body paragraphs → closing
- Emphasize JD alignment naturally
- Preserve key selling points and achievements
- DO NOT change semantic facts: employment dates, company names, role titles must remain accurate
- Remove redundancy
- Maintain professional, persuasive tone
- Make every paragraph count

Return ONLY the refined cover letter markdown, no explanations, no markdown code fences."""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a cover letter expert that creates polished, persuasive cover letters."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=800
            )
            
            refined_cover_letter = response.choices[0].message.content.strip()
            # Remove markdown fences if present
            refined_cover_letter = refined_cover_letter.replace("```markdown", "").replace("```", "").strip()
            
            # Count words
            word_count = len(refined_cover_letter.split())
            
            logger.info(f"Refined cover letter: {word_count} words (target: {max_words})")
            
            return json.dumps({
                "status": "success",
                "message": f"Refined cover letter to {word_count} words",
                "refined_cover_letter": refined_cover_letter,
                "word_count": word_count
            }, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse LLM response: {str(e)}",
                "refined_cover_letter": cover_letter_md
            })
        except Exception as e:
            logger.error(f"Cover letter editor failed: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e),
                "refined_cover_letter": cover_letter_md
            })

