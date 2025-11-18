"""
JSON Diff Computation for Resume Sections

Computes differences between old and new JSON to show what changed.
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Set

from resume_builder.logger import get_logger

logger = get_logger()

# Try to use deepdiff if available, otherwise use simple diff
try:
    from deepdiff import DeepDiff
    HAS_DEEPDIFF = True
except ImportError:
    HAS_DEEPDIFF = False
    logger.warning("deepdiff not available, using simple diff implementation")


def compute_json_diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a human-readable diff between two JSON objects.
    
    Uses deepdiff if available and data is small enough, otherwise uses simple diff.
    
    Args:
        old: Original JSON
        new: Updated JSON
        
    Returns:
        Dictionary with diff information:
        {
            "added": [...],
            "removed": [...],
            "modified": [...],
            "summary": "..."
        }
    """
    # Heuristic: if JSON is very large, use simple diff (deepdiff can be slow)
    try:
        old_size = len(json.dumps(old))
        new_size = len(json.dumps(new))
        total_size = old_size + new_size
        SIZE_THRESHOLD = 50000  # 50k chars
        
        if total_size > SIZE_THRESHOLD:
            logger.debug(f"Large JSON detected ({total_size} chars), using simple diff")
            return _compute_diff_simple(old, new)
    except Exception:
        # If size check fails, proceed with normal diff
        pass
    
    if HAS_DEEPDIFF:
        return _compute_diff_deepdiff(old, new)
    else:
        return _compute_diff_simple(old, new)


def _compute_diff_deepdiff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Compute diff using deepdiff library."""
    try:
        diff = DeepDiff(old, new, ignore_order=False, verbose_level=2)
        
        result = {
            "added": [],
            "removed": [],
            "modified": [],
            "summary": ""
        }
        
        # Extract added items
        if "dictionary_item_added" in diff:
            for item in diff["dictionary_item_added"]:
                result["added"].append(str(item))
        
        # Extract removed items
        if "dictionary_item_removed" in diff:
            for item in diff["dictionary_item_removed"]:
                result["removed"].append(str(item))
        
        # Extract modified items
        if "values_changed" in diff:
            for key, change in diff["values_changed"].items():
                result["modified"].append({
                    "path": str(key),
                    "old_value": str(change.get("old_value", ""))[:100],  # Truncate long values
                    "new_value": str(change.get("new_value", ""))[:100]
                })
        
        # Extract list changes
        if "iterable_item_added" in diff:
            for item in diff["iterable_item_added"]:
                result["added"].append(f"List item added: {item}")
        
        if "iterable_item_removed" in diff:
            for item in diff["iterable_item_removed"]:
                result["removed"].append(f"List item removed: {item}")
        
        # Build summary
        total_changes = len(result["added"]) + len(result["removed"]) + len(result["modified"])
        if total_changes == 0:
            result["summary"] = "No changes detected"
        else:
            parts = []
            if result["added"]:
                parts.append(f"{len(result['added'])} added")
            if result["removed"]:
                parts.append(f"{len(result['removed'])} removed")
            if result["modified"]:
                parts.append(f"{len(result['modified'])} modified")
            result["summary"] = ", ".join(parts)
        
        return result
        
    except Exception as e:
        logger.error(f"Error computing JSON diff: {e}")
        return {
            "added": [],
            "removed": [],
            "modified": [],
            "summary": f"Diff computation error: {str(e)}"
        }


def _compute_diff_simple(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Simple diff implementation when deepdiff is not available."""
    result = {
        "added": [],
        "removed": [],
        "modified": [],
        "summary": ""
    }
    
    # Compare top-level keys
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    
    # Added keys
    for key in new_keys - old_keys:
        result["added"].append(f"Key '{key}' added")
    
    # Removed keys
    for key in old_keys - new_keys:
        result["removed"].append(f"Key '{key}' removed")
    
    # Modified keys
    for key in old_keys & new_keys:
        old_val = old[key]
        new_val = new[key]
        
        if old_val != new_val:
            # For lists, check if it's a length change or content change
            if isinstance(old_val, list) and isinstance(new_val, list):
                if len(old_val) != len(new_val):
                    result["modified"].append({
                        "path": key,
                        "old_value": f"List with {len(old_val)} items",
                        "new_value": f"List with {len(new_val)} items"
                    })
                else:
                    # Check for item changes
                    for i, (old_item, new_item) in enumerate(zip(old_val, new_val)):
                        if old_item != new_item:
                            result["modified"].append({
                                "path": f"{key}[{i}]",
                                "old_value": str(old_item)[:100],
                                "new_value": str(new_item)[:100]
                            })
            else:
                result["modified"].append({
                    "path": key,
                    "old_value": str(old_val)[:100],
                    "new_value": str(new_val)[:100]
                })
    
    # Build summary
    total_changes = len(result["added"]) + len(result["removed"]) + len(result["modified"])
    if total_changes == 0:
        result["summary"] = "No changes detected"
    else:
        parts = []
        if result["added"]:
            parts.append(f"{len(result['added'])} added")
        if result["removed"]:
            parts.append(f"{len(result['removed'])} removed")
        if result["modified"]:
            parts.append(f"{len(result['modified'])} modified")
        result["summary"] = ", ".join(parts)
    
    return result


def format_diff_for_display(diff: Dict[str, Any]) -> str:
    """
    Format diff result as a human-readable string.
    
    Args:
        diff: Diff result from compute_json_diff
        
    Returns:
        Formatted string
    """
    lines = [f"📊 Changes: {diff['summary']}"]
    
    if diff["added"]:
        lines.append("\n➕ Added:")
        for item in diff["added"][:10]:  # Limit to 10 items
            lines.append(f"  • {item}")
        if len(diff["added"]) > 10:
            lines.append(f"  ... and {len(diff['added']) - 10} more")
    
    if diff["removed"]:
        lines.append("\n➖ Removed:")
        for item in diff["removed"][:10]:
            lines.append(f"  • {item}")
        if len(diff["removed"]) > 10:
            lines.append(f"  ... and {len(diff['removed']) - 10} more")
    
    if diff["modified"]:
        lines.append("\n✏️ Modified:")
        for change in diff["modified"][:10]:
            lines.append(f"  • {change['path']}")
            lines.append(f"    Old: {change['old_value']}")
            lines.append(f"    New: {change['new_value']}")
        if len(diff["modified"]) > 10:
            lines.append(f"  ... and {len(diff['modified']) - 10} more")
    
    return "\n".join(lines)


def summarize_diff_for_ui(diff: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a minimal structured summary of diff for UI consumption.
    
    Args:
        diff: Diff result from compute_json_diff
        
    Returns:
        {
            "added_count": int,
            "removed_count": int,
            "modified_count": int,
            "example_changes": [{"path": "...", "old_value": "...", "new_value": "..."}]
        }
    """
    example_changes = []
    
    # Include up to 3 example modifications
    if diff.get("modified"):
        for change in diff["modified"][:3]:
            example_changes.append({
                "path": change.get("path", ""),
                "old_value": str(change.get("old_value", ""))[:100],  # Truncate
                "new_value": str(change.get("new_value", ""))[:100],
            })
    
    return {
        "added_count": len(diff.get("added", [])),
        "removed_count": len(diff.get("removed", [])),
        "modified_count": len(diff.get("modified", [])),
        "example_changes": example_changes,
    }

