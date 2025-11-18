"""
LLM JSON Section Editor

High-level JSON editor: LLM rewrites a single section's JSON according to a user instruction,
then we deterministically validate and write the updated JSON back to disk.

The LLM never sees or edits LaTeX - it only works with JSON sections.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from resume_builder.logger import get_logger
from resume_builder.paths import OUTPUT_DIR
from resume_builder.schema import LLMJsonEditResult
from resume_builder.utils import clean_json_content
from resume_builder.json_validators import validate_section_json
from resume_builder.json_diff import compute_json_diff, format_diff_for_display, summarize_diff_for_ui

logger = get_logger()


# ============================================================================
# Single Source of Truth: Section Metadata
# ============================================================================

# Section name → JSON filename mapping
SECTION_TO_JSON_PATH = {
    "summary": "summary.json",
    "header": "header.json",
    "experiences": "selected_experiences.json",
    "projects": "selected_projects.json",
    "skills": "selected_skills.json",
    "education": "education.json",
    "cover_letter": "cover_letter.json",
}

# Section name → human-readable description
SECTION_DESCRIPTIONS = {
    "summary": "Professional Summary",
    "header": "Header/Contact Information",
    "experiences": "Work Experiences",
    "projects": "Projects/Portfolio",
    "skills": "Skills & Technologies",
    "education": "Education",
    "cover_letter": "Cover Letter",
}

# Section name → validator key (must match keys in json_validators.SECTION_VALIDATORS)
# Note: Section names match validator keys exactly
SECTION_VALIDATOR_KEYS = {
    "summary": "summary",
    "header": "header",
    "experiences": "experiences",
    "projects": "projects",
    "skills": "skills",
    "education": "education",
    "cover_letter": "cover_letter",
}


def get_section_metadata(section: str) -> Dict[str, str]:
    """
    Get all metadata for a section (single source of truth).
    
    Returns:
        {
            "json_file": "summary.json",
            "description": "Professional Summary",
            "validator_key": "summary"
        }
    """
    if section not in SECTION_TO_JSON_PATH:
        raise ValueError(f"Unknown section '{section}'. Valid sections: {list(SECTION_TO_JSON_PATH.keys())}")
    
    return {
        "json_file": SECTION_TO_JSON_PATH[section],
        "description": SECTION_DESCRIPTIONS.get(section, section.title()),
        "validator_key": SECTION_VALIDATOR_KEYS.get(section, section),
    }


def _get_llm_client_and_model():
    """Get OpenAI client and model name."""
    from openai import OpenAI
    
    client = OpenAI()
    model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
    return client, model


class LLMJsonSectionEditor:
    """
    High-level JSON editor: LLM rewrites a single section's JSON
    according to a user instruction, then we deterministically
    validate and write the updated JSON back to disk.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else OUTPUT_DIR

    def _resolve_section_path(self, section: str) -> Path:
        """Resolve the JSON file path for a section."""
        if section not in SECTION_TO_JSON_PATH:
            raise ValueError(f"Unknown section '{section}'. Valid sections: {list(SECTION_TO_JSON_PATH.keys())}")
        return self.base_dir / SECTION_TO_JSON_PATH[section]

    def _load_section_json(self, section: str) -> Dict[str, Any]:
        """Load and parse the JSON for a section."""
        path = self._resolve_section_path(section)
        if not path.exists():
            raise FileNotFoundError(f"JSON file for section '{section}' not found: {path}")
        
        text = path.read_text(encoding="utf-8")
        text = clean_json_content(text)
        return json.loads(text)

    def _save_section_json(self, section: str, data: Dict[str, Any]) -> None:
        """Save JSON data to section file atomically."""
        path = self._resolve_section_path(section)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        
        txt = json.dumps(data, ensure_ascii=False, indent=2)
        tmp_path.write_text(txt, encoding="utf-8")
        tmp_path.replace(path)
        logger.info(f"Saved updated JSON for section '{section}': {path}")

    def _build_prompt(self, section: str, user_instruction: str, original_data: Dict[str, Any], strict: bool = False) -> str:
        """
        Build a strict prompt telling the LLM to:
        - Preserve the overall schema for this section
        - Only change content in allowed fields
        - Not invent employment, dates, or degrees
        
        Strict mode vs Normal mode:
        - Normal mode: LLM can add/remove items, reorder, rewrite text
        - Strict mode: LLM can ONLY rewrite text within existing fields, cannot change structure
        """
        
        # Add strict mode instructions
        strict_mode_note = ""
        if strict:
            strict_mode_note = """
⚠️ STRICT MODE ENABLED:
- Do NOT add or remove any list items (experiences, projects, education entries, skills).
- Do NOT add or remove any top-level keys.
- ONLY rewrite text content within existing fields.
- Preserve the exact structure and count of all arrays and objects.
"""
        
        # Specialize per-section guidance with examples
        if section == "summary":
            section_rules = """
- Keep the same factual information (companies, institutions, dates, degrees).
- You may rephrase for clarity and concision.
- Use 2–3 sentences, max ~90 words.
- Return JSON with the same keys as input: {status, message, summary, approx_word_count}.

Example transformation:
Input: {"status": "success", "summary": "Software engineer with 5 years experience."}
Instruction: "Make it more technical and emphasize AI/ML"
Output: {"status": "success", "summary": "Software engineer with 5 years of experience specializing in AI/ML systems and machine learning pipelines."}
"""
        elif section == "experiences":
            section_rules = """
- Keep the same set of experiences, companies, and dates.
- You may rewrite bullet points for clarity and impact.
- You may drop low-value bullets if needed for brevity (unless in strict mode).
- Return JSON with the same top-level structure as input (selected_experiences array etc.).
- Each experience must have: title, organization (or company), bullets (list of strings).

Example: If input has 3 experiences, output must have exactly 3 experiences (unless strict mode allows removal).
"""
        elif section == "skills":
            section_rules = """
- Preserve the list structure.
- You may reorder, add, or remove skills based on the instruction.
- Return JSON with the same top-level structure as input.
"""
        elif section == "projects":
            section_rules = """
- Keep the same set of projects.
- You may rewrite descriptions and bullet points.
- Return JSON with the same top-level structure as input (selected_projects array etc.).
"""
        elif section == "education":
            section_rules = """
- Preserve all factual details (institutions, degrees, dates).
- Do not add new degrees or institutions.
- Return JSON with exactly the same schema as the input.
"""
        elif section == "header":
            section_rules = """
- Preserve ALL contact information (email, phone, location, links).
- Preserve ALL fields exactly as they are (name, email, phone, location, links, target_title).
- If removing pipe characters (|), ONLY remove the pipe characters from text fields, do NOT change any other content.
- Do NOT remove or modify any fields.
- Do NOT change the structure of links array.
- Return JSON with the EXACT same top-level structure and fields as input.
- ONLY modify text content within existing fields (e.g., remove | from name or title_line if present).
"""
        elif section == "cover_letter":
            section_rules = """
- Preserve factual information about the job and company.
- You may rewrite paragraphs for tone, clarity, or emphasis.
- Return JSON with the same top-level structure as input (cover_letter_md field etc.).
"""
        else:
            section_rules = """
- Preserve all factual details (companies, institutions, dates).
- Do not add new employers, degrees, or years.
- Return JSON with exactly the same schema as the input.
"""

        return f"""You are a resume content editor. The resume is represented as JSON.

You will receive:
1) The target section name
2) The user's edit instruction
3) The current JSON for that section

Your task:
- Modify the JSON content to follow the user instruction.
- Obey the section-specific rules.
- Preserve all factual information (companies, degrees, dates).
- Do NOT invent new jobs, employers, or degrees.
- Return ONLY a single JSON object, no markdown, no explanation.

{strict_mode_note}

Section: {section}

User instruction:
\"\"\"{user_instruction}\"\"\"

Section-specific rules:
{section_rules}

Current JSON:
```json
{json.dumps(original_data, ensure_ascii=False, indent=2)}
```

Return the edited JSON object only (no markdown fences, no explanation):"""

    def _call_llm_for_section(
        self,
        section: str,
        user_instruction: str,
        original_data: Dict[str, Any],
        strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Call LLM to generate updated JSON for a section.
        
        Returns:
            Updated JSON dict
            
        Raises:
            ValueError: If LLM call fails or returns invalid JSON
        """
        client, model = _get_llm_client_and_model()
        prompt = self._build_prompt(section, user_instruction, original_data, strict=strict)
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant that edits resume {section} JSON based on user requests. Always return valid JSON only, no markdown, no explanations."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            
            raw = response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"LLM call failed for section '{section}': {e}")
            raise ValueError(f"LLM call failed: {e}")

        # Parse LLM JSON
        try:
            cleaned = clean_json_content(raw)
            updated = json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON for section '{section}': {e}")
            raise ValueError(f"Failed to parse LLM JSON: {e}")

        # Basic validation: ensure it's a dict
        if not isinstance(updated, dict):
            raise ValueError("LLM returned non-dict JSON for section")

        return updated

    def _check_strict_mode_compliance(
        self,
        original_data: Dict[str, Any],
        updated: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if updated JSON complies with strict mode (no structural changes).
        
        Returns:
            (is_compliant, error_message)
        """
        # Check top-level keys
        original_keys = set(original_data.keys())
        updated_keys = set(updated.keys())
        
        if original_keys != updated_keys:
            added = updated_keys - original_keys
            removed = original_keys - updated_keys
            return False, f"Strict mode violation: keys {'added' if added else 'removed'}: {list(added | removed)}"
        
        # Check list lengths for common list fields
        list_fields = ["selected_experiences", "selected_projects", "selected_skills", "skills", "education"]
        for field in list_fields:
            if field in original_data and field in updated:
                orig_list = original_data[field]
                upd_list = updated[field]
                if isinstance(orig_list, list) and isinstance(upd_list, list):
                    if len(orig_list) != len(upd_list):
                        return False, f"Strict mode violation: {field} list length changed from {len(orig_list)} to {len(upd_list)}"
        
        return True, None

    def _run_schema_validation(
        self,
        section: str,
        updated: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Run schema validation on updated JSON.
        
        Returns:
            (is_valid, error_message)
        """
        is_valid, validation_error = validate_section_json(section, updated)
        if not is_valid:
            logger.error(f"Schema validation failed for section '{section}': {validation_error}")
        return is_valid, validation_error

    def _run_round_trip_validation(
        self,
        section: str,
        original_data: Dict[str, Any],
        updated: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Run round-trip validation: test if updated JSON can rebuild LaTeX.
        
        Uses backup/rollback pattern to ensure original data is always preserved.
        
        Returns:
            (is_valid, error_message)
        """
        try:
            from resume_builder.latex_builder import rebuild_resume_from_existing_json
            from resume_builder.paths import OUTPUT_DIR, GENERATED_DIR
        except ImportError:
            logger.warning("Round-trip validation skipped (rebuild helper not available)")
            return True, None  # Skip validation if helper not available
        
        original_path = self._resolve_section_path(section)
        temp_original_path = original_path.with_suffix(".original_backup")
        
        # Save backup and updated JSON
        try:
            temp_original_path.write_text(json.dumps(original_data, indent=2), encoding="utf-8")
            original_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to prepare round-trip validation for section '{section}': {e}")
            # Try to restore original
            try:
                if temp_original_path.exists():
                    temp_original_path.replace(original_path)
            except Exception:
                pass
            return True, None  # Don't fail on file I/O errors
        
        # Try rebuild
        try:
            test_tex_path = GENERATED_DIR / "rendered_resume_test.tex"
            rebuild_resume_from_existing_json(
                output_dir=OUTPUT_DIR,
                rendered_tex_path=test_tex_path
            )
            # Success - clean up
            test_tex_path.unlink(missing_ok=True)
            temp_original_path.unlink(missing_ok=True)
            logger.info(f"Round-trip validation passed for section '{section}'")
            return True, None
        except Exception as rebuild_error:
            # Rebuild failed - rollback to original
            try:
                original_path.write_text(json.dumps(original_data, indent=2), encoding="utf-8")
                temp_original_path.unlink(missing_ok=True)
            except Exception as rollback_error:
                logger.error(f"Failed to rollback after round-trip validation failure: {rollback_error}")
            logger.error(f"Round-trip validation failed for section '{section}': {rebuild_error}")
            return False, f"Round-trip validation failed: {str(rebuild_error)[:200]}"
        finally:
            # Ensure backup is cleaned up
            temp_original_path.unlink(missing_ok=True)

    def _compute_and_format_diff(
        self,
        original_data: Dict[str, Any],
        updated: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Compute diff and format for display.
        
        Returns:
            (diff_dict, formatted_diff_string or None)
        """
        diff = compute_json_diff(original_data, updated)
        diff_summary = diff.get("summary", "Changes detected")
        
        # Format diff for warnings (truncate if too long)
        formatted_diff = None
        if diff.get("summary") != "No changes detected":
            formatted_diff = format_diff_for_display(diff)
            # Truncate warnings to max 2000 chars
            if len(formatted_diff) > 2000:
                formatted_diff = formatted_diff[:2000] + "\n...(truncated)"
        
        return diff, formatted_diff

    def llm_edit_section(
        self,
        section: str,
        user_instruction: str,
        strict: bool = False,
        dry_run: bool = False,
    ) -> LLMJsonEditResult:
        """
        Use LLM to produce a new JSON object for a single section.
        
        Flow:
        1. Load original JSON
        2. Call LLM to generate updated JSON
        3. Check strict mode compliance (if strict=True)
        4. Run schema validation
        5. Run round-trip validation (skipped if dry_run=True)
        6. Save updated JSON (skipped if dry_run=True)
        7. Compute diff and return result
        
        Args:
            section: Section name (e.g., "summary", "experiences")
            user_instruction: Natural language instruction for the edit
            strict: If True, only allow text rewrites (no structural changes)
            dry_run: If True, preview only (no file writes, no round-trip validation)
        """
        
        # Load original JSON
        try:
            original_data = self._load_section_json(section)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load section '{section}': {e}")
            return {
                "status": "error",
                "section": section,
                "message": str(e),
                "warnings": [],
                "updated_json": None,
                "diff_meta": None,
            }
        
        # Store original for diff computation
        original_data_copy = json.loads(json.dumps(original_data))  # Deep copy
        
        # Store user_instruction for later use in validation
        self._current_user_instruction = user_instruction.lower()
        
        # Call LLM
        try:
            updated = self._call_llm_for_section(section, user_instruction, original_data, strict=strict)
        except ValueError as e:
            return {
                "status": "error",
                "section": section,
                "message": str(e),
                "warnings": [],
                "updated_json": None,
                "diff_meta": None,
            }
        
        # Check strict mode compliance
        if strict:
            is_compliant, compliance_error = self._check_strict_mode_compliance(original_data_copy, updated)
            if not is_compliant:
                logger.error(f"Strict mode violation for section '{section}': {compliance_error}")
                return {
                    "status": "error",
                    "section": section,
                    "message": f"Strict mode violation: {compliance_error}",
                    "warnings": [],
                    "updated_json": None,
                    "diff_meta": None,
                }
        
        # Basic safety: preserve certain invariants
        if section == "summary" and "status" in original_data:
            if "status" not in updated:
                updated["status"] = original_data["status"]
            if "message" not in updated:
                updated["message"] = original_data.get("message", "Summary updated")
        
        # For header section: preserve all fields that should not be modified
        if section == "header":
            # Preserve all contact fields if they exist in original
            for field in ["email", "phone", "location", "links", "target_title", "name"]:
                if field in original_data and field not in updated:
                    logger.warning(f"Header field '{field}' was removed by LLM, restoring from original")
                    updated[field] = original_data[field]
                elif field in original_data and field in updated:
                    # For links array, ensure structure is preserved
                    if field == "links" and isinstance(original_data[field], list):
                        if not isinstance(updated[field], list):
                            logger.warning(f"Header links field changed from list to {type(updated[field])}, restoring original")
                            updated[field] = original_data[field]
                        # For simple character removal (pipes), preserve array structure
                        elif len(updated[field]) != len(original_data[field]) and ("pipe" in getattr(self, '_current_user_instruction', '') or "|" in getattr(self, '_current_user_instruction', '')):
                            logger.warning(f"Header links array length changed during pipe removal, preserving original structure")
                            # Only remove pipes from link strings, don't change array structure
                            updated[field] = [
                                link.replace("|", "").strip() if isinstance(link, str) else link 
                                for link in original_data[field]
                            ]
                    # For string fields, if only removing pipes, ensure we don't lose other content
                    elif isinstance(original_data[field], str) and isinstance(updated[field], str):
                        # If the only change should be removing pipes, check if content was lost
                        original_no_pipes = original_data[field].replace("|", "").replace("||", "").replace("|||", "").strip()
                        current_instruction = getattr(self, '_current_user_instruction', '')
                        if original_no_pipes != updated[field].replace("|", "").replace("||", "").replace("|||", "").strip() and ("pipe" in current_instruction or "|" in current_instruction):
                            # LLM changed more than just removing pipes - log warning but allow (might be intentional)
                            logger.warning(f"Header field '{field}' had more changes than just pipe removal")

        # Schema validation (always runs, even in dry_run mode)
        is_valid, validation_error = self._run_schema_validation(section, updated)
        if not is_valid:
            return {
                "status": "error",
                "section": section,
                "message": f"Schema validation failed: {validation_error}",
                "warnings": [f"LLM output did not pass validation. Original data preserved."],
                "updated_json": None,
                "diff_meta": None,
            }

        # Round-trip validation (skipped in dry_run mode)
        if not dry_run:
            is_valid_roundtrip, roundtrip_error = self._run_round_trip_validation(section, original_data_copy, updated)
            if not is_valid_roundtrip:
                return {
                    "status": "error",
                    "section": section,
                    "message": f"Round-trip validation failed: JSON edit breaks LaTeX generation. Original data preserved.",
                    "warnings": [roundtrip_error] if roundtrip_error else [],
                    "updated_json": None,
                    "diff_meta": None,
                }
        else:
            logger.debug(f"Dry-run mode: skipping round-trip validation for section '{section}'")

        # Save updated JSON (skipped in dry_run mode)
        if not dry_run:
            try:
                self._save_section_json(section, updated)
            except Exception as e:
                logger.error(f"Failed to save updated JSON for section '{section}': {e}")
                return {
                    "status": "error",
                    "section": section,
                    "message": f"Failed to save updated JSON: {e}",
                    "warnings": [],
                    "updated_json": None,
                    "diff_meta": None,
                }
        else:
            logger.debug(f"Dry-run mode: skipping file save for section '{section}'")

        # Compute diff (always computed for preview/display)
        diff, formatted_diff = self._compute_and_format_diff(original_data_copy, updated)
        diff_summary = diff.get("summary", "Changes detected")
        diff_meta = summarize_diff_for_ui(diff)
        
        # Log success
        if dry_run:
            logger.info(f"LLM edit preview successful for section '{section}': {diff_summary} (dry-run, no changes saved)")
        else:
            logger.info(f"LLM edit successful for section '{section}': {diff_summary}")

        # Build message
        if dry_run:
            message = f"Preview for section '{section}': {diff_summary}. No changes saved."
        else:
            message = f"Section '{section}' JSON updated by LLM. {diff_summary}"

        return {
            "status": "ok",
            "section": section,
            "message": message,
            "updated_json": updated,
            "warnings": [formatted_diff] if formatted_diff else [],
            "diff_meta": diff_meta,
        }


def apply_llm_json_edit(
    section: str,
    user_instruction: str,
    base_dir: Optional[Path] = None,
    strict: bool = False,
    dry_run: bool = False,
) -> LLMJsonEditResult:
    """
    Top-level convenience function for LLM JSON editing.
    
    Args:
        section: Section name (e.g., "summary", "experiences", "skills")
        user_instruction: Natural language instruction for the edit
        base_dir: Optional base directory (defaults to OUTPUT_DIR)
        strict: If True, only allow text rewrites (no structural changes)
        dry_run: If True, preview only (no file writes, no round-trip validation)
        
    Returns:
        LLMJsonEditResult with status, message, and updated JSON
    """
    editor = LLMJsonSectionEditor(base_dir=base_dir)
    return editor.llm_edit_section(
        section=section,
        user_instruction=user_instruction,
        strict=strict,
        dry_run=dry_run
    )

