# System Architecture

High-level overview of how the AI Resume Builder works.

## System Overview

The AI Resume Builder uses a **multi-agent AI system** (CrewAI) where specialized AI agents work together to create tailored resumes. The system follows a pipeline architecture with clear separation between AI reasoning and LaTeX generation.

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT                                │
│  • Resume File (PDF/DOCX/TXT)                               │
│  • Job Description                                           │
│  • Optional: Custom Template (.tex)                         │
│  • Optional: Reference PDFs                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 1: INPUT PROCESSING                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Profile Validator Agent                               │  │
│  │ • Validates profile structure                         │  │
│  │ • Checks required fields                              │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ File Collector Agent                                  │  │
│  │ • Extracts info from .tex files                       │  │
│  │ • Merges with parsed resume data                      │  │
│  │ • Fills missing contact information                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Template Validator Agent                              │  │
│  │ • Checks custom templates for missing packages         │  │
│  │ • Validates LaTeX compatibility                       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ JD Analyst Agent                                      │  │
│  │ • Parses job description                              │  │
│  │ • Extracts keywords and requirements                  │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 2: CONTENT SELECTION                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Experience Selector Agent                             │  │
│  │ • Selects 3-5 most relevant work experiences           │  │
│  │ • Matches experiences to job requirements             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Project Selector Agent                                │  │
│  │ • Selects 2-4 most relevant projects                   │  │
│  │ • Prioritizes technical skills                        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Skill Selector Agent                                 │  │
│  │ • Selects 8-12 most relevant skills                   │  │
│  │ • Prioritizes skills mentioned in job description    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 3: CONTENT WRITING                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Summary Writer Agent                                  │  │
│  │ • Writes 2-3 sentence professional summary            │  │
│  │ • Highlights relevant experience and skills            │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Education Writer Agent                               │  │
│  │ • Extracts all education entries                     │  │
│  │ • Formats with dates and details                     │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│       PHASE 4: QUALITY ASSURANCE & PLANNING                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ ATS Checker Agent                                     │  │
│  │ • Analyzes keyword coverage                          │  │
│  │ • Identifies missing keywords                         │  │
│  │ • Provides optimization recommendations                │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Privacy Guard Agent                                  │  │
│  │ • Scans for sensitive information                    │  │
│  │ • Warns about privacy risks                           │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Planner Agent                                        │  │
│  │ • Creates strategic tailoring plan                    │  │
│  │ • Explains selection reasoning                       │  │
│  │ • Reports template warnings                          │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         PYTHON-BASED LATEX GENERATION                        │
│  • Reads JSON outputs from agents                           │
│  • Generates LaTeX using template                           │
│  • Automatically adds missing packages                      │
│  • Fixes font expansion issues                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PDF COMPILATION                                │
│  • Compiles LaTeX to PDF                                    │
│  • Handles compilation errors                               │
│  • Returns final resume PDF                                 │
└──────────────────────────────────────────────────────────────┘
```

## Agent Communication

Agents communicate through **JSON files** in the `output/` directory:

1. Each agent writes its output to a JSON file
2. Subsequent agents read these files as context
3. This creates a clear data flow and allows for debugging

### Data Flow Example

```
profile_validation_task → output/validated_profile.json
         ↓
select_experiences_task reads validated_profile.json
         ↓
select_experiences_task → output/selected_experiences.json
         ↓
write_summary_task reads selected_experiences.json
         ↓
write_summary_task → output/summary_block.json
```

## Key Design Principles

### 1. Separation of Concerns

- **AI Agents**: Handle reasoning, selection, and writing
- **Python Code**: Handles LaTeX generation and file operations
- **Clear Boundaries**: Agents output JSON, Python generates LaTeX

### 2. Modularity

- Each agent has a specific role
- Agents can be swapped or modified independently
- Tools are reusable across agents

### 3. Extensibility

- Easy to add new agents
- Easy to add new tools
- Template system allows customization

## Tools Available to Agents

Agents have access to specialized tools:

- **profile_reader**: Read and parse user profile JSON
- **tex_info_extractor**: Extract information from .tex files
- **latex_package_checker**: Validate LaTeX packages
- **privacy_guard_tool**: Check for sensitive information

## Execution Model

### Sequential Processing

The crew uses `Process.sequential`, meaning:
- Tasks execute one after another
- Each task can depend on previous tasks
- Clear execution order

### Error Handling

- **Agent Errors**: Logged and reported to user
- **LaTeX Errors**: Automatically detected and fixed where possible
- **Missing Packages**: Warnings shown, compilation continues if possible

## Output Structure

All outputs are organized in `output/`:

```
output/
├── user_profile.json          # Extracted profile data
├── validated_profile.json      # Validation results
├── parsed_jd.json             # Parsed job description
├── selected_experiences.json  # Selected work experiences
├── selected_projects.json     # Selected projects
├── selected_skills.json       # Selected skills
├── summary_block.json         # Generated summary
├── education_block.json       # Education entries
├── ats_report.json           # ATS analysis
├── tailor_plan.json          # Strategic plan
├── rendered_resume.tex       # Generated LaTeX
└── final_resume.pdf          # Final PDF output
```

## Configuration Files

- **agents.yaml**: Defines agent roles, goals, and LLM models
- **tasks.yaml**: Defines task descriptions and dependencies
- **crew.py**: Registers tools and assembles the crew

## Next Steps

- [Agent Roles](AGENTS.md) - Detailed agent descriptions
- [Data Flow](DATA_FLOW.md) - How data moves through the system
- [Configuration](CONFIGURATION.md) - Customizing the system

---

**See Also**: [Installation](INSTALLATION.md) | [Usage](USAGE.md)

