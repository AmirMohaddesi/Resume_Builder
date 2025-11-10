# Agent Roles

Detailed description of each AI agent in the system.

## Agent Overview

The system uses 11 specialized AI agents, each with a specific role in the resume generation process.

## Phase 1: Input Processing Agents

### Profile Validator

**Role**: Data validation specialist  
**Model**: gpt-4o-mini  
**Tools**: profile_reader

**Responsibilities**:
- Validates user profile structure
- Checks for required fields (name, email)
- Ensures data completeness
- Outputs validation status

**Output**: `output/validated_profile.json`

---

### File Collector

**Role**: Information merger  
**Model**: gpt-4o  
**Tools**: profile_reader, tex_info_extractor

**Responsibilities**:
- Extracts information from .tex files
- Merges .tex data with parsed resume data
- Fills missing contact information (links, email, phone)
- Prioritizes accurate data from .tex files

**Output**: `output/file_collection_report.json`

---

### Template Validator

**Role**: LaTeX expert  
**Model**: gpt-4o-mini  
**Tools**: latex_package_checker

**Responsibilities**:
- Checks custom templates for missing packages
- Validates LaTeX compatibility
- Provides installation recommendations
- Warns about potential compilation issues

**Output**: `output/template_validation.json`

---

### JD Analyst

**Role**: Job description parser  
**Model**: gpt-4o  
**Tools**: None

**Responsibilities**:
- Parses job descriptions
- Extracts job title, company, location
- Identifies required skills and keywords
- Creates cleaned, structured job description data

**Output**: `output/parsed_jd.json`

## Phase 2: Content Selection Agents

### Experience Selector

**Role**: Career strategist  
**Model**: gpt-4o  
**Tools**: profile_reader

**Responsibilities**:
- Selects 3-5 most relevant work experiences
- Matches experiences to job requirements
- Prioritizes experiences that demonstrate required skills
- Outputs structured JSON with organization, title, dates, descriptions

**Output**: `output/selected_experiences.json`

---

### Project Selector

**Role**: Project curator  
**Model**: gpt-4o  
**Tools**: profile_reader

**Responsibilities**:
- Selects 2-4 most relevant projects
- Focuses on technical skills alignment
- Prioritizes projects mentioned in job description
- Outputs project name, description, and URLs

**Output**: `output/selected_projects.json`

---

### Skill Selector

**Role**: Skill matching expert  
**Model**: gpt-4o-mini  
**Tools**: profile_reader

**Responsibilities**:
- Selects 8-12 most relevant skills
- Prioritizes skills explicitly mentioned in job description
- Balances technical and soft skills
- Outputs simple JSON array

**Output**: `output/selected_skills.json`

## Phase 3: Content Writing Agents

### Summary Writer

**Role**: Professional resume writer  
**Model**: gpt-4o  
**Tools**: profile_reader

**Responsibilities**:
- Writes 2-3 sentence professional summary
- Highlights relevant experience and skills
- Tailors to specific job requirements
- Uses plain text (no LaTeX formatting)

**Output**: `output/summary_block.json`

---

### Education Writer

**Role**: Education section specialist  
**Model**: gpt-4o-mini  
**Tools**: profile_reader

**Responsibilities**:
- Extracts all education entries
- Formats with degree, institution, dates, location
- Includes optional details (GPA, honors)
- Outputs structured JSON

**Output**: `output/education_block.json`

## Phase 4: Quality Assurance Agents

### ATS Checker

**Role**: ATS compatibility analyzer  
**Model**: gpt-4o  
**Tools**: profile_reader

**Responsibilities**:
- Analyzes keyword coverage
- Identifies missing keywords from job description
- Provides optimization recommendations
- Calculates coverage score

**Output**: `output/ats_report.json`

---

### Privacy Guard

**Role**: Privacy and security specialist  
**Model**: gpt-4o-mini  
**Tools**: privacy_guard_tool

**Responsibilities**:
- Scans content for sensitive information
- Detects SSN, passport numbers, private addresses
- Provides privacy risk warnings
- Ensures compliance

**Output**: `output/privacy_validation_report.json`

---

### Planner

**Role**: Strategic resume consultant  
**Model**: gpt-4o  
**Tools**: profile_reader

**Responsibilities**:
- Creates high-level tailoring plan
- Explains what was included and why
- Notes template usage and warnings
- Adapts strategy based on user inputs (template, reference PDFs)

**Output**: `output/tailor_plan.json`

## Agent Communication

Agents communicate through JSON files:

1. **Read Context**: Agents read JSON files from previous tasks
2. **Process**: Agents use LLM reasoning to complete their task
3. **Write Output**: Agents write results to JSON files
4. **Next Agent**: Subsequent agents use these outputs as context

## Model Selection Rationale

- **gpt-4o**: Used for complex reasoning tasks (selection, writing, analysis)
- **gpt-4o-mini**: Used for simpler tasks (validation, checking)

This balances cost and quality. You can change models in `config/agents.yaml`.

## Customizing Agents

To modify agent behavior:

1. Edit `src/resume_builder/config/agents.yaml`
2. Change `role`, `goal`, or `backstory` fields
3. Change `llm` field to use different models
4. Add or remove tools as needed

## Next Steps

- [System Architecture](ARCHITECTURE.md) - Overall system design
- [Data Flow](DATA_FLOW.md) - How agents exchange data
- [Configuration](CONFIGURATION.md) - Changing LLM models

---

**See Also**: [Usage](USAGE.md) | [Troubleshooting](TROUBLESHOOTING.md)

