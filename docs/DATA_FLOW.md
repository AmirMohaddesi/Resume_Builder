# Data Flow

How data moves through the AI Resume Builder system.

## Overview

The system uses a **file-based communication model** where agents read and write JSON files. This creates a clear, debuggable pipeline.

## Input Data

### User Provides

1. **Resume File** (PDF/DOCX/TXT)
   - Parsed by `agent_resume_parser.py`
   - Extracted to: `output/user_profile.json`

2. **Job Description** (Text)
   - Passed directly to JD Analyst agent

3. **Optional Files**
   - Custom template (.tex) → `output/custom_template.tex`
   - Reference PDFs → `output/reference_resume_*.pdf`

## Processing Pipeline

### Stage 1: Profile Extraction

```
Resume File → Agent Parser → user_profile.json
```

**File**: `output/user_profile.json`
```json
{
  "identity": { "first": "...", "last": "...", ... },
  "experience": [...],
  "skills": [...],
  ...
}
```

### Stage 2: Input Processing

```
user_profile.json → Profile Validator → validated_profile.json
custom_template.tex → File Collector → file_collection_report.json
custom_template.tex → Template Validator → template_validation.json
Job Description → JD Analyst → parsed_jd.json
```

**Key Files**:
- `validated_profile.json` - Validation status
- `file_collection_report.json` - Merged information from .tex
- `template_validation.json` - Package warnings
- `parsed_jd.json` - Structured job description

### Stage 3: Content Selection

```
user_profile.json + parsed_jd.json → Experience Selector → selected_experiences.json
user_profile.json + parsed_jd.json → Project Selector → selected_projects.json
user_profile.json + parsed_jd.json → Skill Selector → selected_skills.json
```

**Key Files**:
- `selected_experiences.json` - Filtered work experiences
- `selected_projects.json` - Selected projects
- `selected_skills.json` - Selected skills array

### Stage 4: Content Writing

```
selected_experiences.json + selected_skills.json + parsed_jd.json 
  → Summary Writer → summary_block.json

user_profile.json → Education Writer → education_block.json
```

**Key Files**:
- `summary_block.json` - Generated professional summary
- `education_block.json` - Formatted education entries

### Stage 5: Quality Assurance

```
selected_experiences.json + selected_skills.json + parsed_jd.json 
  → ATS Checker → ats_report.json

user_profile.json → Privacy Guard → privacy_validation_report.json

All JSON files → Planner → tailor_plan.json
```

**Key Files**:
- `ats_report.json` - Keyword coverage analysis
- `privacy_validation_report.json` - Privacy risk assessment
- `tailor_plan.json` - Strategic plan and reasoning

## LaTeX Generation

### Python-Based Generation

After all agents complete, Python code:

1. **Reads JSON files**:
   ```python
   user_profile.json → identity data
   summary_block.json → summary text
   selected_experiences.json → experience entries
   education_block.json → education entries
   selected_skills.json → skills list
   selected_projects.json → projects (optional)
   ```

2. **Generates LaTeX**:
   - Uses template (custom or default)
   - Replaces markers with content
   - Escapes special characters
   - Adds missing packages automatically

3. **Outputs**: `output/rendered_resume.tex`

## PDF Compilation

```
rendered_resume.tex → pdflatex → final_resume.pdf
```

**Process**:
1. LaTeX file compiled with `pdflatex`
2. Errors logged to `output/compile.log`
3. PDF generated: `output/final_resume.pdf`

## File Dependencies Graph

```
user_profile.json
    ├─→ validated_profile.json
    ├─→ file_collection_report.json (if .tex provided)
    ├─→ selected_experiences.json
    ├─→ selected_projects.json
    ├─→ selected_skills.json
    ├─→ education_block.json
    └─→ privacy_validation_report.json

parsed_jd.json
    ├─→ selected_experiences.json
    ├─→ selected_projects.json
    ├─→ selected_skills.json
    ├─→ summary_block.json
    └─→ ats_report.json

selected_experiences.json + selected_skills.json
    └─→ summary_block.json

All JSON files
    └─→ tailor_plan.json

All JSON files
    └─→ rendered_resume.tex
        └─→ final_resume.pdf
```

## Data Formats

### Profile Structure

```json
{
  "identity": {
    "first": "John",
    "last": "Doe",
    "email": "john@example.com",
    "website": "https://johndoe.com",
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "education": [...]
  },
  "experience": [...],
  "skills": [...],
  "projects": [...],
  "awards": [...]
}
```

### Selected Content Structure

```json
{
  "selected_experiences": [
    {
      "organization": "Company",
      "title": "Role",
      "dates": "2020-2023",
      "description": ["Achievement 1", "Achievement 2"]
    }
  ]
}
```

## Debugging Data Flow

To debug the pipeline:

1. **Check JSON files** in `output/` directory
2. **Verify file existence** before each agent runs
3. **Inspect JSON content** to see what agents produced
4. **Check logs** in `output/logs/` for agent reasoning

## Next Steps

- [System Architecture](ARCHITECTURE.md) - Overall design
- [Agent Roles](AGENTS.md) - What each agent does
- [Troubleshooting](TROUBLESHOOTING.md) - Common data flow issues

---

**See Also**: [Usage](USAGE.md) | [Configuration](CONFIGURATION.md)

