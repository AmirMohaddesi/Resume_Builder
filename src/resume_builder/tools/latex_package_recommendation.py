"""LLM-powered tool to recommend missing LaTeX packages and fixes."""
from __future__ import annotations

import json
import logging
import os
from typing import Type, Optional, List, Tuple

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

try:
    from resume_builder.logger import get_logger
    logger = get_logger("latex_package_recommendation")
except ImportError:
    logger = logging.getLogger("latex_package_recommendation")


def _get_llm_client_and_model() -> Tuple[object, str]:
    """Get OpenAI client and model name from environment."""
    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
        return client, model
    except ImportError:
        raise ImportError("OpenAI client not available")


class LatexPackageRecommendationInput(BaseModel):
    """Input schema for LatexPackageRecommendationTool."""
    preamble: str = Field(..., description="LaTeX preamble section")
    errors: Optional[List[str]] = Field(default=None, description="List of error messages (optional)")
    used_commands: Optional[List[str]] = Field(default=None, description="List of LaTeX commands used (optional)")
    model_config = ConfigDict(extra="ignore")


class LatexPackageRecommendationTool(BaseTool):
    """Recommend missing LaTeX packages and fixes using LLM.
    
    Analyzes:
    - Missing packages based on commands used
    - Package conflicts
    - Optimal package order
    - Alternative packages
    """
    name: str = "latex_package_recommendation"
    description: str = (
        "Analyze LaTeX preamble and errors to recommend missing packages and fixes. "
        "Identifies required packages based on commands used and suggests optimal configurations. "
        "Use this when LaTeX compilation fails due to missing packages."
    )
    args_schema: Type[BaseModel] = LatexPackageRecommendationInput

    def _run(
        self,
        preamble: str,
        errors: Optional[List[str]] = None,
        used_commands: Optional[List[str]] = None
    ) -> str:
        """Recommend packages using LLM.
        
        This is a secondary helper - should be called after deterministic checks
        (e.g. latex_package_checker), not as first line of defense.
        Tool provides recommendations only, not verification.
        """
        # Input validation
        if not preamble or not preamble.strip():
            return json.dumps({
                "status": "error",
                "message": "Empty preamble provided",
                "recommendations": {}
            })
        
        try:
            client, model = _get_llm_client_and_model()
        except ImportError:
            logger.error("OpenAI client not available", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": "OpenAI client not available",
                "recommendations": {}
            })
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to initialize LLM client: {str(e)}",
                "recommendations": {}
            })
        
        # Build prompt with optional errors and commands (truncated)
        errors_text = ""
        if errors:
            errors_text = f"\n\nError messages:\n" + "\n".join(f"- {e}" for e in errors[:10])
        
        commands_text = ""
        if used_commands:
            commands_text = f"\n\nCommands used:\n" + ", ".join(used_commands[:20])
        
        prompt = f"""You are analyzing LaTeX preamble to recommend missing packages and fixes.

LaTeX preamble:
{preamble}{errors_text}{commands_text}

Analyze:
1. Missing packages based on commands/errors
2. Package conflicts or incompatibilities
3. Optimal package order
4. Alternative packages if needed
5. Package options that might help

Return ONLY valid JSON with this structure:
{{
  "missing_packages": [{{"name": "package1", "reason": "required for \\command", "priority": "high|medium|low"}}],
  "package_conflicts": ["conflict description"] or [],
  "recommended_order": ["package1", "package2", ...],
  "package_options": [{{"package": "package1", "options": "[option1,option2]", "reason": "why"}}] or [],
  "alternative_packages": [{{"original": "package1", "alternative": "package2", "reason": "why"}}] or [],
  "fixes": ["fix 1", "fix 2"] or []
}}

Return ONLY JSON, no explanations, no code fences."""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a LaTeX expert that recommends packages and fixes based on code analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            recommendations_json = response.choices[0].message.content.strip()
            recommendations = json.loads(recommendations_json)
            
            missing_count = len(recommendations.get("missing_packages", []))
            logger.info(f"Package recommendations: {missing_count} missing packages identified")
            
            return json.dumps({
                "status": "success",
                "message": f"Identified {missing_count} missing packages",
                "recommendations": recommendations
            }, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}", exc_info=True)
            # Return minimal fallback on JSON parse error
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse LLM response: {str(e)}",
                "recommendations": {
                    "missing_packages": [],
                    "package_conflicts": [],
                    "recommended_order": [],
                    "package_options": [],
                    "alternative_packages": [],
                    "fixes": []
                }
            })
        except Exception as e:
            logger.error(f"LaTeX package recommendation failed: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e),
                "recommendations": {}
            })

