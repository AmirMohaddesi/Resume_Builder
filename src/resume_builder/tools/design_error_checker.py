"""
Design Error Checker Tool

This tool allows agents to check for known design errors before generating content.
Agents can query the design error memory to see what issues have been reported
for their specific context (header, summary, experience, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from crewai.tools import BaseTool
from resume_builder.paths import OUTPUT_DIR
from resume_builder.logger import get_logger

logger = get_logger("design_error_checker")


class DesignErrorCheckerInput(BaseModel):
    """Input schema for DesignErrorCheckerTool."""
    context: str = Field(
        ...,
        description="Context/section to check for known design errors. Options: 'header', 'summary', 'experience', 'projects', 'skills', 'education', 'general'"
    )

    model_config = ConfigDict(extra="ignore")


class DesignErrorCheckerTool(BaseTool):
    """Check for known design errors in a specific context.
    
    This tool reads the design error memory to find issues that have been
    reported by users for the given context. Agents should use this tool
    before generating content to avoid repeating known design mistakes.
    """
    name: str = "design_error_checker"
    description: str = (
        "Check for known design errors that have been reported for a specific context. "
        "Use this tool before generating content to avoid repeating design mistakes. "
        "Returns a list of known errors with prevention guidance. "
        "Context options: 'header', 'summary', 'experience', 'projects', 'skills', 'education', 'general'"
    )
    args_schema: type[BaseModel] = DesignErrorCheckerInput

    def _run(self, context: str) -> str:
        """Check for known design errors in the given context.
        
        Args:
            context: Context/section to check (e.g., 'header', 'summary', 'experience')
            
        Returns:
            JSON string with known errors and prevention guidance
        """
        try:
            from resume_builder.design_error_memory import lookup_design_errors
            
            # Lookup errors for this context
            errors = lookup_design_errors(context)
            
            if not errors:
                return json.dumps({
                    "status": "success",
                    "message": f"No known design errors found for context: {context}",
                    "errors": [],
                    "prevention_guidance": None
                }, indent=2)
            
            # Get the most frequent/recent error
            primary_error = errors[0]
            count = primary_error.get("count", 1)
            
            # Build prevention guidance
            prevention_guidance = None
            if count >= 2:  # Only warn if error occurred multiple times
                error_type = primary_error.get("error_type", "Unknown")
                prevention = primary_error.get("prevention", "")
                issue_description = primary_error.get("issue_description", "")
                
                prevention_guidance = {
                    "warning": f"Known design issue reported {count} times",
                    "error_type": error_type,
                    "issue": issue_description,
                    "prevention": prevention
                }
            
            # Format all errors for reference
            formatted_errors = []
            for err in errors[:5]:  # Limit to top 5
                formatted_errors.append({
                    "issue": err.get("issue_description", ""),
                    "error_type": err.get("error_type", "Unknown"),
                    "count": err.get("count", 1),
                    "prevention": err.get("prevention", "")
                })
            
            result = {
                "status": "success",
                "message": f"Found {len(errors)} known design error(s) for context: {context}",
                "errors": formatted_errors,
                "prevention_guidance": prevention_guidance,
                "recommendation": (
                    f"⚠️ IMPORTANT: Before generating {context} content, review the prevention guidance above. "
                    f"This issue has been reported {count} time(s) by users. Follow the prevention suggestions to avoid repeating this mistake."
                ) if prevention_guidance else None
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Design error checker failed: {e}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": f"Failed to check design errors: {str(e)}",
                "errors": [],
                "prevention_guidance": None
            }, indent=2)

