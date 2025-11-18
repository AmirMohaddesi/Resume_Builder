"""Shared JSON file I/O tool for reading and writing structured data.

This tool provides a unified interface for agents to read and write JSON files,
improving modularity and resilience when tasks are run out of sequence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from resume_builder.utils import clean_json_content
from resume_builder.paths import PROJECT_ROOT, OUTPUT_DIR

# Module-level cache shared between ReadJsonFileTool and WriteJsonFileTool
# Using module-level dict to avoid Pydantic ModelPrivateAttr issues
_json_file_cache: dict[str, dict[str, Any]] = {}
_json_cache_timestamps: dict[str, float] = {}

try:
    from resume_builder.logger import get_logger
    logger = get_logger("json_file_io")
except ImportError:
    import logging
    logger = logging.getLogger("json_file_io")


class ReadJsonFileInput(BaseModel):
    """Input schema for ReadJsonFileTool."""
    file_path: str = Field(..., description="Path to the JSON file to read (absolute or relative to project root).")
    model_config = ConfigDict(extra="ignore")


class ReadJsonFileTool(BaseTool):
    """Read a JSON file and return its parsed contents.
    
    Returns structured error messages that orchestrator agents can reason about:
    - "[error] JSON file not found: <path>" - File is missing
    - "[error] JSON file is empty: <path>" - File exists but is empty
    - "[error] Failed to parse JSON file <path>: <error>" - Invalid JSON
    
    On success, returns formatted JSON with file path and contents.
    Orchestrator agents should treat missing files as non-fatal only if that phase is optional.
    """
    
    name: str = "read_json_file"
    description: str = (
        "Read a JSON file and return its parsed contents. Use this to access structured data "
        "from any JSON file in the project, such as parsed_jd.json, selected_experiences.json, "
        "selected_skills.json, tailor_plan.json, etc. This provides modularity and resilience "
        "when tasks are run out of sequence. Files are cached to avoid redundant reads. "
        "Returns structured error messages (starting with '[error]') that can be reasoned about "
        "by orchestrator agents. Missing files return '[error] JSON file not found: <path>'."
    )
    args_schema: Type[BaseModel] = ReadJsonFileInput
    
    def _run(self, file_path: str) -> str:
        """Read and return JSON file contents with caching to avoid redundant reads."""
        try:
            json_file = Path(file_path)
            if not json_file.is_absolute():
                # Try resolving relative to OUTPUT_DIR first (most common case)
                if file_path.startswith("output/"):
                    json_file = OUTPUT_DIR / file_path.replace("output/", "", 1)
                else:
                    # Try multiple locations in order of likelihood
                    # 1. OUTPUT_DIR (most common location for JSON files)
                    json_file = OUTPUT_DIR / file_path
                    if not json_file.exists():
                        # 2. PROJECT_ROOT
                        json_file = PROJECT_ROOT / file_path
                        if not json_file.exists():
                            # 3. Fallback: try resolving as-is
                            json_file = Path(file_path).resolve()
            
            if not json_file.exists():
                # Provide helpful error message with possible locations
                possible_locations = [
                    str(OUTPUT_DIR / file_path),
                    str(PROJECT_ROOT / file_path),
                    str(Path(file_path).resolve())
                ]
                return f"[error] JSON file not found: {file_path}\nTried locations: {', '.join(possible_locations)}"
            
            # Check file extension - warn if not .json
            if json_file.suffix.lower() not in ('.json', ''):
                logger.warning(f"read_json_file called on non-JSON file: {json_file} (extension: {json_file.suffix})")
                return f"[error] File {file_path} is not a JSON file (extension: {json_file.suffix}). Use appropriate tool for this file type (e.g., read_latex_file for .tex files, tex_info_extractor for LaTeX templates)."
            
            # Resolve to absolute path for cache key
            cache_key = str(json_file.resolve())
            current_mtime = json_file.stat().st_mtime
            
            # Check cache - return cached data if file hasn't changed
            if cache_key in _json_file_cache:
                if cache_key in _json_cache_timestamps and _json_cache_timestamps[cache_key] >= current_mtime:
                    logger.debug(f"Returning cached JSON file: {json_file}")
                    cached_data = _json_file_cache[cache_key]
                    formatted = json.dumps(cached_data, indent=2, ensure_ascii=False)
                    return f"✅ JSON file read successfully (cached).\n\nFile: {json_file}\n\nContents:\n{formatted}"
            
            # Read file from disk
            content = json_file.read_text(encoding='utf-8')
            
            # Clean the content to handle markdown-wrapped JSON
            cleaned_content = clean_json_content(content)
            
            if not cleaned_content:
                return f"[error] JSON file is empty: {file_path}"
            
            # Try to parse the JSON
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                # Log the problematic content for debugging
                logger.error(f"JSON parse error in {json_file}: {str(e)}")
                logger.debug(f"Content preview (first 500 chars): {cleaned_content[:500]}")
                return f"[error] Failed to parse JSON file {file_path}: {str(e)}. The file may contain invalid JSON or markdown formatting."
            
            # Cache the parsed data
            _json_file_cache[cache_key] = data
            _json_cache_timestamps[cache_key] = current_mtime
            
            logger.info(f"Read JSON file: {json_file}")
            
            # Format the output nicely
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            return f"✅ JSON file read successfully.\n\nFile: {json_file}\n\nContents:\n{formatted}"
            
        except Exception as e:
            error_msg = f"Failed to read JSON file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"[error] {error_msg}"


class WriteJsonFileInput(BaseModel):
    """Input schema for WriteJsonFileTool."""
    file_path: str = Field(..., description="Path to the JSON file to write (absolute or relative to project root).")
    data: str = Field(..., description="The JSON data to write, as a JSON-formatted string.")
    model_config = ConfigDict(extra="ignore")


class WriteJsonFileTool(BaseTool):
    """Write data to a JSON file."""
    
    name: str = "write_json_file"
    description: str = (
        "Write data to a JSON file. Use this to save structured data to any JSON file in the project. "
        "The data parameter should be a valid JSON string. The file will be created or overwritten."
    )
    args_schema: Type[BaseModel] = WriteJsonFileInput
    
    def _run(self, file_path: str, data: str) -> str:
        """Write JSON data to file with atomic write and validation."""
        try:
            # Input validation
            if not data or not data.strip():
                return "[error] JSON data is empty"
            
            json_file = Path(file_path)
            if not json_file.is_absolute():
                # Try resolving relative to OUTPUT_DIR first (most common case)
                if file_path.startswith("output/"):
                    json_file = OUTPUT_DIR / file_path.replace("output/", "", 1)
                else:
                    # Try relative to PROJECT_ROOT
                    json_file = PROJECT_ROOT / file_path
            
            logger.debug(f"Writing JSON file: {json_file} ({len(data)} chars)")
            
            # Ensure parent directory exists
            if not json_file.parent.exists():
                json_file.parent.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {json_file.parent}")
            
            # Clean the input data to handle markdown-wrapped JSON
            cleaned_data = clean_json_content(data)
            
            if not cleaned_data:
                logger.error(f"JSON data is empty after cleaning for {json_file}")
                return "[error] JSON data is empty after cleaning"
            
            # Parse the JSON string to validate it
            try:
                parsed_data = json.loads(cleaned_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON data for {json_file}: {str(e)}")
                logger.debug(f"Data preview (first 500 chars): {cleaned_data[:500]}")
                return f"[error] Invalid JSON data: {str(e)}. Please ensure the data is valid JSON."
            
            # Validate basic schema: should be a dict/object (not array or primitive)
            if not isinstance(parsed_data, dict):
                logger.error(f"JSON data must be an object (dict), got {type(parsed_data).__name__} for {json_file}")
                return f"[error] JSON data must be an object (dict), got {type(parsed_data).__name__}"
            
            # Atomic write: write to temp file first, then rename
            # This prevents partial writes if the process is interrupted
            temp_file = json_file.with_suffix(json_file.suffix + '.tmp')
            try:
                formatted_json = json.dumps(parsed_data, indent=2, ensure_ascii=False)
                temp_file.write_text(formatted_json, encoding='utf-8')
                
                # Atomic rename (works on Windows and Unix)
                temp_file.replace(json_file)
                
                logger.debug(f"Wrote JSON file: {json_file} ({len(formatted_json)} chars)")
            except Exception as e:
                logger.error(f"Exception during file write for {json_file}: {e}", exc_info=True)
                # Clean up temp file if rename failed
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise e
            
            # Invalidate cache for this file so subsequent reads get fresh data
            cache_key = str(json_file.resolve())
            if cache_key in _json_file_cache:
                del _json_file_cache[cache_key]
            if cache_key in _json_cache_timestamps:
                del _json_cache_timestamps[cache_key]
            
            return f"✅ JSON file written successfully.\n\nFile: {json_file}\nData size: {len(formatted_json)} characters"
            
        except Exception as e:
            error_msg = f"Failed to write JSON file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"[error] {error_msg}"

