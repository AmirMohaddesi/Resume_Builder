# Edit Request Engine Integration Diff

## Summary
Add `apply_user_edit()` function and integrate edit requests into `orchestration.py` and `ui.py`.

## Current State
- `edit_engine.py` exists with `apply_edit_request(request: str)` that loads from files
- Need to add `apply_user_edit(request: str, resume_data: dict)` that works with in-memory data
- Need integration in `orchestration.py` before LaTeX generation
- Need UI integration in `ui.py` with textbox

## Changes Required

### 1. Update `edit_engine.py` - Add `apply_user_edit()` Function

**ADD AFTER** `apply_edit_request()` function (after line 565):

```python
def apply_user_edit(request: str, resume_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply user edit request to in-memory resume data.
    
    This function works with resume data directly (no file I/O) and is designed
    for integration into the pipeline before LaTeX generation.
    
    Args:
        request: Natural language edit request (e.g., "Make my summary shorter", "Add AWS to skills")
        resume_data: Dictionary containing resume data blocks. Expected keys:
            - "summary": str (from summary_block.json)
            - "selected_experiences": List[Dict] (from selected_experiences.json)
            - "selected_skills": List[str] (from selected_skills.json)
            - "selected_projects": List[Dict] (from selected_projects.json, optional)
            - "education": List[Dict] (from education_block.json, optional)
            - "header": Dict with "title_line" and "contact_info" (from header_block.json, optional)
            - "cover_letter": Dict with "cover_letter_md" (from cover_letter.json, optional)
    
    Returns:
        Dictionary with:
        - ok: bool - Whether edit was applied
        - status: str - "applied" or "not_possible"
        - new_json: Dict - Updated resume_data (if applied)
        - changed_fields: List[str] - Fields that were modified
        - reason: str - Explanation if not possible
    """
    engine = EditEngine()
    
    # Detect edit type
    edit_type = engine.detect_edit_type(request)
    
    # Check if possible (simplified check - no file existence check needed)
    if edit_type == EditType.UNKNOWN:
        return {
            "ok": False,
            "status": "not_possible",
            "reason": "Could not determine what section to edit. Please be more specific (e.g., 'summary', 'skills', 'experiences').",
            "new_json": None,
            "changed_fields": []
        }
    
    # Check for impossible operations
    request_lower = request.lower()
    if any(word in request_lower for word in ["change template", "modify template", "alter template structure"]):
        return {
            "ok": False,
            "status": "not_possible",
            "reason": "Template structure changes are not supported. Use template matching feature instead.",
            "new_json": None,
            "changed_fields": []
        }
    
    if any(word in request_lower for word in ["latex", "tex", "\\", "command", "macro"]):
        return {
            "ok": False,
            "status": "not_possible",
            "reason": "LaTeX-specific edits are not supported. Use the LaTeX adjustment feature in the UI instead.",
            "new_json": None,
            "changed_fields": []
        }
    
    # Map edit type to resume_data keys
    data_key_map = {
        EditType.SUMMARY: "summary",
        EditType.EXPERIENCES: "selected_experiences",
        EditType.SKILLS: "selected_skills",
        EditType.PROJECTS: "selected_projects",
        EditType.EDUCATION: "education",
        EditType.HEADER: "header",
        EditType.COVER_LETTER: "cover_letter",
    }
    
    data_key = data_key_map.get(edit_type)
    if not data_key or data_key not in resume_data:
        return {
            "ok": False,
            "status": "not_possible",
            "reason": f"Required data block '{data_key}' not found in resume_data. Please generate the resume first.",
            "new_json": None,
            "changed_fields": []
        }
    
    try:
        # Prepare current_data in the format expected by EditEngine
        current_data = resume_data[data_key]
        
        # Wrap in expected schema format for EditEngine methods
        if edit_type == EditType.SUMMARY:
            current_data_wrapped = {"summary": current_data, "status": "success", "message": ""}
        elif edit_type == EditType.EXPERIENCES:
            current_data_wrapped = {"selected_experiences": current_data, "status": "success", "message": ""}
        elif edit_type == EditType.SKILLS:
            current_data_wrapped = {"selected_skills": current_data, "status": "success", "message": ""}
        elif edit_type == EditType.PROJECTS:
            current_data_wrapped = {"selected_projects": current_data, "status": "success", "message": ""}
        elif edit_type == EditType.EDUCATION:
            current_data_wrapped = {"education": current_data, "status": "success", "message": ""}
        elif edit_type == EditType.HEADER:
            current_data_wrapped = current_data if isinstance(current_data, dict) else {"title_line": "", "contact_info": {}}
        elif edit_type == EditType.COVER_LETTER:
            current_data_wrapped = current_data if isinstance(current_data, dict) else {"cover_letter_md": "", "status": "success", "message": ""}
        else:
            return {
                "ok": False,
                "status": "not_possible",
                "reason": f"Unsupported edit type: {edit_type}",
                "new_json": None,
                "changed_fields": []
            }
        
        # Apply edit
        new_data_wrapped = engine.apply_edit(edit_type, request, current_data_wrapped)
        
        # Extract the updated block from wrapped format
        if edit_type == EditType.SUMMARY:
            updated_block = new_data_wrapped.get("summary", current_data)
        elif edit_type == EditType.EXPERIENCES:
            updated_block = new_data_wrapped.get("selected_experiences", current_data)
        elif edit_type == EditType.SKILLS:
            updated_block = new_data_wrapped.get("selected_skills", current_data)
        elif edit_type == EditType.PROJECTS:
            updated_block = new_data_wrapped.get("selected_projects", current_data)
        elif edit_type == EditType.EDUCATION:
            updated_block = new_data_wrapped.get("education", current_data)
        elif edit_type == EditType.HEADER:
            updated_block = new_data_wrapped
        elif edit_type == EditType.COVER_LETTER:
            updated_block = new_data_wrapped
        else:
            updated_block = current_data
        
        # Create updated resume_data
        new_resume_data = resume_data.copy()
        new_resume_data[data_key] = updated_block
        
        # Determine changed fields
        changed_fields = [data_key] if updated_block != current_data else []
        
        return {
            "ok": True,
            "status": "applied",
            "new_json": new_resume_data,
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
```

### 2. Update `orchestration.py` - Integrate Edit Requests Before LaTeX Generation

**FIND** (around line 960, before LaTeX generation):
```python
    # All orchestration logic is now in the orchestrator agent
    # Python only checks pipeline_status.json and proceeds with LaTeX generation
    
    # Step 2: Generate LaTeX using Python builder (no agents involved)
```

**ADD BEFORE** LaTeX generation (after line 962, before line 967):
```python
    # ============================================
    # STEP 1.5: Apply user edit requests if any
    # ============================================
    
    # Check for edit requests in inputs or environment
    edit_requests = inputs.get("edit_requests", [])
    if not edit_requests and os.getenv("RESUME_EDIT_REQUESTS"):
        # Try to parse from environment variable (JSON array of strings)
        try:
            import json
            edit_requests = json.loads(os.getenv("RESUME_EDIT_REQUESTS"))
        except Exception:
            edit_requests = []
    
    if edit_requests:
        logger.info("="*80)
        logger.info("Applying user edit requests...")
        logger.info("="*80)
        
        try:
            from resume_builder.edit_engine import apply_user_edit
            from resume_builder.json_loaders import (
                load_summary_block,
                load_selected_experiences,
                load_selected_skills,
                load_selected_projects,
                load_education_block,
                load_header_block,
            )
            
            # Load current resume data from JSON files
            resume_data = {}
            
            # Load required blocks
            summary_data = load_summary_block(OUTPUT_DIR / "summary_block.json")
            if summary_data.get("status") == "success":
                resume_data["summary"] = summary_data.get("summary", "")
            
            exp_data = load_selected_experiences(OUTPUT_DIR / "selected_experiences.json")
            if exp_data.get("status") == "success":
                resume_data["selected_experiences"] = exp_data.get("selected_experiences", [])
            
            skills_data = load_selected_skills(OUTPUT_DIR / "selected_skills.json")
            if skills_data.get("status") == "success":
                resume_data["selected_skills"] = skills_data.get("selected_skills", [])
            
            # Load optional blocks
            projects_data = load_selected_projects(OUTPUT_DIR / "selected_projects.json")
            if projects_data.get("status") == "success":
                resume_data["selected_projects"] = projects_data.get("selected_projects", [])
            
            edu_data = load_education_block(OUTPUT_DIR / "education_block.json")
            if edu_data.get("status") == "success":
                resume_data["education"] = edu_data.get("education", [])
            
            header_data = load_header_block(OUTPUT_DIR / "header_block.json")
            if header_data.get("status") == "success":
                resume_data["header"] = {
                    "title_line": header_data.get("title_line", ""),
                    "contact_info": header_data.get("contact_info", {})
                }
            
            # Apply each edit request sequentially
            for i, edit_request in enumerate(edit_requests, 1):
                if not edit_request or not edit_request.strip():
                    continue
                
                logger.info(f"[EDIT {i}/{len(edit_requests)}] Processing: {edit_request}")
                
                result = apply_user_edit(edit_request, resume_data)
                
                if result.get("ok"):
                    logger.info(f"✅ Edit applied successfully. Changed fields: {result.get('changed_fields', [])}")
                    # Update resume_data with the new version
                    resume_data = result.get("new_json", resume_data)
                    
                    # Write updated JSON back to files
                    changed_fields = result.get("changed_fields", [])
                    for field in changed_fields:
                        if field == "summary":
                            summary_file = OUTPUT_DIR / "summary_block.json"
                            summary_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Summary updated via edit request",
                                    "summary": resume_data["summary"]
                                }, indent=2),
                                encoding='utf-8'
                            )
                        elif field == "selected_experiences":
                            exp_file = OUTPUT_DIR / "selected_experiences.json"
                            exp_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Experiences updated via edit request",
                                    "selected_experiences": resume_data["selected_experiences"]
                                }, indent=2),
                                encoding='utf-8'
                            )
                        elif field == "selected_skills":
                            skills_file = OUTPUT_DIR / "selected_skills.json"
                            skills_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Skills updated via edit request",
                                    "selected_skills": resume_data["selected_skills"]
                                }, indent=2),
                                encoding='utf-8'
                            )
                        elif field == "selected_projects":
                            projects_file = OUTPUT_DIR / "selected_projects.json"
                            projects_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Projects updated via edit request",
                                    "selected_projects": resume_data["selected_projects"]
                                }, indent=2),
                                encoding='utf-8'
                            )
                        elif field == "education":
                            edu_file = OUTPUT_DIR / "education_block.json"
                            edu_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Education updated via edit request",
                                    "education": resume_data["education"]
                                }, indent=2),
                                encoding='utf-8'
                            )
                        elif field == "header":
                            header_file = OUTPUT_DIR / "header_block.json"
                            header_file.write_text(
                                json.dumps({
                                    "status": "success",
                                    "message": "Header updated via edit request",
                                    "title_line": resume_data["header"].get("title_line", ""),
                                    "contact_info": resume_data["header"].get("contact_info", {})
                                }, indent=2),
                                encoding='utf-8'
                            )
                else:
                    reason = result.get("reason", "Unknown error")
                    logger.warning(f"⚠️ Edit not applied: {reason}")
            
            logger.info("✅ All edit requests processed")
            
        except Exception as e:
            logger.error(f"Error processing edit requests: {e}", exc_info=True)
            logger.warning("Continuing with original resume data (edit requests ignored)")
    
    # Step 2: Generate LaTeX using Python builder (no agents involved)
```

### 3. Update `ui.py` - Add Edit Request Textbox

**FIND** the UI layout section (around line 200-300 where inputs are defined):

**ADD** a new textbox for edit requests. Look for where other inputs are defined (e.g., `jd`, `debug`, `fast_mode`):

```python
# Find where inputs are defined, add:
edit_requests_input = gr.Textbox(
    label="📝 Edit Requests (Optional)",
    placeholder="Example: 'Make my summary shorter' or 'Add AWS to skills' or 'Reorder experiences by date'",
    lines=3,
    info="Enter natural language edit requests, one per line. These will be applied before LaTeX generation.",
    visible=True
)
```

**FIND** the `handle_generate` function signature and update it:

**BEFORE**:
```python
async def handle_generate(jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy, progress=gr.Progress()):
```

**AFTER**:
```python
async def handle_generate(jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy, edit_requests, progress=gr.Progress()):
```

**FIND** where `run_pipeline` is called (around line 800-900):

**BEFORE**:
```python
pdf_path, msg, cover_letter_pdf_path = run_pipeline(
    jd_text=jd,
    profile_path=profile_path,
    custom_template_path=template_path,
    reference_pdf_paths=reference_pdfs,
    progress_callback=progress_callback,
    debug=debug,
    enable_ats=enable_ats,
    enable_privacy=enable_privacy,
    fast_mode=fast_mode
)
```

**AFTER**:
```python
# Parse edit requests (split by newlines, filter empty)
edit_requests_list = []
if edit_requests and edit_requests.strip():
    edit_requests_list = [req.strip() for req in edit_requests.split('\n') if req.strip()]

pdf_path, msg, cover_letter_pdf_path = run_pipeline(
    jd_text=jd,
    profile_path=profile_path,
    custom_template_path=template_path,
    reference_pdf_paths=reference_pdfs,
    progress_callback=progress_callback,
    debug=debug,
    enable_ats=enable_ats,
    enable_privacy=enable_privacy,
    fast_mode=fast_mode,
    edit_requests=edit_requests_list  # NEW PARAMETER
)
```

**FIND** the UI layout where inputs are assembled (look for `gr.Column` or `gr.Row` with inputs):

**ADD** `edit_requests_input` to the inputs list in the appropriate location.

**FIND** the `generate_btn.click` event handler:

**BEFORE**:
```python
generate_btn.click(
    fn=handle_generate,
    inputs=[jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy],
    outputs=[...]
)
```

**AFTER**:
```python
generate_btn.click(
    fn=handle_generate,
    inputs=[jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy, edit_requests_input],
    outputs=[...]
)
```

### 4. Update `orchestration.py` - Add `edit_requests` Parameter to `run_pipeline()`

**FIND** `run_pipeline()` function signature (line 208):

**BEFORE**:
```python
def run_pipeline(
    jd_text: str,
    profile_path: Optional[str],
    custom_template_path: Optional[str] = None,
    reference_pdf_paths: Optional[list] = None,
    progress_callback=None,
    debug: bool = False,
    enable_ats: bool = True,
    enable_privacy: bool = True,
    fast_mode: bool = True
) -> Tuple[Optional[str], str, Optional[str]]:
```

**AFTER**:
```python
def run_pipeline(
    jd_text: str,
    profile_path: Optional[str],
    custom_template_path: Optional[str] = None,
    reference_pdf_paths: Optional[list] = None,
    progress_callback=None,
    debug: bool = False,
    enable_ats: bool = True,
    enable_privacy: bool = True,
    fast_mode: bool = True,
    edit_requests: Optional[List[str]] = None  # NEW PARAMETER
) -> Tuple[Optional[str], str, Optional[str]]:
```

**FIND** where `inputs` dictionary is created (around line 348):

**ADD**:
```python
inputs = {
    "job_description": jd_text,
    "profile_path": str(profile_path),
    "template_path": str(template_path),
    "has_custom_template": custom_template_path is not None,
    "has_reference_pdfs": has_reference_pdfs,
    "reference_pdf_count": len(reference_pdf_paths) if has_reference_pdfs else 0,
    "debug": debug,
    "enable_ats": enable_ats,
    "enable_privacy": enable_privacy,
    "fast_mode": fast_mode,
    "edit_requests": edit_requests or [],  # NEW FIELD
}
```

## Summary of Changes

### Files Modified:
1. **`edit_engine.py`**: Add `apply_user_edit()` function (~150 lines)
2. **`orchestration.py`**: 
   - Add `edit_requests` parameter to `run_pipeline()` 
   - Add edit request processing before LaTeX generation (~100 lines)
3. **`ui.py`**: 
   - Add `edit_requests_input` textbox
   - Update `handle_generate()` signature
   - Parse and pass edit requests to `run_pipeline()` (~20 lines)

### Behavior:
- Edit requests are applied **before** LaTeX generation
- Uses `gpt-4o-mini` for LLM edits (cost-optimized)
- Preserves all JSON schemas
- Never adds/removes required fields
- Updates JSON files after each successful edit
- Continues with original data if edits fail

### Integration Points:
1. **UI**: User enters edit requests in textbox → passed to `run_pipeline()`
2. **Orchestration**: Edit requests applied after crew execution, before LaTeX generation
3. **Edit Engine**: Processes requests and updates in-memory data, then writes to files

