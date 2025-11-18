"""LLM-powered tool to validate content for factuality and privacy."""
from __future__ import annotations

import json
import logging
from typing import Type, Optional, Dict, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ContentValidatorInput(BaseModel):
    """Input schema for ContentValidatorTool."""
    resume_json: Dict[str, Any] = Field(..., description="Full resume JSON data to validate")
    profile_json: Optional[Dict[str, Any]] = Field(default=None, description="User profile JSON for factuality checking")
    model_config = ConfigDict(extra="ignore")


class ContentValidatorTool(BaseTool):
    """Validate resume content for factuality, hallucinations, and privacy risks using LLM.
    
    Checks:
    - Factuality: Does content match profile data?
    - Hallucinations: Is any information invented?
    - Privacy: Are there privacy violations?
    - Consistency: Are dates, locations, etc. consistent?
    """
    name: str = "content_validator"
    description: str = (
        "Validate resume content for factuality, hallucinations, and privacy risks. "
        "Compares generated content against profile to detect invented information. "
        "Use this to ensure resume accuracy and privacy compliance."
    )
    args_schema: Type[BaseModel] = ContentValidatorInput

    def _run(
        self,
        resume_json: Dict[str, Any],
        profile_json: Optional[Dict[str, Any]] = None
    ) -> str:
        """Validate content using LLM."""
        try:
            if not resume_json:
                return json.dumps({"status": "error", "message": "Empty resume JSON provided", "validation": {}})
            
            # Get LLM client
            try:
                from openai import OpenAI
                client = OpenAI()
            except ImportError:
                logger.error("OpenAI client not available")
                return json.dumps({"status": "error", "message": "OpenAI client not available", "validation": {}})
            
            # Get model from environment
            import os
            model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
            
            # Prepare data for LLM (truncate if too large)
            resume_str = json.dumps(resume_json, indent=2)
            if len(resume_str) > 3000:
                resume_str = resume_str[:3000] + "... (truncated)"
            
            profile_str = ""
            if profile_json:
                profile_str = json.dumps(profile_json, indent=2)
                if len(profile_str) > 2000:
                    profile_str = profile_str[:2000] + "... (truncated)"
            
            prompt = f"""You are validating resume content for factuality, hallucinations, and privacy risks.

Generated Resume JSON:
{resume_str}

User Profile JSON (ground truth):
{profile_str if profile_str else "Not provided"}

Check for:
1. Factuality: Does resume content match profile data? (names, dates, companies, locations)
2. Hallucinations: Is any information invented that's not in the profile?
3. Privacy: Are there privacy violations? (SSN, excessive personal details)
4. Consistency: Are dates, locations, and other facts consistent?

Return ONLY valid JSON with this structure:
{{
  "is_factual": true/false,
  "has_hallucinations": true/false,
  "privacy_risks": ["risk 1", "risk 2"] or [],
  "factuality_issues": ["issue 1", "issue 2"] or [],
  "invented_information": ["item 1", "item 2"] or [],
  "overall_status": "safe|warning|error",
  "recommendations": ["recommendation 1", "recommendation 2"] or []
}}"""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a resume validator that checks for factuality, hallucinations, and privacy risks."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            validation_json = response.choices[0].message.content.strip()
            validation = json.loads(validation_json)
            
            logger.info(f"Content validation: {validation.get('overall_status', 'unknown')}")
            
            return json.dumps({
                "status": "success",
                "message": "Content validation completed",
                "validation": validation
            }, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse LLM response: {e}",
                "validation": {"overall_status": "error", "has_hallucinations": False}
            })
        except Exception as e:
            logger.error(f"Content validator failed: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e),
                "validation": {}
            })

