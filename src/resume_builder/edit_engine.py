"""
User Edit Request Engine

This module handles natural language edit requests from users to modify resume/cover letter content.
Uses LLM only for summary and cover letter text editing. All other edits are deterministic.

Also provides LLMJsonSectionEditor for high-level JSON section editing where LLM rewrites entire JSON sections.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR
from resume_builder.json_loaders import (
    load_summary_block,
    load_selected_experiences,
    load_selected_skills,
    load_selected_projects,
    load_education_block,
    load_header_block,
    load_cover_letter,
)
from resume_builder.schema import LLMJsonEditResult
from resume_builder.utils import clean_json_content

logger = get_logger()


class EditType(Enum):
    """Types of edits that can be applied."""
    SUMMARY = "summary"
    EXPERIENCES = "experiences"
    SKILLS = "skills"
    PROJECTS = "projects"
    EDUCATION = "education"
    HEADER = "header"
    COVER_LETTER = "cover_letter"
    SECTION_REMOVAL = "section_removal"  # For removing entire sections
    UNKNOWN = "unknown"


class EditEngine:
    """Engine for processing and applying user edit requests."""
    
    def __init__(self, use_llm: bool = True, model: str = "gpt-4o-mini"):
        """
        Initialize the edit engine.
        
        Args:
            use_llm: Whether to use LLM for text edits (summary/cover letter only)
            model: LLM model to use (default: gpt-4o-mini)
        """
        self.use_llm = use_llm
        self.model = model
        self._llm_client = None
    
    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from openai import OpenAI
                self._llm_client = OpenAI()
            except ImportError:
                logger.warning("OpenAI client not available, LLM edits will be disabled")
                self.use_llm = False
        return self._llm_client
    
    def detect_edit_type(self, request: str) -> EditType:
        """Detect what type of edit is being requested."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["summary", "professional summary", "profile summary"]):
            return EditType.SUMMARY
        
        if any(word in request_lower for word in ["experience", "work", "employment", "job", "position", "role"]):
            return EditType.EXPERIENCES
        
        if any(word in request_lower for word in ["skill", "technology", "tech", "tool", "language", "framework"]):
            return EditType.SKILLS
        
        # Check for section removal first (before specific content edits)
        if "remove" in request_lower and any(word in request_lower for word in ["section", "additional info", "achievements", "summary", "experience", "education", "skills"]):
            from resume_builder.section_removal import detect_section_name
            if detect_section_name(request):
                return EditType.SECTION_REMOVAL
        
        if any(word in request_lower for word in ["project", "portfolio", "github"]):
            return EditType.PROJECTS
        
        if any(word in request_lower for word in ["education", "degree", "university", "college", "school"]):
            return EditType.EDUCATION
        
        if any(word in request_lower for word in [
            "header", "title line", "contact", "phone", "email", "location", "linkedin", "github",
            "first page", "top of", "before summary", "above summary", "at the top"
        ]):
            return EditType.HEADER
        
        if any(word in request_lower for word in ["cover letter", "letter", "cover"]):
            return EditType.COVER_LETTER
        
        return EditType.UNKNOWN
    
    def check_edit_possibility(
        self,
        edit_type: EditType,
        request: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if an edit is possible."""
        file_map = {
            EditType.SUMMARY: OUTPUT_DIR / "summary.json",
            EditType.EXPERIENCES: OUTPUT_DIR / "selected_experiences.json",
            EditType.SKILLS: OUTPUT_DIR / "selected_skills.json",
            EditType.PROJECTS: OUTPUT_DIR / "selected_projects.json",
            EditType.EDUCATION: OUTPUT_DIR / "education.json",
            EditType.HEADER: OUTPUT_DIR / "header.json",
            EditType.COVER_LETTER: OUTPUT_DIR / "cover_letter.json",
        }
        
        if edit_type == EditType.UNKNOWN:
            return False, "Could not determine what section to edit. Please be more specific."
        
        # Section removal doesn't require a file - it uses metadata
        if edit_type == EditType.SECTION_REMOVAL:
            from resume_builder.section_removal import detect_section_name
            section = detect_section_name(request)
            if not section:
                return False, "Could not detect which section to remove from your request. Please be more specific."
            return True, None
        
        file_path = file_map.get(edit_type)
        if not file_path or not file_path.exists():
            return False, f"Required file not found: {file_path.name if file_path else 'unknown'}. Please generate the resume first."
        
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["latex", "tex", "\\", "command", "macro", "template"]):
            return False, "LaTeX-specific edits are not supported. Use the LaTeX adjustment feature instead."
        
        return True, None
    
    def apply_edit(
        self,
        edit_type: EditType,
        request: str,
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply an edit to the current data."""
        if edit_type == EditType.SUMMARY:
            return self._edit_summary(request, current_data)
        elif edit_type == EditType.EXPERIENCES:
            return self._edit_experiences(request, current_data)
        elif edit_type == EditType.SKILLS:
            return self._edit_skills(request, current_data)
        elif edit_type == EditType.PROJECTS:
            return self._edit_projects(request, current_data)
        elif edit_type == EditType.EDUCATION:
            return self._edit_education(request, current_data)
        elif edit_type == EditType.HEADER:
            return self._edit_header(request, current_data)
        elif edit_type == EditType.COVER_LETTER:
            return self._edit_cover_letter(request, current_data)
        elif edit_type == EditType.SECTION_REMOVAL:
            return self._edit_section_removal(request, current_data)
        else:
            return current_data
    
    def _edit_summary(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit summary block - uses LLM only."""
        summary = current_data.get("summary", "")
        
        if self.use_llm:
            summary = self._llm_edit_text(summary, request, "summary")
        
        result = current_data.copy()
        result["summary"] = summary
        result["status"] = "success"
        result["message"] = "Summary updated successfully"
        return result
    
    def _edit_skills(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit skills list - deterministic only."""
        request_lower = request.lower()
        skills = current_data.get("selected_skills", [])
        
        # Add skill
        add_match = re.search(r'add\s+([a-z0-9\s+]+?)(?:\s+to|$)', request_lower)
        if add_match:
            new_skill = add_match.group(1).strip()
            if new_skill and new_skill not in skills:
                skills.append(new_skill)
        
        # Remove skill
        remove_match = re.search(r'remove\s+([a-z0-9\s+]+?)(?:\s+from|$)', request_lower)
        if remove_match:
            skill_to_remove = remove_match.group(1).strip()
            skills = [s for s in skills if skill_to_remove.lower() not in s.lower()]
        
        # Dedupe and sort alphabetically
        skills = sorted(list(set(skills)))
        
        result = current_data.copy()
        result["selected_skills"] = skills
        result["status"] = "success"
        result["message"] = "Skills updated successfully"
        return result
    
    def _edit_experiences(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit experiences list - deterministic only."""
        request_lower = request.lower()
        experiences = current_data.get("selected_experiences", [])
        
        # Remove experience by keyword
        if "remove" in request_lower:
            for keyword in ["first", "last", "second", "third"]:
                if keyword in request_lower:
                    if keyword == "first" and experiences:
                        experiences = experiences[1:]
                    elif keyword == "last" and experiences:
                        experiences = experiences[:-1]
                    elif keyword == "second" and len(experiences) > 1:
                        experiences = experiences[:1] + experiences[2:]
                    elif keyword == "third" and len(experiences) > 2:
                        experiences = experiences[:2] + experiences[3:]
                    break
            else:
                # Try to match by organization/title
                for exp in experiences[:]:
                    org = exp.get('organization', '').lower()
                    title = exp.get('title', '').lower()
                    if any(word in org or word in title for word in request_lower.split() if len(word) > 3):
                        experiences.remove(exp)
                        break
        
        # Swap two experiences by index
        elif "swap" in request_lower:
            swap_match = re.search(r'swap\s+(\d+)\s+and\s+(\d+)', request_lower)
            if swap_match:
                idx1 = int(swap_match.group(1)) - 1
                idx2 = int(swap_match.group(2)) - 1
                if 0 <= idx1 < len(experiences) and 0 <= idx2 < len(experiences):
                    experiences[idx1], experiences[idx2] = experiences[idx2], experiences[idx1]
        
        result = current_data.copy()
        result["selected_experiences"] = experiences
        result["status"] = "success"
        result["message"] = "Experiences updated successfully"
        return result
    
    def _edit_projects(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit projects list - deterministic only."""
        request_lower = request.lower()
        projects = current_data.get("selected_projects", [])
        
        # Remove all projects (Additional Info section)
        # This is safe - LaTeX builder will remove the section header automatically
        if "additional info" in request_lower and "remove" in request_lower:
            original_count = len(projects)
            projects = []
            logger.info(f"Removing Additional Info section: cleared {original_count} project(s). LaTeX builder will remove section header automatically.")
        # Remove by keyword
        elif "remove" in request_lower:
            for keyword in ["first", "last", "second", "third"]:
                if keyword in request_lower:
                    if keyword == "first" and projects:
                        projects = projects[1:]
                    elif keyword == "last" and projects:
                        projects = projects[:-1]
                    elif keyword == "second" and len(projects) > 1:
                        projects = projects[:1] + projects[2:]
                    elif keyword == "third" and len(projects) > 2:
                        projects = projects[:2] + projects[3:]
                    break
        
        result = current_data.copy()
        result["selected_projects"] = projects
        result["status"] = "success"
        result["message"] = "Projects updated successfully"
        return result
    
    def _edit_education(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit education - treat as static, no edits allowed."""
        return current_data
    
    def _edit_header(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit header - handles pipe character removal and simple field updates."""
        request_lower = request.lower()
        result = current_data.copy()
        changed = False
        changed_fields_list = []
        
        # Remove pipe characters from header fields
        if "pipe" in request_lower or "|" in request or ("remove" in request_lower and ("pipe" in request_lower or "|" in request)):
            # Recursively remove pipes from all string fields
            def remove_pipes_from_value(value):
                """Recursively remove pipe characters from strings in nested structures."""
                if isinstance(value, str):
                    original = value
                    cleaned = value.replace("|", "").replace("||", "").replace("|||", "").strip()
                    return cleaned, cleaned != original
                elif isinstance(value, list):
                    changed_in_list = False
                    cleaned_list = []
                    for item in value:
                        cleaned_item, item_changed = remove_pipes_from_value(item)
                        cleaned_list.append(cleaned_item)
                        if item_changed:
                            changed_in_list = True
                    return cleaned_list, changed_in_list
                elif isinstance(value, dict):
                    changed_in_dict = False
                    cleaned_dict = {}
                    for k, v in value.items():
                        cleaned_v, v_changed = remove_pipes_from_value(v)
                        cleaned_dict[k] = cleaned_v
                        if v_changed:
                            changed_in_dict = True
                    return cleaned_dict, changed_in_dict
                else:
                    return value, False
            
            # Check all fields in header
            for key in result.keys():
                if key in ["status", "message"]:
                    continue  # Skip metadata fields
                original_value = result[key]
                cleaned_value, field_changed = remove_pipes_from_value(original_value)
                if field_changed:
                    result[key] = cleaned_value
                    changed = True
                    changed_fields_list.append(key)
        
        if changed:
            result["status"] = "success"
            result["message"] = f"Header updated: removed pipe characters from {', '.join(changed_fields_list) if changed_fields_list else 'fields'}"
        else:
            result["status"] = "success"
            result["message"] = "Header unchanged (no pipe characters found or no changes needed)"
        
        return result
    
    def _edit_cover_letter(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit cover letter - uses LLM only."""
        cover_letter_md = current_data.get("cover_letter_md", "")

        if self.use_llm:
            cover_letter_md = self._llm_edit_text(cover_letter_md, request, "cover letter")

        result = current_data.copy()
        result["cover_letter_md"] = cover_letter_md
        result["status"] = "success"
        result["message"] = "Cover letter updated successfully"
        return result
    
    def _edit_section_removal(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle section removal requests.
        
        This doesn't modify JSON data - it marks sections for removal in metadata.
        The LaTeX builder will apply removals during generation.
        """
        from resume_builder.section_removal import detect_section_name, mark_section_for_removal
        
        section = detect_section_name(request)
        if section:
            mark_section_for_removal(section)
            result = current_data.copy()
            result["status"] = "success"
            result["message"] = f"Section '{section.value}' marked for removal. It will be removed from the next LaTeX generation."
            return result
        else:
            result = current_data.copy()
            result["status"] = "error"
            result["message"] = "Could not detect which section to remove from your request."
            return result
    
    def _llm_edit_text(self, text: str, request: str, context: str) -> str:
        """Use LLM to edit text content (summary/cover letter only)."""
        if not self.use_llm:
            return text
        
        try:
            client = self._get_llm_client()
            if not client:
                return text
            
            prompt = f"""You are editing a {context} based on this user request: "{request}"

Current {context}:
{text}

Apply the requested edit and return ONLY the edited {context} text. Do not add explanations, do not wrap in markdown, just return the edited text directly."""
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant that edits {context} text based on user requests."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=500
            )
            
            edited_text = response.choices[0].message.content.strip()
            edited_text = re.sub(r'^```[a-z]*\n', '', edited_text)
            edited_text = re.sub(r'\n```$', '', edited_text)
            return edited_text
        
        except Exception as e:
            logger.error(f"LLM edit failed: {e}")
            return text


def apply_edit_request(request: str) -> Dict[str, Any]:
    """
    Main entry point for applying user edit requests.
    Processes single edit requests (no recursion).
    
    Args:
        request: Natural language edit request
        
    Returns:
        Dictionary with:
        - ok: bool - Whether edit was applied
        - status: str - "applied" or "not_possible"
        - new_json: Dict - Updated JSON block (if applied)
        - changed_fields: List[str] - Fields that were modified
        - reason: str - Explanation if not possible
    """
    engine = EditEngine()
    
    # Detect edit type
    edit_type = engine.detect_edit_type(request)
    
    # Check if possible
    is_possible, reason = engine.check_edit_possibility(edit_type, request)
    
    if not is_possible:
        return {
            "ok": False,
            "status": "not_possible",
            "reason": reason,
            "new_json": None,
            "changed_fields": []
        }
    
    # Load current data
    # Section removal doesn't need a file - it uses metadata
    if edit_type == EditType.SECTION_REMOVAL:
        engine = EditEngine()
        result = engine.apply_edit(edit_type, request, {})
        return {
            "ok": result.get("status") == "success",
            "status": "applied" if result.get("status") == "success" else "not_possible",
            "new_json": result,
            "changed_fields": ["section_removal_metadata"],
            "reason": None if result.get("status") == "success" else result.get("message", "Unknown error")
        }
    
    # Map edit type to file path and loader function
    file_map = {
        EditType.SUMMARY: (OUTPUT_DIR / "summary.json", load_summary_block),
        EditType.EXPERIENCES: (OUTPUT_DIR / "selected_experiences.json", load_selected_experiences),
        EditType.SKILLS: (OUTPUT_DIR / "selected_skills.json", load_selected_skills),
        EditType.PROJECTS: (OUTPUT_DIR / "selected_projects.json", load_selected_projects),
        EditType.EDUCATION: (OUTPUT_DIR / "education.json", load_education_block),
        EditType.HEADER: (OUTPUT_DIR / "header.json", load_header_block),
        EditType.COVER_LETTER: (OUTPUT_DIR / "cover_letter.json", load_cover_letter),
    }
    
    file_path, loader_func = file_map.get(edit_type, (None, None))
    if not file_path or not loader_func:
        return {
            "ok": False,
            "status": "not_possible",
            "reason": f"Unsupported edit type: {edit_type}",
            "new_json": None,
            "changed_fields": []
        }

    try:
        current_data = loader_func(file_path)
        
        if current_data.get("status") == "error":
            return {
                "ok": False,
                "status": "not_possible",
                "reason": f"Could not load {file_path.name}: {current_data.get('message', 'Unknown error')}",
                "new_json": None,
                "changed_fields": []
            }
        
        # Apply edit
        new_data = engine.apply_edit(edit_type, request, current_data)
        
        # Determine changed fields (improved comparison)
        changed_fields = []
        all_keys = set(current_data.keys()) | set(new_data.keys())
        for key in all_keys:
            old_value = current_data.get(key)
            new_value = new_data.get(key)
            # Use JSON comparison for complex types (lists, dicts)
            if isinstance(old_value, (list, dict)) and isinstance(new_value, (list, dict)):
                import json
                old_json = json.dumps(old_value, sort_keys=True)
                new_json = json.dumps(new_value, sort_keys=True)
                if old_json != new_json:
                    changed_fields.append(key)
            elif old_value != new_value:
                changed_fields.append(key)
        
        # Save updated JSON
        file_path.write_text(json.dumps(new_data, indent=2), encoding='utf-8')
        
        return {
            "ok": True,
            "status": "applied",
            "new_json": new_data,
            "changed_fields": changed_fields,
            "reason": None
        }
    
    except Exception as e:
        logger.error(f"Error applying edit: {e}", exc_info=True)
        return {
            "ok": False,
            "status": "not_possible",
            "reason": f"Error applying edit: {str(e)}",
            "new_json": None,
            "changed_fields": []
        }


# Export LLM JSON editing functions
from resume_builder.edit_engine_llm_json import (
    LLMJsonSectionEditor,
    apply_llm_json_edit,
    SECTION_TO_JSON_PATH,
)
