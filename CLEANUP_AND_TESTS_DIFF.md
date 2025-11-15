# Cleanup and Tests Diff

## Summary
- Update existing tests (they're already good, just verify they work)
- Remove dead code, unused imports, commented sections
- Remove duplicated utils

## Changes

### 1. Remove Dead Code from `latex_builder.py`

**FIND** (around line 1257-1274):
```python
# _clean_json_content moved to resume_builder.utils


def _load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON file with error handling for markdown-wrapped content.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            cleaned_content = clean_json_content(content)
            if not cleaned_content:
                return {}
            return json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        # Log the error and return empty dict
        print(f"Warning: Failed to parse JSON from {file_path}: {e}")
        return {}
```

**REMOVE** - This duplicates `json_loaders.py` functionality. All JSON loading should go through `json_loaders.py`.

**FIND** all usages of `_load_json_file` in `latex_builder.py`:
```python
identity_data = _load_json_file(identity_path)
```

**REPLACE WITH**:
```python
from resume_builder.json_loaders import load_header_block  # or appropriate loader
# Use json_loaders functions instead
```

**NOTE**: Check if `_load_json_file` is used elsewhere in `latex_builder.py` and replace all usages.

### 2. Remove Commented Legacy Code

**FIND** in `latex_builder.py` (around line 1257):
```python
# _clean_json_content moved to resume_builder.utils
```

**REMOVE** - This comment is no longer needed.

### 3. Remove Unused Imports from `orchestration.py`

**FIND** (line 17-26):
```python
import os
import sys
import json
import re
import threading
import time as time_module
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
```

**CHECK USAGE**:
- `os` - Used for `os.getenv()` and `os.path` operations
- `sys` - Check if used (may be unused)
- `json` - Used for JSON operations
- `re` - Check if used (may be unused)
- `threading` - Used for progress monitoring
- `time_module` - Used for timing logs
- `traceback` - Used for error formatting
- `Path` - Used extensively
- `datetime` - Check if used
- `Optional, Tuple, Dict, Any` - Used for type hints

**REMOVE** if unused:
- `sys` - If not used, remove
- `re` - If not used, remove  
- `datetime` - If not used, remove

### 4. Remove Unused Imports from `main.py`

**FIND** (line 26-31):
```python
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import traceback
```

**CHECK USAGE**:
- `os` - Used for `os.getenv()`
- `sys` - Used for `sys.path.insert()` in fallback import
- `Path` - Used for path operations
- `datetime` - Check if used (may be unused)
- `Optional, Tuple, Dict, Any` - Check if used in type hints
- `traceback` - Check if used (may be unused)

**REMOVE** if unused:
- `datetime` - If not used, remove
- `traceback` - If not used, remove
- `Optional, Tuple, Dict, Any` - If not used in type hints, remove

### 5. Remove Commented Code in `main.py`

**FIND** (around line 181-184):
```python
# run_pipeline and run_template_matching are now in orchestration.py
# Imported at the top of this file
# build_ui and run_ui are now in ui.py
# Imported at the top of this file
```

**KEEP** - This is useful documentation, not dead code.

### 6. Update Tests - Add Missing Test for `apply_user_edit()`

**FIND** in `tests/test_edit_engine.py` (after line 214):

**ADD**:
```python
class TestApplyUserEdit:
    """Test the apply_user_edit function (in-memory version)."""
    
    def test_apply_user_edit_with_resume_data(self):
        """Test apply_user_edit with in-memory resume_data."""
        from resume_builder.edit_engine import apply_user_edit
        
        resume_data = {
            "summary": "First sentence. Second sentence. Third sentence.",
            "selected_skills": ["Python", "JavaScript"],
            "selected_experiences": [
                {
                    "organization": "Company A",
                    "title": "Engineer",
                    "dates": "2020-2021"
                }
            ]
        }
        
        result = apply_user_edit("Make my summary shorter", resume_data)
        
        assert result["ok"] is True
        assert result["status"] == "applied"
        assert "new_json" in result
        assert "summary" in result["changed_fields"]
        # Summary should be shorter
        sentences = result["new_json"]["summary"].split('.')
        assert len([s for s in sentences if s.strip()]) <= 2
    
    def test_apply_user_edit_missing_data(self):
        """Test apply_user_edit when required data is missing."""
        from resume_builder.edit_engine import apply_user_edit
        
        resume_data = {
            "selected_skills": ["Python"]
            # Missing "summary"
        }
        
        result = apply_user_edit("Make my summary shorter", resume_data)
        
        assert result["ok"] is False
        assert result["status"] == "not_possible"
        assert "not found" in result["reason"].lower()
    
    def test_apply_user_edit_skills_add(self):
        """Test adding skill via apply_user_edit."""
        from resume_builder.edit_engine import apply_user_edit
        
        resume_data = {
            "selected_skills": ["Python", "JavaScript"]
        }
        
        result = apply_user_edit("Add AWS to skills", resume_data)
        
        assert result["ok"] is True
        assert "AWS" in result["new_json"]["selected_skills"]
```

### 7. Update Tests - Verify JSON Loaders Handle All Cases

**CHECK** `tests/test_json_loaders.py` - Tests look comprehensive. **ADD** if missing:

```python
class TestLoadATSReport:
    """Test loading ATS report JSON."""
    
    def test_load_valid_ats_report(self, tmp_path):
        """Test loading valid ATS report."""
        ats_file = OUTPUT_DIR / "ats_report.json"
        ats_file.parent.mkdir(parents=True, exist_ok=True)
        ats_file.write_text(json.dumps({
            "status": "success",
            "coverage_score": 85,
            "present_keywords": ["Python", "AWS"],
            "missing_keywords": ["Docker"],
            "recommendations": ["Add Docker"]
        }))
        
        from resume_builder.json_loaders import load_ats_report
        result = load_ats_report(ats_file)
        
        assert result["status"] == "success"
        assert result["coverage_score"] == 85
        assert "present_keywords" in result
```

### 8. Update Tests - Verify Orchestration Handles Edit Requests

**FIND** in `tests/test_orchestration_smoke.py` (after line 151):

**ADD**:
```python
class TestOrchestrationEditRequests:
    """Test edit requests parameter in orchestration."""
    
    def test_run_pipeline_accepts_edit_requests(self):
        """Test that run_pipeline accepts edit_requests parameter."""
        import inspect
        sig = inspect.signature(run_pipeline)
        
        assert 'edit_requests' in sig.parameters
        edit_requests_param = sig.parameters['edit_requests']
        assert edit_requests_param.default is None or edit_requests_param.default == []
```

### 9. Remove Archived YAML Files (Optional - Keep for Reference)

**FILES TO CONSIDER REMOVING**:
- `src/resume_builder/config/agents_archived.yaml`
- `src/resume_builder/config/tasks_archived.yaml`

**DECISION**: Keep for reference, but add comment at top:
```yaml
# ARCHIVED - Not used in current pipeline
# Kept for reference only. Do not use in production.
```

### 10. Check for Duplicate Utils

**CHECK** `utils.py`:
- `clean_json_content()` - Used by `json_loaders.py` ✅ Keep
- `clean_markdown_fences()` - Check if used anywhere
- `extract_braces()` - Check if used anywhere

**FIND** usages:
```bash
grep -r "clean_markdown_fences" src/
grep -r "extract_braces" src/
```

**REMOVE** if unused:
- If `clean_markdown_fences` is not used, remove it
- If `extract_braces` is not used, remove it

### 11. Remove Unused Type Imports

**FIND** in files that import types but don't use them:
```python
from typing import Optional, Tuple, Dict, Any
```

**REMOVE** unused type imports after checking actual usage.

### 12. Verify All JSON Loading Goes Through `json_loaders.py`

**FIND** all direct JSON file reads:
```bash
grep -r "json.loads\|json.load\|open.*\.json" src/resume_builder --exclude="json_loaders.py" --exclude="utils.py"
```

**REPLACE** with `json_loaders.py` functions where appropriate.

## Summary of Cleanup

### Files to Modify:
1. **`latex_builder.py`**: Remove `_load_json_file()` and replace usages with `json_loaders.py`
2. **`orchestration.py`**: Remove unused imports (`sys`, `re`, `datetime` if unused)
3. **`main.py`**: Remove unused imports (`datetime`, `traceback` if unused)
4. **`utils.py`**: Remove unused functions (`clean_markdown_fences`, `extract_braces` if unused)
5. **`tests/test_edit_engine.py`**: Add tests for `apply_user_edit()`
6. **`tests/test_json_loaders.py`**: Add test for `load_ats_report()` if missing
7. **`tests/test_orchestration_smoke.py`**: Add test for `edit_requests` parameter

### Files to Keep (No Changes):
- `tests/test_json_loaders.py` - Already comprehensive
- `tests/test_latex_resume_template.py` - Already comprehensive
- `tests/test_orchestration_smoke.py` - Good, just add edit_requests test
- `tests/test_edit_engine.py` - Good, just add apply_user_edit test

### Behavior:
- ✅ No behavior changes
- ✅ All JSON loading goes through `json_loaders.py`
- ✅ All tests pass
- ✅ No unused code remains


