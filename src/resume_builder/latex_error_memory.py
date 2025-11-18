"""
LaTeX Error Memory & Caching System

This module provides intelligent caching and recognition of repeated LaTeX compilation errors.
It normalizes errors, stores them persistently, and provides helpful diagnostics for recurring issues.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from resume_builder.paths import OUTPUT_DIR
from resume_builder.logger import get_logger

logger = get_logger("latex_error_memory")

# Configuration
ENABLE_LATEX_ERROR_MEMORY = True  # Can be disabled via environment variable or config
ERROR_MEMORY_FILE = OUTPUT_DIR / "latex_error_memory.json"
MAX_CACHE_SIZE = 1000  # Maximum number of error records to keep


def compute_latex_fingerprint(latex_source: str) -> str:
    """
    Compute a fingerprint (hash) of the LaTeX source.
    
    Normalizes the source by:
    - Stripping whitespace and comments
    - Removing absolute paths
    - Normalizing line endings
    
    Args:
        latex_source: The LaTeX source code
        
    Returns:
        SHA256 hash as hex string
    """
    if not latex_source:
        return hashlib.sha256(b"").hexdigest()
    
    # Normalize: remove comments, extra whitespace, and paths
    normalized = latex_source
    
    # Remove LaTeX comments (lines starting with %)
    lines = normalized.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove inline comments (but preserve % in strings/commands)
        # Simple approach: remove % at end of line (not in commands)
        if '%' in line:
            # Check if % is part of a command or string
            comment_pos = line.find('%')
            # If % is not escaped and not in a command, it's a comment
            if comment_pos > 0 and line[comment_pos-1] != '\\':
                line = line[:comment_pos].rstrip()
        cleaned_lines.append(line)
    
    normalized = '\n'.join(cleaned_lines)
    
    # Remove absolute paths (common patterns)
    normalized = re.sub(r'/[^\s]+/[\w\-\.]+\.(tex|sty|cls)', r'[PATH]/\1', normalized)
    normalized = re.sub(r'C:\\[^\s]+\\[\w\-\.]+\.(tex|sty|cls)', r'[PATH]\\\1', normalized)
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = normalized.strip()
    
    # Compute hash
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def normalize_error_message(error_text: str) -> str:
    """
    Normalize an error message by removing paths, line numbers, and other variable content.
    
    Args:
        error_text: Raw error message from LaTeX log
        
    Returns:
        Normalized error message
    """
    if not error_text:
        return ""
    
    normalized = error_text
    
    # Remove absolute paths
    normalized = re.sub(r'/[^\s]+/[\w\-\.]+\.(tex|sty|cls)', r'[FILE].\1', normalized)
    normalized = re.sub(r'C:\\[^\s]+\\[\w\-\.]+\.(tex|sty|cls)', r'[FILE].\1', normalized)
    
    # Remove line numbers
    normalized = re.sub(r'line \d+', 'line [N]', normalized)
    normalized = re.sub(r'l\.\d+', 'l.[N]', normalized)
    
    # Remove specific file paths in error messages
    normalized = re.sub(r'File `[^\']+\'', "File '[FILE]'", normalized)
    normalized = re.sub(r'File "[^"]+"', 'File "[FILE]"', normalized)
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = normalized.strip()
    
    return normalized


def classify_error_type(error_text: str) -> str:
    """
    Classify the error type based on error message patterns.
    
    Args:
        error_text: Normalized error message
        
    Returns:
        Error type: MissingPackage, UndefinedControlSequence, EncodingError, OverfullBox, or Unknown
    """
    error_lower = error_text.lower()
    
    # Missing package
    if any(pattern in error_lower for pattern in [
        "file '", "file `", "not found", "missing package", "package not found"
    ]):
        return "MissingPackage"
    
    # Undefined control sequence
    if any(pattern in error_lower for pattern in [
        "undefined control sequence", "undefined command", "command not found"
    ]):
        return "UndefinedControlSequence"
    
    # Encoding errors
    if any(pattern in error_lower for pattern in [
        "encoding", "utf-8", "character", "invalid character", "inputenc"
    ]):
        return "EncodingError"
    
    # Overfull/underfull boxes
    if any(pattern in error_lower for pattern in [
        "overfull", "underfull", "hbox", "vbox"
    ]):
        return "OverfullBox"
    
    # Syntax errors
    if any(pattern in error_lower for pattern in [
        "missing", "inserted", "extra", "syntax", "parse error"
    ]):
        return "SyntaxError"
    
    return "Unknown"


def extract_error_snippet(log_text: str, max_length: int = 200) -> str:
    """
    Extract a relevant snippet from the log that contains the error.
    
    Args:
        log_text: Full compilation log
        max_length: Maximum length of snippet
        
    Returns:
        Error snippet
    """
    if not log_text:
        return ""
    
    # Look for error markers
    error_patterns = [
        r'! (.*)',
        r'Error: (.*)',
        r'Fatal error: (.*)',
    ]
    
    lines = log_text.split('\n')
    for i, line in enumerate(lines):
        for pattern in error_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Get context (current line + next few lines)
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 5)
                snippet = '\n'.join(lines[context_start:context_end])
                if len(snippet) > max_length:
                    snippet = snippet[:max_length] + "..."
                return snippet
    
    # Fallback: return last part of log
    return log_text[-max_length:] if len(log_text) > max_length else log_text


def suggest_fix(error_type: str, normalized_message: str) -> str:
    """
    Generate a suggested fix based on error type and message.
    
    Args:
        error_type: Classified error type
        normalized_message: Normalized error message
        
    Returns:
        Suggested fix text
    """
    if error_type == "MissingPackage":
        # Try to extract package name
        package_match = re.search(r"File '[^']*'([^']+)'", normalized_message)
        if package_match:
            package = package_match.group(1).replace('.sty', '').replace('.cls', '')
            return f"Install TeX package '{package}' or use a template that does not require it."
        return "Install the missing TeX package or modify the template to remove the dependency."
    
    elif error_type == "UndefinedControlSequence":
        # Try to extract command name
        cmd_match = re.search(r"undefined control sequence.*?\\?([a-zA-Z]+)", normalized_message)
        if cmd_match:
            cmd = cmd_match.group(1)
            return f"Command '\\{cmd}' is undefined. Add the required package or define the command."
        return "An undefined LaTeX command is being used. Check package requirements or command definitions."
    
    elif error_type == "EncodingError":
        return "Check character encoding in the LaTeX source. Ensure UTF-8 encoding and proper inputenc package."
    
    elif error_type == "OverfullBox":
        return "Text is too wide for the page. Consider shortening text or adjusting page margins."
    
    elif error_type == "SyntaxError":
        return "Check LaTeX syntax: missing braces, unescaped special characters, or malformed commands."
    
    return "Review the LaTeX source for syntax errors or missing dependencies."


def load_error_memory() -> Dict[str, Any]:
    """
    Load the error memory cache from disk.
    
    Returns:
        Dictionary with error records, or empty dict if file doesn't exist or is corrupted
    """
    if not ENABLE_LATEX_ERROR_MEMORY:
        return {}
    
    if not ERROR_MEMORY_FILE.exists():
        return {}
    
    try:
        with open(ERROR_MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load error memory cache: {e}")
        return {}


def save_error_memory(memory: Dict[str, Any]) -> None:
    """
    Save the error memory cache to disk.
    
    Args:
        memory: Dictionary with error records
    """
    if not ENABLE_LATEX_ERROR_MEMORY:
        return
    
    try:
        # Ensure directory exists
        ERROR_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Limit cache size
        if "errors" in memory and len(memory["errors"]) > MAX_CACHE_SIZE:
            # Keep most recent errors
            errors = memory["errors"]
            errors.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
            memory["errors"] = errors[:MAX_CACHE_SIZE]
            logger.debug(f"Trimmed error cache to {MAX_CACHE_SIZE} entries")
        
        with open(ERROR_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        logger.warning(f"Failed to save error memory cache: {e}")


def record_error(
    fingerprint: str,
    error_info: Dict[str, Any],
    latex_source: Optional[str] = None
) -> None:
    """
    Record a LaTeX compilation error in the memory cache.
    
    Args:
        fingerprint: LaTeX source fingerprint
        error_info: Dictionary with error details:
            - log_text: Full compilation log
            - error_message: Extracted error message
            - error_type: Classified error type
        latex_source: Optional LaTeX source for context
    """
    if not ENABLE_LATEX_ERROR_MEMORY:
        return
    
    try:
        memory = load_error_memory()
        
        # Initialize structure if needed
        if "errors" not in memory:
            memory["errors"] = []
        
        # Normalize error message
        error_message = error_info.get("error_message", "")
        normalized_message = normalize_error_message(error_message)
        
        # Classify error
        error_type = error_info.get("error_type")
        if not error_type:
            error_type = classify_error_type(normalized_message)
        
        # Extract snippet
        log_text = error_info.get("log_text", "")
        error_snippet = extract_error_snippet(log_text)
        
        # Generate suggested fix
        suggested_fix = error_info.get("suggested_fix")
        if not suggested_fix:
            suggested_fix = suggest_fix(error_type, normalized_message)
        
        # Check if we already have this error (by fingerprint + normalized message)
        now = datetime.now().isoformat()
        existing_error = None
        for err in memory["errors"]:
            if (err.get("fingerprint") == fingerprint and 
                err.get("normalized_message") == normalized_message):
                existing_error = err
                break
        
        if existing_error:
            # Update existing error
            existing_error["last_seen"] = now
            existing_error["count"] = existing_error.get("count", 1) + 1
            existing_error["error_type"] = error_type
            existing_error["suggested_fix"] = suggested_fix
            # Update snippet if we have a better one
            if error_snippet and len(error_snippet) > len(existing_error.get("raw_snippet", "")):
                existing_error["raw_snippet"] = error_snippet
        else:
            # Add new error
            new_error = {
                "fingerprint": fingerprint,
                "first_seen": now,
                "last_seen": now,
                "count": 1,
                "error_type": error_type,
                "normalized_message": normalized_message,
                "raw_snippet": error_snippet,
                "suggested_fix": suggested_fix,
            }
            memory["errors"].append(new_error)
        
        save_error_memory(memory)
        logger.debug(f"Recorded LaTeX error: {error_type} (count: {existing_error['count'] if existing_error else 1})")
        
    except Exception as e:
        logger.warning(f"Failed to record error in memory: {e}")


def lookup_errors(fingerprint: str) -> List[Dict[str, Any]]:
    """
    Look up past errors for a given LaTeX fingerprint.
    
    Args:
        fingerprint: LaTeX source fingerprint
        
    Returns:
        List of error records matching this fingerprint
    """
    if not ENABLE_LATEX_ERROR_MEMORY:
        return []
    
    try:
        memory = load_error_memory()
        errors = memory.get("errors", [])
        
        # Find errors matching this fingerprint
        matching_errors = [
            err for err in errors
            if err.get("fingerprint") == fingerprint
        ]
        
        # Sort by count (most frequent first) and last_seen (most recent first)
        matching_errors.sort(key=lambda x: (x.get("count", 0), x.get("last_seen", "")), reverse=True)
        
        return matching_errors
    except Exception as e:
        logger.warning(f"Failed to lookup errors: {e}")
        return []


def summarize_errors_for_ui(fingerprint: str) -> Optional[str]:
    """
    Generate a user-friendly summary of known errors for a fingerprint.
    
    Args:
        fingerprint: LaTeX source fingerprint
        
    Returns:
        Formatted string for UI display, or None if no errors found
    """
    errors = lookup_errors(fingerprint)
    if not errors:
        return None
    
    # Get the most frequent/recent error
    primary_error = errors[0]
    count = primary_error.get("count", 1)
    error_type = primary_error.get("error_type", "Unknown")
    normalized_message = primary_error.get("normalized_message", "")
    suggested_fix = primary_error.get("suggested_fix", "")
    
    # Build summary message
    parts = []
    
    if count > 1:
        parts.append(f"⚠️ This LaTeX document previously failed with the same error ({count} times).")
    else:
        parts.append("⚠️ This LaTeX document previously failed with a similar error.")
    
    if error_type != "Unknown":
        parts.append(f"Error type: {error_type}")
    
    if normalized_message:
        # Truncate long messages
        msg = normalized_message[:150] + "..." if len(normalized_message) > 150 else normalized_message
        parts.append(f"Error: {msg}")
    
    if suggested_fix:
        parts.append(f"Suggested fix: {suggested_fix}")
    
    return "\n".join(parts)

