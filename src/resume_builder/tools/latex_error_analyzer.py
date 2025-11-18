"""LLM-powered tool to analyze LaTeX compilation errors and suggest fixes."""
from __future__ import annotations

import json
import logging
import os
from typing import Type, Optional, Tuple

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

try:
    from resume_builder.logger import get_logger
    logger = get_logger("latex_error_analyzer")
except ImportError:
    logger = logging.getLogger("latex_error_analyzer")


def _get_llm_client_and_model() -> Tuple[object, str]:
    """Get OpenAI client and model name from environment."""
    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
        return client, model
    except ImportError:
        raise ImportError("OpenAI client not available")


class LatexErrorAnalyzerInput(BaseModel):
    """Input schema for LatexErrorAnalyzerTool."""
    log_text: str = Field(..., description="LaTeX compilation log text containing errors")
    tex_content: Optional[str] = Field(default=None, description="LaTeX source content (optional, for context)")
    model_config = ConfigDict(extra="ignore")


class LatexErrorAnalyzerTool(BaseTool):
    """Analyze LaTeX compilation errors and suggest fixes using LLM.
    
    Identifies:
    - Root cause of errors
    - Error chains (primary vs. secondary errors)
    - Specific fixes with code examples
    - Missing packages or commands
    """
    name: str = "latex_error_analyzer"
    description: str = (
        "Analyze LaTeX compilation errors and provide root cause analysis with recommended fixes. "
        "Identifies error chains, missing packages, and suggests specific code changes. "
        "Use this when LaTeX compilation fails to get actionable error messages."
    )
    args_schema: Type[BaseModel] = LatexErrorAnalyzerInput

    def _run(
        self,
        log_text: str,
        tex_content: Optional[str] = None
    ) -> str:
        """Analyze LaTeX errors using LLM.
        
        Input: raw LaTeX log (optionally tex content for context).
        Output: JSON with root_cause, error_type, recommended_fix, code_example, 
        missing_packages, additional_errors.
        """
        # Input validation
        if not log_text or not log_text.strip():
            return json.dumps({
                "status": "error",
                "message": "Empty log text provided",
                "analysis": {}
            })
        
        # Truncate log if too long (keep last ~2000 chars which usually contain the errors)
        LOG_TRUNCATE_SIZE = 2000
        if len(log_text) > LOG_TRUNCATE_SIZE:
            log_text_truncated = "..." + log_text[-LOG_TRUNCATE_SIZE:]
            logger.debug(f"Truncated log from {len(log_text)} to {LOG_TRUNCATE_SIZE} chars")
        else:
            log_text_truncated = log_text
        
        try:
            client, model = _get_llm_client_and_model()
        except ImportError:
            logger.error("OpenAI client not available", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": "OpenAI client not available",
                "analysis": {}
            })
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to initialize LLM client: {str(e)}",
                "analysis": {}
            })
        
        # Build prompt with optional LaTeX context (truncated)
        tex_context = ""
        if tex_content and tex_content.strip():
            TEX_PREVIEW_SIZE = 1000
            tex_preview = tex_content[:TEX_PREVIEW_SIZE] + "..." if len(tex_content) > TEX_PREVIEW_SIZE else tex_content
            tex_context = f"\n\nLaTeX source (first {TEX_PREVIEW_SIZE} chars for context):\n{tex_preview}"
        
        prompt = f"""You are analyzing LaTeX compilation errors. Identify the root cause and suggest specific fixes.

Compilation log:
{log_text_truncated}{tex_context}

Analyze:
1. Root cause (primary error)
2. Error chain (if errors cascade)
3. Specific fix with code example
4. Missing packages or commands (if applicable)
5. Common LaTeX issues (unescaped characters, missing braces, etc.)

Return ONLY valid JSON with this structure:
{{
  "root_cause": "description of primary error",
  "error_type": "missing_package|syntax_error|undefined_command|other",
  "recommended_fix": "specific fix description",
  "code_example": "example LaTeX code showing the fix",
  "missing_packages": ["package1", "package2"] or [],
  "additional_errors": ["secondary error 1", "secondary error 2"] or []
}}

Return ONLY JSON, no explanations, no code fences."""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a LaTeX expert that analyzes compilation errors and provides actionable fixes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            analysis_json = response.choices[0].message.content.strip()
            analysis = json.loads(analysis_json)
            
            logger.info(f"Analyzed LaTeX errors: {analysis.get('error_type', 'unknown')}")
            
            return json.dumps({
                "status": "success",
                "message": "LaTeX error analysis completed",
                "analysis": analysis
            }, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse LLM response: {str(e)}",
                "analysis": {
                    "root_cause": "Failed to analyze errors",
                    "error_type": "unknown",
                    "recommended_fix": "Check compilation log manually",
                    "code_example": "",
                    "missing_packages": [],
                    "additional_errors": []
                }
            })
        except Exception as e:
            logger.error(f"LaTeX error analyzer failed: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e),
                "analysis": {}
            })

