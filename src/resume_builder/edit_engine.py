"""
User Edit Request Engine

This module handles natural language edit requests from users to modify resume/cover letter content.
It determines if edits are possible and applies transformations to JSON blocks while preserving schemas.
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
    UNKNOWN = "unknown"


class EditEngine:
    """Engine for processing and applying user edit requests."""
    
    def __init__(self, use_llm: bool = True, model: str = "gpt-4o-mini"):
        """
        Initialize the edit engine.
        
        Args:
            use_llm: Whether to use LLM for complex edits (default: True)
            model: LLM model to use (default: gpt-4o-mini for cost optimization)
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
        """
        Detect what type of edit is being requested.
        
        Args:
            request: Natural language edit request
            
        Returns:
            EditType enum indicating the type of edit
        """
        request_lower = request.lower()
        
        # Summary edits
        if any(word in request_lower for word in ["summary", "professional summary", "profile summary"]):
            return EditType.SUMMARY
        
        # Experience edits
        if any(word in request_lower for word in ["experience", "work", "employment", "job", "position", "role"]):
            return EditType.EXPERIENCES
        
        # Skills edits
        if any(word in request_lower for word in ["skill", "technology", "tech", "tool", "language", "framework"]):
            return EditType.SKILLS
        
        # Projects edits
        if any(word in request_lower for word in ["project", "portfolio", "github"]):
            return EditType.PROJECTS
        
        # Education edits
        if any(word in request_lower for word in ["education", "degree", "university", "college", "school"]):
            return EditType.EDUCATION
        
        # Header edits (including pipe character removal from title line)
        if any(word in request_lower for word in ["header", "title line", "contact", "phone", "email", "linkedin", "github", "|", "pipe"]):
            return EditType.HEADER
        
        # Additional Info section edits (treat as projects since that's what populates it)
        if any(word in request_lower for word in ["additional info", "additional information", "additional section"]):
            # Check if it's a removal request - if so, handle as projects removal
            if "remove" in request_lower:
                return EditType.PROJECTS
            # Otherwise, could be header or projects depending on context
            return EditType.PROJECTS
        
        # Cover letter edits
        if any(word in request_lower for word in ["cover letter", "letter", "cover"]):
            return EditType.COVER_LETTER
        
        return EditType.UNKNOWN
    
    def check_edit_possibility(
        self,
        edit_type: EditType,
        request: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an edit is possible.
        
        Args:
            edit_type: Type of edit being requested
            request: Natural language edit request
            
        Returns:
            Tuple of (is_possible, reason_if_not)
        """
        # Check if required JSON file exists
        file_map = {
            EditType.SUMMARY: OUTPUT_DIR / "summary_block.json",
            EditType.EXPERIENCES: OUTPUT_DIR / "selected_experiences.json",
            EditType.SKILLS: OUTPUT_DIR / "selected_skills.json",
            EditType.PROJECTS: OUTPUT_DIR / "selected_projects.json",
            EditType.EDUCATION: OUTPUT_DIR / "education_block.json",
            EditType.HEADER: OUTPUT_DIR / "header_block.json",
            EditType.COVER_LETTER: OUTPUT_DIR / "cover_letter.json",
        }
        
        if edit_type == EditType.UNKNOWN:
            return False, "Could not determine what section to edit. Please be more specific (e.g., 'summary', 'skills', 'experiences')."
        
        file_path = file_map.get(edit_type)
        if not file_path or not file_path.exists():
            return False, f"Required file not found: {file_path.name}. Please generate the resume first."
        
        # Check for impossible operations
        request_lower = request.lower()
        
        # Structural changes that might break LaTeX
        if any(word in request_lower for word in ["change template", "modify template", "alter template structure"]):
            return False, "Template structure changes are not supported. Use template matching feature instead."
        
        # Check for edits that require LaTeX knowledge
        if any(word in request_lower for word in ["latex", "tex", "\\", "command", "macro"]):
            return False, "LaTeX-specific edits are not supported. Use the LaTeX adjustment feature in the UI instead."
        
        return True, None
    
    def apply_edit(
        self,
        edit_type: EditType,
        request: str,
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply an edit to the current data.
        
        Args:
            edit_type: Type of edit being requested
            request: Natural language edit request
            current_data: Current JSON data to modify
            
        Returns:
            Updated JSON data with the same schema
        """
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
        else:
            return current_data
    
    def _edit_summary(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit summary block."""
        request_lower = request.lower()
        summary = current_data.get("summary", "")
        
        # Simple deterministic edits
        if "shorter" in request_lower or "reduce" in request_lower or "condense" in request_lower:
            # Split into sentences and take first 2
            sentences = re.split(r'[.!?]+', summary)
            sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) > 2:
                summary = ". ".join(sentences[:2]) + "."
        
        elif "longer" in request_lower or "expand" in request_lower or "add detail" in request_lower:
            # Use LLM to expand
            if self.use_llm:
                summary = self._llm_edit_text(summary, request, "summary")
        
        elif "focus" in request_lower or "emphasize" in request_lower:
            # Use LLM to refocus
            if self.use_llm:
                summary = self._llm_edit_text(summary, request, "summary")
        
        else:
            # Generic edit - use LLM
            if self.use_llm:
                summary = self._llm_edit_text(summary, request, "summary")
        
        # Preserve schema
        result = current_data.copy()
        result["summary"] = summary
        result["status"] = "success"
        result["message"] = "Summary updated successfully"
        return result
    
    def _edit_skills(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit skills list."""
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
        
        # Reorder (use LLM for complex reordering)
        if "reorder" in request_lower or "prioritize" in request_lower:
            if self.use_llm:
                skills = self._llm_edit_list(skills, request, "skills")
        
        # Preserve schema
        result = current_data.copy()
        result["selected_skills"] = skills
        result["status"] = "success"
        result["message"] = "Skills updated successfully"
        return result
    
    def _edit_experiences(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit experiences list."""
        request_lower = request.lower()
        experiences = current_data.get("selected_experiences", [])
        
        # Swap/reorder experiences
        if "swap" in request_lower or "move" in request_lower or "reorder" in request_lower:
            # Use LLM for complex reordering
            if self.use_llm:
                experiences = self._llm_edit_list(experiences, request, "experiences")
        
        # Remove experience
        elif "remove" in request_lower:
            # Try to identify which experience to remove
            if self.use_llm:
                experiences = self._llm_edit_list(experiences, request, "experiences")
        
        # Modify experience content
        elif "modify" in request_lower or "change" in request_lower or "update" in request_lower:
            if self.use_llm:
                experiences = self._llm_edit_list(experiences, request, "experiences")
        
        # Preserve schema
        result = current_data.copy()
        result["selected_experiences"] = experiences
        result["status"] = "success"
        result["message"] = "Experiences updated successfully"
        return result
    
    def _edit_projects(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit projects list."""
        request_lower = request.lower()
        projects = current_data.get("selected_projects", [])
        
        # Handle "remove additional info section" - this means remove all projects
        if "additional info" in request_lower or "additional information" in request_lower:
            if "remove" in request_lower:
                # Remove all projects (which populates the Additional Info section)
                projects = []
                result = current_data.copy()
                result["selected_projects"] = projects
                result["status"] = "success"
                result["message"] = "Removed Additional Info section (all projects removed)"
                return result
        
        # Similar to experiences
        if any(word in request_lower for word in ["swap", "move", "reorder", "remove", "modify", "change"]):
            if self.use_llm:
                projects = self._llm_edit_list(projects, request, "projects")
        
        # Preserve schema
        result = current_data.copy()
        result["selected_projects"] = projects
        result["status"] = "success"
        result["message"] = "Projects updated successfully"
        return result
    
    def _edit_education(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit education list."""
        # Education is usually just extraction, but allow edits
        if self.use_llm:
            education = current_data.get("education", [])
            education = self._llm_edit_list(education, request, "education")
            result = current_data.copy()
            result["education"] = education
            result["status"] = "success"
            result["message"] = "Education updated successfully"
            return result
        return current_data
    
    def _edit_header(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit header block."""
        request_lower = request.lower()
        result = current_data.copy()
        title_line = result.get("title_line", "")
        
        # Handle pipe character removal
        if "|" in request or "pipe" in request_lower or ("remove" in request_lower and "|" in title_line):
            # Remove pipe characters from title line
            if title_line:
                # Remove pipes and clean up spacing
                new_title = title_line.replace("|", "").replace("  ", " ").strip()
                # Optionally replace with commas or just remove
                result["title_line"] = new_title
                result["status"] = "success"
                result["message"] = "Removed pipe characters from title line"
                return result
        
        # Other header edits - use LLM if available
        if self.use_llm:
            # Use LLM to modify header
            result = self._llm_edit_dict(result, request, "header")
            result["status"] = "success"
            result["message"] = "Header updated successfully"
            return result
        
        return current_data
    
    def _edit_cover_letter(self, request: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit cover letter."""
        request_lower = request.lower()
        cover_letter_md = current_data.get("cover_letter_md", "")
        
        # Simple edits
        if "shorter" in request_lower or "condense" in request_lower:
            # Split into paragraphs and take first 2-3
            paragraphs = cover_letter_md.split("\n\n")
            if len(paragraphs) > 3:
                cover_letter_md = "\n\n".join(paragraphs[:3])
        
        elif "longer" in request_lower or "expand" in request_lower:
            if self.use_llm:
                cover_letter_md = self._llm_edit_text(cover_letter_md, request, "cover letter")
        
        elif any(word in request_lower for word in ["tone", "style", "focus", "emphasize"]):
            if self.use_llm:
                cover_letter_md = self._llm_edit_text(cover_letter_md, request, "cover letter")
        
        else:
            if self.use_llm:
                cover_letter_md = self._llm_edit_text(cover_letter_md, request, "cover letter")
        
        # Preserve schema
        result = current_data.copy()
        result["cover_letter_md"] = cover_letter_md
        result["status"] = "success"
        result["message"] = "Cover letter updated successfully"
        return result
    
    def _llm_edit_text(self, text: str, request: str, context: str) -> str:
        """Use LLM to edit text content."""
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
            # Remove markdown fences if present
            edited_text = re.sub(r'^```[a-z]*\n', '', edited_text)
            edited_text = re.sub(r'\n```$', '', edited_text)
            return edited_text
        
        except Exception as e:
            logger.error(f"LLM edit failed: {e}")
            return text
    
    def _llm_edit_list(self, items: List[Dict[str, Any]], request: str, context: str) -> List[Dict[str, Any]]:
        """Use LLM to edit a list of items."""
        if not self.use_llm:
            return items
        
        try:
            client = self._get_llm_client()
            if not client:
                return items
            
            items_json = json.dumps(items, indent=2)
            prompt = f"""You are editing a {context} list based on this user request: "{request}"

Current {context} list (JSON):
{items_json}

Apply the requested edit and return ONLY the edited JSON array. Preserve all field names and structure. Do not add explanations, do not wrap in markdown code fences."""
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant that edits {context} JSON arrays based on user requests. Always preserve the exact schema."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=2000
            )
            
            edited_json_str = response.choices[0].message.content.strip()
            # Remove markdown fences if present
            edited_json_str = re.sub(r'^```json\n', '', edited_json_str)
            edited_json_str = re.sub(r'^```\n', '', edited_json_str)
            edited_json_str = re.sub(r'\n```$', '', edited_json_str)
            
            edited_items = json.loads(edited_json_str)
            return edited_items
        
        except Exception as e:
            logger.error(f"LLM list edit failed: {e}")
            return items
    
    def _llm_edit_dict(self, data: Dict[str, Any], request: str, context: str) -> Dict[str, Any]:
        """Use LLM to edit a dictionary."""
        if not self.use_llm:
            return data
        
        try:
            client = self._get_llm_client()
            if not client:
                return data
            
            data_json = json.dumps(data, indent=2)
            prompt = f"""You are editing a {context} JSON object based on this user request: "{request}"

Current {context} (JSON):
{data_json}

Apply the requested edit and return ONLY the edited JSON object. Preserve all field names and structure. Do not add explanations, do not wrap in markdown code fences."""
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant that edits {context} JSON objects based on user requests. Always preserve the exact schema."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=1000
            )
            
            edited_json_str = response.choices[0].message.content.strip()
            # Remove markdown fences if present
            edited_json_str = re.sub(r'^```json\n', '', edited_json_str)
            edited_json_str = re.sub(r'^```\n', '', edited_json_str)
            edited_json_str = re.sub(r'\n```$', '', edited_json_str)
            
            edited_data = json.loads(edited_json_str)
            return edited_data
        
        except Exception as e:
            logger.error(f"LLM dict edit failed: {e}")
            return data


def apply_edit_request(request: str) -> Dict[str, Any]:
    """
    Main entry point for applying user edit requests.
    Supports multiple edits in a single request (e.g., "remove pipes and remove additional info section").
    
    Args:
        request: Natural language edit request (e.g., "Make my summary shorter", "Add AWS to skills")
        
    Returns:
        Dictionary with:
        - ok: bool - Whether edit was applied
        - status: str - "applied" or "not_possible"
        - new_json: Dict - Updated JSON block (if applied)
        - changed_fields: List[str] - Fields that were modified
        - reason: str - Explanation if not possible
    """
    engine = EditEngine()
    
    # Check if request contains multiple edits (common separators: "also", "and", comma, period)
    # Split on common separators and process each part
    request_lower = request.lower()
    parts = []
    
    # Split on "also", "and", or multiple sentences
    if " also " in request_lower or " and " in request_lower:
        # Try to split intelligently
        if " also " in request_lower:
            parts = [p.strip() for p in request.split(" also ", 1)]
        elif " and " in request_lower:
            parts = [p.strip() for p in request.split(" and ", 1)]
    elif ". " in request and len(request.split(". ")) > 1:
        # Multiple sentences
        parts = [p.strip() for p in request.split(". ") if p.strip()]
    
    # If we detected multiple parts, process them sequentially
    if len(parts) > 1:
        all_changed_fields = []
        all_results = []
        
        for part in parts:
            result = apply_edit_request(part)  # Recursive call
            all_results.append(result)
            if result.get("ok"):
                all_changed_fields.extend(result.get("changed_fields", []))
        
        # Return combined result
        if any(r.get("ok") for r in all_results):
            return {
                "ok": True,
                "status": "applied",
                "new_json": None,  # Multiple files may have been updated
                "changed_fields": list(set(all_changed_fields)),  # Remove duplicates
                "reason": None
            }
        else:
            # All failed - return first error
            return all_results[0]
    
    # Single edit request - process normally
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
    file_map = {
        EditType.SUMMARY: ("summary_block.json", load_summary_block),
        EditType.EXPERIENCES: ("selected_experiences.json", load_selected_experiences),
        EditType.SKILLS: ("selected_skills.json", load_selected_skills),
        EditType.PROJECTS: ("selected_projects.json", load_selected_projects),
        EditType.EDUCATION: ("education_block.json", load_education_block),
        EditType.HEADER: ("header_block.json", load_header_block),
        EditType.COVER_LETTER: ("cover_letter.json", load_cover_letter),
    }
    
    file_name, loader_func = file_map[edit_type]
    file_path = OUTPUT_DIR / file_name
    
    try:
        current_data = loader_func(file_path)
        
        # Check if data loaded successfully
        if current_data.get("status") == "error":
            return {
                "ok": False,
                "status": "not_possible",
                "reason": f"Could not load {file_name}: {current_data.get('message', 'Unknown error')}",
                "new_json": None,
                "changed_fields": []
            }
        
        # Apply edit
        new_data = engine.apply_edit(edit_type, request, current_data)
        
        # Determine changed fields
        changed_fields = []
        for key in new_data.keys():
            if key in current_data and new_data[key] != current_data[key]:
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

