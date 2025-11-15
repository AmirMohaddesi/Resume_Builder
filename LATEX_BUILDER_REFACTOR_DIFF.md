# LaTeX Builder Refactoring Diff

## Summary
Refactor `latex_builder.py` into a proper module structure while maintaining EXACT behavior.

## Current State
- `latex/core.py` - Already has: `escape_latex`, `format_phone`, `format_url`, `strip_latex_comments`, `has_pkg`
- `latex/resume_template.py` - Already has: `build_preamble`, `build_header`, `build_summary`, `build_experience_entry`, `build_experience_section`, `build_education_entry`, `build_education_section`, `build_skills_section`, `build_projects_section`
- `latex_builder.py` - Still contains: `LaTeXBuilder` class, `build_complete_resume`, `build_resume_from_json_files`, `repair_latex_file`, internal helpers
- Cover letter generation is in `orchestration.py` as `_generate_cover_letter_pdf`

## Target Structure

```
src/resume_builder/latex/
    __init__.py          # Exports all public functions
    core.py              # ✅ Already done (escaping, formatting, helpers)
    resume_template.py   # ✅ Partially done (needs build_complete_resume, build_resume_from_json_files)
    cover_letter_template.py  # NEW (move from orchestration.py)
    validation.py        # NEW (repair_latex_file and safety checks)
```

## Changes Required

### 1. Create `latex/cover_letter_template.py` (NEW)

**Source**: Extract from `orchestration.py` lines 71-205

**Content**:
```python
"""
LaTeX template generation for cover letters.

This module contains functions to generate LaTeX code for cover letters
from JSON data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional

from resume_builder.latex.core import escape_latex
from resume_builder.paths import TEMPLATES, GENERATED_DIR

COVER_LETTER_TEX = GENERATED_DIR / "cover_letter.tex"


def build_cover_letter_latex(
    cover_letter_md: str,
    identity: Dict[str, Any],
    template_path: Optional[Path] = None
) -> str:
    """
    Build LaTeX content for cover letter from markdown and identity.
    
    Args:
        cover_letter_md: Cover letter content in markdown format
        identity: Identity dictionary with first, last, email, phone, website
        template_path: Optional path to custom template (defaults to TEMPLATES/cover_letter.tex)
    
    Returns:
        Complete LaTeX document as string
    """
    # Load template
    if template_path and template_path.exists():
        template = template_path.read_text(encoding='utf-8')
    else:
        template_path = TEMPLATES / "cover_letter.tex"
        if not template_path.exists():
            raise FileNotFoundError(f"Cover letter template not found: {template_path}")
        template = template_path.read_text(encoding='utf-8')
    
    # Extract contact info
    first_name = identity.get('first', '')
    last_name = identity.get('last', '')
    email = identity.get('email', '')
    phone = identity.get('phone', '')
    website = identity.get('website', '')
    
    # Build header
    name = f"{first_name} {last_name}".strip()
    contact_lines = []
    if email:
        contact_lines.append(email)
    if phone:
        contact_lines.append(phone)
    if website:
        contact_lines.append(website)
    
    # Build header LaTeX with name bold and contact info below
    header_parts = []
    if name:
        header_parts.append(f'\\textbf{{{escape_latex(name)}}}')
    for contact in contact_lines:
        header_parts.append(escape_latex(contact))
    header = '\\\\\n        '.join(header_parts) if header_parts else ''
    
    # Parse cover letter markdown to extract recipient and body
    lines = cover_letter_md.split('\n')
    recipient = ""
    greeting = "Dear Hiring Manager,"
    body_lines = []
    closing = "Sincerely,\n[Your Name]"
    
    # Simple parsing: look for "Dear" line, then body, then closing
    in_body = False
    greeting_found = False
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            if in_body:
                body_lines.append('')
            continue
        
        if not greeting_found and line.lower().startswith('dear'):
            greeting = line
            greeting_found = True
            in_body = True
        elif in_body and (line.lower().startswith('sincerely') or line.lower().startswith('best regards') or line.lower().startswith('regards')):
            closing = '\n'.join(lines[i:])
            break
        elif in_body:
            body_lines.append(line)
    
    # If no greeting found, use entire content as body
    if not greeting_found:
        body = cover_letter_md
    else:
        body = '\n\n'.join(body_lines) if body_lines else cover_letter_md
    
    # Escape LaTeX
    recipient_escaped = escape_latex(recipient) if recipient else ''
    greeting_escaped = escape_latex(greeting) if greeting else 'Dear Hiring Manager,'
    body_escaped = escape_latex(body, keep_commands=True)  # Allow some formatting
    closing_escaped = escape_latex(closing) if closing else 'Sincerely,\n[Your Name]'
    
    # Replace name placeholder
    if '[Your Name]' in closing_escaped:
        closing_escaped = closing_escaped.replace('[Your Name]', name if name else '[Your Name]')
    
    # Replace template markers
    if header:
        header_latex = f'\\begin{{flushright}}\n        {header}\n    \\end{{flushright}}\n    \\vspace{{0.5cm}}'
    else:
        header_latex = ''
    latex_content = template.replace('% === AUTO:HEADER ===', header_latex)
    latex_content = latex_content.replace('% === AUTO:RECIPIENT ===', recipient_escaped)
    latex_content = latex_content.replace('% === AUTO:GREETING ===', greeting_escaped)
    latex_content = latex_content.replace('% === AUTO:BODY ===', body_escaped)
    latex_content = latex_content.replace('% === AUTO:CLOSING ===', closing_escaped)
    
    return latex_content
```

### 2. Create `latex/validation.py` (NEW)

**Source**: Extract from `latex_builder.py` lines 1362-2463 (`repair_latex_file` function)

**Content**: Move entire `repair_latex_file` function and any validation helpers.

**Note**: This is a large function (~1000 lines). Keep it as-is, just move it.

### 3. Update `latex/resume_template.py`

**Add**:
- `build_complete_resume()` - Move from `LaTeXBuilder.build_complete_resume` (lines 568-734)
- `build_resume_from_json_files()` - Move from standalone function (lines 1277-1359)
- Internal helpers: `_ensure_required_packages`, `_post_process_latex`, `_add_intelligent_page_breaks`, `_get_default_template`

**Convert**: Change from class methods to standalone functions, using imports from `core.py`

### 4. Update `latex/__init__.py`

**Add exports**:
```python
from .core import (
    escape_latex,
    format_phone,
    format_url,
    strip_latex_comments,
    has_pkg,
)

from .resume_template import (
    build_preamble,
    build_header,
    build_summary,
    build_experience_entry,
    build_experience_section,
    build_education_entry,
    build_education_section,
    build_skills_section,
    build_projects_section,
    build_complete_resume,
    build_resume_from_json_files,
)

from .cover_letter_template import (
    build_cover_letter_latex,
)

from .validation import (
    repair_latex_file,
)

__all__ = [
    # Core helpers
    'escape_latex',
    'format_phone',
    'format_url',
    'strip_latex_comments',
    'has_pkg',
    # Resume generation
    'build_preamble',
    'build_header',
    'build_summary',
    'build_experience_entry',
    'build_experience_section',
    'build_education_entry',
    'build_education_section',
    'build_skills_section',
    'build_projects_section',
    'build_complete_resume',
    'build_resume_from_json_files',
    # Cover letter generation
    'build_cover_letter_latex',
    # Validation/repair
    'repair_latex_file',
]
```

### 5. Update `orchestration.py`

**CHANGE** (line 75):
```python
# BEFORE:
from resume_builder.latex_builder import LaTeXBuilder

# AFTER:
from resume_builder.latex.cover_letter_template import build_cover_letter_latex
from resume_builder.latex.core import escape_latex
```

**CHANGE** (lines 104-183):
```python
# BEFORE:
builder = LaTeXBuilder()
# ... uses builder.escape_latex() ...

# AFTER:
# Use build_cover_letter_latex function directly
latex_content = build_cover_letter_latex(
    cover_letter_md=cover_letter_md,
    identity=identity,
    template_path=template_path
)
```

**CHANGE** (line 975):
```python
# BEFORE:
from resume_builder.latex_builder import build_resume_from_json_files

# AFTER:
from resume_builder.latex.resume_template import build_resume_from_json_files
```

**CHANGE** (line 1175):
```python
# BEFORE:
from resume_builder.latex_builder import repair_latex_file

# AFTER:
from resume_builder.latex.validation import repair_latex_file
```

### 6. Deprecate `latex_builder.py`

**Option A**: Keep as compatibility shim (recommended for gradual migration)
```python
"""
DEPRECATED: This module is kept for backward compatibility.
Please use the new latex package modules instead:
- latex.core for escaping/formatting
- latex.resume_template for resume generation
- latex.cover_letter_template for cover letter generation
- latex.validation for repair/validation
"""

from resume_builder.latex import (
    escape_latex,
    format_phone,
    format_url,
    build_preamble,
    build_header,
    build_summary,
    build_experience_section,
    build_education_section,
    build_skills_section,
    build_projects_section,
    build_complete_resume,
    build_resume_from_json_files,
    build_cover_letter_latex,
    repair_latex_file,
)

# Keep LaTeXBuilder class for backward compatibility
class LaTeXBuilder:
    """DEPRECATED: Use functions from latex package instead."""
    
    @staticmethod
    def escape_latex(text: str, *, keep_commands: bool = False) -> str:
        return escape_latex(text, keep_commands=keep_commands)
    
    @staticmethod
    def format_phone(phone: str) -> str:
        return format_phone(phone)
    
    @staticmethod
    def format_url(url: str) -> str:
        return format_url(url)
    
    def build_preamble(self, identity):
        return build_preamble(identity)
    
    def build_header(self, title_line, contact_info):
        return build_header(title_line, contact_info)
    
    # ... etc for all methods ...
```

**Option B**: Remove entirely (requires updating all imports first)

## File Size Estimates

- `latex/core.py`: ~120 lines (already done)
- `latex/resume_template.py`: ~800 lines (add ~600 lines from latex_builder.py)
- `latex/cover_letter_template.py`: ~150 lines (new)
- `latex/validation.py`: ~1100 lines (new, from repair_latex_file)
- `latex/__init__.py`: ~80 lines (updated)
- `latex_builder.py`: ~200 lines (compatibility shim) or 0 (removed)

## Import Updates Required

Files that import from `latex_builder`:
1. `orchestration.py` - 3 imports (update all)
2. Any other files (check with grep)

## Testing Checklist

- [ ] All imports resolve correctly
- [ ] Resume generation works identically
- [ ] Cover letter generation works identically
- [ ] LaTeX repair works identically
- [ ] No behavior changes
- [ ] All functions accessible via `latex` package
- [ ] Backward compatibility maintained (if keeping shim)

## Notes

- Keep EXACT behavior - no logic changes
- Use `json_loaders` for all JSON access (already done in `build_resume_from_json_files`)
- All functions should be standalone (no class wrapper needed)
- Maintain schema usage via `json_loaders` as specified

