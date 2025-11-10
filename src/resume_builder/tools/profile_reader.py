from __future__ import annotations

"""
Tool for reading and extracting profile data from JSON files.
This ensures agents can access the profile data directly.
"""

import json
from pathlib import Path
from typing import Dict, Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict


class ProfileReaderInput(BaseModel):
    """Input schema for the ProfileReaderTool."""
    profile_path: str = Field(..., description="Path to the profile JSON file to read.")
    # Ignore any extra fields passed by upstream configs
    model_config = ConfigDict(extra="ignore")


class ProfileReaderTool(BaseTool):
    """
    Read and extract profile data from a JSON file.
    This allows agents to access the candidate's profile information directly.
    """

    name: str = "profile_reader"
    description: str = (
        "Read the candidate profile from a JSON file. Use this to get the actual candidate's "
        "information including name, experience, education, projects, skills, and awards. "
        "Returns the full profile as a JSON object. You MUST use this tool to get the real profile data "
        "before generating any resume content. Never use placeholder or fictional data - always read the profile first."
    )
    # Declare args_schema as a ClassVar so Pydantic treats it as a static attribute.
    args_schema: Type[BaseModel] = ProfileReaderInput

    def _run(self, profile_path: str) -> str:  # type: ignore[override]
        """Read the profile JSON file and return its contents as a JSON string."""
        try:
            # Check if the path contains template variables (means agent used literal string instead of actual path)
            if "{{" in profile_path or "}}" in profile_path or "input.profile_path" in profile_path:
                error_msg = (
                    f"Profile path contains template variable: {profile_path}\n"
                    f"CRITICAL: You must use the ACTUAL profile path value from the task inputs, not the template string.\n"
                    f"The profile path is provided in the task inputs under the key 'profile_path'.\n"
                    f"Extract the actual path value from the task inputs and call this tool with that value.\n"
                    f"Do NOT use the literal string '{{input.profile_path}}' - use the actual resolved path."
                )
                return json.dumps({
                    "success": False,
                    "error": error_msg,
                    "profile": None
                }, indent=2)
            
            profile = Path(profile_path)
            
            # Resolve relative paths
            if not profile.is_absolute():
                # Try relative to current working directory
                profile = Path.cwd() / profile
                if not profile.exists():
                    # Try relative to project root (look for pyproject.toml or src/)
                    current = Path.cwd()
                    while current != current.parent:
                        if (current / "pyproject.toml").exists() or (current / "src").exists():
                            profile = current / profile_path
                            break
                        current = current.parent
            
            # Resolve to absolute path
            profile = profile.resolve()
            
            # Check if file exists
            if not profile.exists():
                error_msg = f"Profile file not found: {profile_path} (resolved to: {profile})"
                return json.dumps({
                    "success": False,
                    "error": error_msg,
                    "profile": None
                }, indent=2)
            
            # Read and parse the JSON file
            with open(profile, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            # Return successful result with profile data
            result = {
                "success": True,
                "profile": profile_data,
                "profile_path": str(profile)
            }
            return json.dumps(result, indent=2)
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in profile file: {str(e)}"
            return json.dumps({
                "success": False,
                "error": error_msg,
                "profile": None
            }, indent=2)
        except Exception as e:
            error_msg = f"Error reading profile file: {str(e)}"
            return json.dumps({
                "success": False,
                "error": error_msg,
                "profile": None
            }, indent=2)

