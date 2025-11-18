"""
Design Error Memory & Learning System

This module captures and learns from design/logical errors reported by users
through the post-orchestration chatbox. Unlike LaTeX compilation errors,
these are design issues like "four pipes in header" or formatting problems.

The system:
1. Records user-reported design issues
2. Normalizes and classifies them
3. Provides warnings to agents during content generation
4. Learns from corrections to prevent future occurrences
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from resume_builder.paths import OUTPUT_DIR
from resume_builder.logger import get_logger

logger = get_logger("design_error_memory")

# Configuration
ENABLE_DESIGN_ERROR_MEMORY = True
DESIGN_ERROR_MEMORY_FILE = OUTPUT_DIR / "design_error_memory.json"
MAX_CACHE_SIZE = 500  # Maximum number of design error records


def normalize_design_issue(issue_description: str) -> str:
    """
    Normalize a design issue description for matching.
    
    Args:
        issue_description: User-reported issue description
        
    Returns:
        Normalized issue description
    """
    if not issue_description:
        return ""
    
    normalized = issue_description.lower().strip()
    
    # Remove common filler words
    filler_words = ["the", "a", "an", "there", "are", "is", "on", "in", "at", "to", "for"]
    words = normalized.split()
    normalized = " ".join(w for w in words if w not in filler_words)
    
    # Normalize common variations
    normalized = re.sub(r'\b(four|4)\s*pipes?\b', 'multiple pipes', normalized)
    normalized = re.sub(r'\b(too\s*many|excessive|multiple)\s*pipes?\b', 'multiple pipes', normalized)
    normalized = re.sub(r'\b(header|title)\s*line\b', 'header', normalized)
    normalized = re.sub(r'\b(pipe|pipes|separator|separators)\b', 'pipe', normalized)
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def classify_design_error(issue_description: str, context: Optional[str] = None) -> str:
    """
    Classify the type of design error.
    
    Args:
        issue_description: User-reported issue description
        context: Optional context (e.g., "header", "summary", "experience")
        
    Returns:
        Error type: HeaderFormatting, Spacing, Length, Layout, Typography, or Unknown
    """
    issue_lower = issue_description.lower()
    context_lower = (context or "").lower()
    
    # Header formatting issues
    if any(pattern in issue_lower for pattern in [
        "pipe", "separator", "header", "title line", "contact info", "formatting"
    ]) or "header" in context_lower:
        return "HeaderFormatting"
    
    # Spacing issues
    if any(pattern in issue_lower for pattern in [
        "spacing", "too much space", "too little space", "gap", "margin"
    ]):
        return "Spacing"
    
    # Length issues
    if any(pattern in issue_lower for pattern in [
        "too long", "too short", "length", "truncated", "cut off"
    ]):
        return "Length"
    
    # Layout issues
    if any(pattern in issue_lower for pattern in [
        "layout", "alignment", "position", "placement", "arrangement"
    ]):
        return "Layout"
    
    # Typography issues
    if any(pattern in issue_lower for pattern in [
        "font", "size", "bold", "italic", "typography", "text style"
    ]):
        return "Typography"
    
    return "Unknown"


def extract_context_from_request(user_message: str) -> str:
    """
    Extract context (section) from user message.
    
    Args:
        user_message: User's edit request or error report
        
    Returns:
        Context string: "header", "summary", "experience", "skills", "projects", or "general"
    """
    message_lower = user_message.lower()
    
    # Check for header context first (including "before summary", "at the top", etc.)
    if any(word in message_lower for word in [
        "header", "title line", "contact", "top of resume", "at the top",
        "before the summary", "right before", "above the summary"
    ]):
        return "header"
    elif any(word in message_lower for word in ["summary", "professional summary", "profile"]):
        return "summary"
    elif any(word in message_lower for word in ["experience", "work", "employment", "job"]):
        return "experience"
    elif any(word in message_lower for word in ["skill", "technology", "tech"]):
        return "skills"
    elif any(word in message_lower for word in ["project", "portfolio"]):
        return "projects"
    elif any(word in message_lower for word in ["education", "degree", "university"]):
        return "education"
    
    return "general"


def suggest_prevention(error_type: str, normalized_issue: str, context: str) -> str:
    """
    Generate a prevention suggestion for agents.
    
    Args:
        error_type: Classified error type
        normalized_issue: Normalized issue description
        context: Context/section where error occurred
        
    Returns:
        Prevention suggestion text
    """
    if error_type == "HeaderFormatting":
        if "multiple pipes" in normalized_issue or "pipe" in normalized_issue:
            return "Header title line should use at most 2-3 pipe separators (|). Avoid excessive separators. Use '|' or '•' sparingly for visual clarity."
        return "Ensure header formatting is clean and professional. Avoid excessive separators or formatting elements."
    
    elif error_type == "Spacing":
        return "Check spacing between sections and elements. Ensure consistent, professional spacing throughout the resume."
    
    elif error_type == "Length":
        return "Verify content length fits within page limits. Use the length guard to ensure 1-2 page target."
    
    elif error_type == "Layout":
        return "Ensure proper alignment and layout. Check that all sections are properly formatted and aligned."
    
    elif error_type == "Typography":
        return "Use consistent typography throughout. Avoid excessive bold, italic, or font size variations."
    
    return "Review the design for professional appearance and consistency."


def load_design_error_memory() -> Dict[str, Any]:
    """
    Load the design error memory cache from disk.
    
    Returns:
        Dictionary with error records, or empty dict if file doesn't exist or is corrupted
    """
    if not ENABLE_DESIGN_ERROR_MEMORY:
        return {}
    
    if not DESIGN_ERROR_MEMORY_FILE.exists():
        return {}
    
    try:
        with open(DESIGN_ERROR_MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load design error memory cache: {e}")
        return {}


def save_design_error_memory(memory: Dict[str, Any]) -> None:
    """
    Save the design error memory cache to disk.
    
    Args:
        memory: Dictionary with error records
    """
    if not ENABLE_DESIGN_ERROR_MEMORY:
        return
    
    try:
        # Ensure directory exists
        DESIGN_ERROR_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Limit cache size
        if "errors" in memory and len(memory["errors"]) > MAX_CACHE_SIZE:
            # Keep most recent errors
            errors = memory["errors"]
            errors.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
            memory["errors"] = errors[:MAX_CACHE_SIZE]
            logger.debug(f"Trimmed design error cache to {MAX_CACHE_SIZE} entries")
        
        with open(DESIGN_ERROR_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        logger.warning(f"Failed to save design error memory cache: {e}")


def record_design_error(
    issue_description: str,
    context: Optional[str] = None,
    user_message: Optional[str] = None,
    section: Optional[str] = None
) -> None:
    """
    Record a design error reported by the user.
    
    Args:
        issue_description: Description of the design issue (e.g., "four pipes in header")
        context: Optional context about where the error occurred
        user_message: Optional full user message for reference
        section: Optional section name (e.g., "header", "summary")
    """
    if not ENABLE_DESIGN_ERROR_MEMORY:
        return
    
    try:
        memory = load_design_error_memory()
        
        # Initialize structure if needed
        if "errors" not in memory:
            memory["errors"] = []
        
        # Extract context if not provided
        if not context and user_message:
            context = extract_context_from_request(user_message)
        elif not context:
            context = section or "general"
        
        # Normalize issue
        normalized_issue = normalize_design_issue(issue_description)
        
        # Classify error
        error_type = classify_design_error(issue_description, context)
        
        # Generate prevention suggestion
        prevention = suggest_prevention(error_type, normalized_issue, context)
        
        # Check if we already have this error (by normalized issue + context)
        now = datetime.now().isoformat()
        existing_error = None
        for err in memory["errors"]:
            if (err.get("normalized_issue") == normalized_issue and 
                err.get("context") == context):
                existing_error = err
                break
        
        if existing_error:
            # Update existing error
            existing_error["last_seen"] = now
            existing_error["count"] = existing_error.get("count", 1) + 1
            existing_error["error_type"] = error_type
            existing_error["prevention"] = prevention
            # Update description if we have a better one
            if issue_description and len(issue_description) > len(existing_error.get("issue_description", "")):
                existing_error["issue_description"] = issue_description
        else:
            # Add new error
            new_error = {
                "issue_description": issue_description,
                "normalized_issue": normalized_issue,
                "context": context,
                "error_type": error_type,
                "prevention": prevention,
                "first_seen": now,
                "last_seen": now,
                "count": 1,
                "user_message": user_message[:200] if user_message else None,  # Store snippet
            }
            memory["errors"].append(new_error)
        
        save_design_error_memory(memory)
        logger.info(f"Recorded design error: {error_type} in {context} (count: {existing_error['count'] if existing_error else 1})")
        
    except Exception as e:
        logger.warning(f"Failed to record design error: {e}")


def detect_design_error_in_message(user_message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if a user message contains a design error report.
    
    This function looks for patterns that indicate the user is reporting
    a design issue rather than requesting a content edit.
    
    Args:
        user_message: User's message from chatbox
        
    Returns:
        Dictionary with detected error info, or None if no error detected
    """
    message_lower = user_message.lower()
    
    # Patterns that indicate error reporting
    error_indicators = [
        "there are", "there is", "there's",
        "i see", "i notice", "i found",
        "problem", "issue", "error", "bug", "wrong",
        "too many", "too much", "excessive",
        "missing", "shouldn't", "should not",
        "looks bad", "looks wrong", "doesn't look right",
        "fix the", "remove the", "get rid of"
    ]
    
    # Check if message contains error indicators
    has_error_indicator = any(indicator in message_lower for indicator in error_indicators)
    
    if not has_error_indicator:
        return None
    
    # Extract issue description
    # Look for patterns like "there are four pipes" or "too many pipes"
    issue_description = None
    
    # Pattern: "there are/is [something]"
    match = re.search(r'there (?:are|is|was|were)\s+([^\.]+)', message_lower)
    if match:
        issue_description = match.group(1).strip()
    
    # Pattern: "[something] is wrong/bad/problem"
    if not issue_description:
        match = re.search(r'([^\.]+)\s+(?:is|are|was|were)\s+(?:wrong|bad|problem|issue|error)', message_lower)
        if match:
            issue_description = match.group(1).strip()
    
    # Pattern: "too many/much [something]"
    if not issue_description:
        match = re.search(r'too (?:many|much)\s+([^\.]+)', message_lower)
        if match:
            issue_description = f"too many {match.group(1).strip()}"
    
    # Pattern: "remove/get rid of [something]"
    if not issue_description:
        match = re.search(r'(?:remove|get rid of|delete)\s+([^\.]+)', message_lower)
        if match:
            issue_description = f"remove {match.group(1).strip()}"
    
    # Fallback: use first sentence or first 50 chars
    if not issue_description:
        sentences = user_message.split('.')
        if sentences:
            issue_description = sentences[0].strip()[:100]
        else:
            issue_description = user_message[:100]
    
    if issue_description:
        context = extract_context_from_request(user_message)
        return {
            "issue_description": issue_description,
            "context": context,
            "user_message": user_message
        }
    
    return None


def lookup_design_errors(context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Look up known design errors for a given context.
    
    Args:
        context: Optional context/section (e.g., "header", "summary")
        
    Returns:
        List of error records matching the context
    """
    if not ENABLE_DESIGN_ERROR_MEMORY:
        return []
    
    try:
        memory = load_design_error_memory()
        errors = memory.get("errors", [])
        
        # Filter by context if provided
        if context:
            matching_errors = [
                err for err in errors
                if err.get("context") == context or err.get("context") == "general"
            ]
        else:
            matching_errors = errors
        
        # Sort by count (most frequent first) and last_seen (most recent first)
        matching_errors.sort(key=lambda x: (x.get("count", 0), x.get("last_seen", "")), reverse=True)
        
        return matching_errors
    except Exception as e:
        logger.warning(f"Failed to lookup design errors: {e}")
        return []


def get_prevention_guidance(context: str) -> Optional[str]:
    """
    Get prevention guidance for agents based on known design errors.
    
    Args:
        context: Section/context (e.g., "header", "summary")
        
    Returns:
        Prevention guidance string, or None if no known errors
    """
    errors = lookup_design_errors(context)
    if not errors:
        return None
    
    # Get the most frequent/recent error
    primary_error = errors[0]
    count = primary_error.get("count", 1)
    
    if count >= 2:  # Only warn if error occurred multiple times
        prevention = primary_error.get("prevention", "")
        if prevention:
            return f"⚠️ Known design issue in {context} (reported {count} times): {prevention}"
    
    return None

