"""Shared utility functions for resume builder.

This module contains common functions used across multiple modules to avoid duplication.
"""

from __future__ import annotations


def clean_json_content(content: str) -> str:
    """
    Clean JSON content by removing markdown code blocks, invalid control characters, and extra whitespace.
    
    Agents sometimes wrap JSON in ```json ... ``` which breaks parsing, or include extra text after JSON.
    This function removes those markdown fences, invalid control characters, extracts the first valid JSON,
    and normalizes whitespace.
    
    Args:
        content: Raw content that may contain markdown code fences, invalid control characters, or extra text
        
    Returns:
        Cleaned content with only the first valid JSON object/array, without markdown fences and invalid control characters
    """
    import re
    import json as json_module
    content = content.strip()
    
    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    if content.startswith('```'):
        lines = content.split('\n')
        # Remove first line (```json or ```)
        if lines[0].startswith('```'):
            lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        content = '\n'.join(lines)
    
    # Remove invalid control characters (except newline, tab, carriage return)
    # JSON spec allows: \n, \r, \t, but not other control chars (0x00-0x1F except those)
    # We'll replace invalid control chars with spaces or remove them
    # Keep: \n (0x0A), \r (0x0D), \t (0x09)
    # Remove/replace: others in 0x00-0x1F range
    def replace_control_char(match):
        char_code = ord(match.group(0))
        # Allow newline, carriage return, tab
        if char_code in (0x09, 0x0A, 0x0D):
            return match.group(0)
        # Replace other control chars with space
        return ' '
    
    # Pattern to match control characters (0x00-0x1F) except allowed ones
    content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', replace_control_char, content)
    content = content.strip()
    
    # Try to extract first valid JSON object/array if there's extra data after it
    # Look for the first complete JSON object or array
    try:
        # Try parsing the whole content first
        json_module.loads(content)
        return content
    except json_module.JSONDecodeError:
        # If that fails, try to find the first complete JSON object/array
        # Look for opening brace or bracket
        for start_char in ['{', '[']:
            start_idx = content.find(start_char)
            if start_idx == -1:
                continue
            
            # Find matching closing brace/bracket
            depth = 0
            in_string = False
            escape_next = False
            end_idx = -1
            
            for i in range(start_idx, len(content)):
                char = content[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == start_char:
                        depth += 1
                    elif char == ('}' if start_char == '{' else ']'):
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
            
            if end_idx > start_idx:
                # Extract the JSON portion
                json_content = content[start_idx:end_idx]
                try:
                    # Validate it's actually valid JSON
                    json_module.loads(json_content)
                    return json_content
                except json_module.JSONDecodeError:
                    continue
        
        # If we couldn't extract valid JSON, return the cleaned content as-is
        # (let the caller handle the error)
        return content


def clean_markdown_fences(content: str) -> str:
    """
    Remove markdown code fences from content (generic version for LaTeX, etc.).
    
    Similar to clean_json_content but more generic for non-JSON content.
    
    Args:
        content: Content that may contain markdown code fences
        
    Returns:
        Cleaned content without markdown fences
    """
    content = content.strip()
    
    # Remove markdown code fences (```language ... ``` or ``` ... ```)
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line if it's a code fence
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it's a code fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    
    return content.strip()


def extract_braces(text: str, start_pos: int) -> tuple[str | None, int]:
    """
    Extract content from balanced braces starting at start_pos.
    
    Handles escaped characters and nested braces correctly.
    Used for parsing LaTeX commands with arguments.
    
    Args:
        text: Text to search in
        start_pos: Starting position (must point to '{')
        
    Returns:
        Tuple of (extracted_content, next_position) or (None, start_pos) if not found
    """
    if start_pos >= len(text) or text[start_pos] != '{':
        return None, start_pos
    
    brace_count = 0
    i = start_pos
    content_start = start_pos + 1
    
    while i < len(text):
        # Skip escaped characters
        if text[i] == '\\' and i + 1 < len(text):
            i += 2
            continue
        
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[content_start:i], i + 1
        
        i += 1
    
    # Unbalanced braces - return None
    return None, start_pos

