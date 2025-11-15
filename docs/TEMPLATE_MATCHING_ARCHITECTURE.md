# LaTeX Template Matching Architecture

## Problem Statement

Match a generated resume PDF to a reference PDF visually, fixing LaTeX templates while preserving data-driven design.

## Recommended Approach: **Hybrid (Low-Level + Crew)**

### Why Hybrid?

- **Low-level code**: Fast, precise, deterministic for structural analysis
- **Crew/LLM**: Semantic understanding, intelligent fixes, validation
- **Best of both**: Precision where needed, intelligence where helpful

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT LAYER                              │
│  - reference_resume.pdf (target visual)                     │
│  - generated_resume.pdf (current output)                    │
│  - LaTeX sources (templates/*.tex, .cls, .sty)             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              LOW-LEVEL ANALYSIS (Python)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. PDF Comparison Tool                                │  │
│  │    - Extract text from both PDFs (PyMuPDF)           │  │
│  │    - Compare section structure                        │  │
│  │    - Detect visual differences (layout, spacing)     │  │
│  │    - Generate structured diff report                 │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. LaTeX Structure Analyzer                         │  │
│  │    - Parse LaTeX AST (pylatex or regex)            │  │
│  │    - Map sections to PDF regions                    │  │
│  │    - Identify template markers                      │  │
│  │    - Extract command definitions                     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. Difference Report Generator                       │  │
│  │    - Structured JSON diff report                     │  │
│  │    - Section-by-section comparison                  │  │
│  │    - Formatting differences (spacing, fonts, etc.)  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              CREW-LEVEL FIX GENERATION                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Template Fixer Agent                                  │  │
│  │ Role: LaTeX Template Specialist                      │  │
│  │ Tools:                                               │  │
│  │   - read_latex_file                                  │  │
│  │   - write_latex_file                                 │  │
│  │   - pdf_comparison_tool (new)                        │  │
│  │   - latex_structure_analyzer (new)                   │  │
│  │                                                       │  │
│  │ Tasks:                                               │  │
│  │   1. Read diff report                                │  │
│  │   2. Analyze LaTeX structure                         │  │
│  │   3. Generate fixes (preserve data model)           │  │
│  │   4. Validate changes                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              ITERATIVE REFINEMENT                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Compile fixed LaTeX → new PDF                     │  │
│  │ 2. Compare new PDF vs reference                      │  │
│  │ 3. If differences remain → iterate                   │  │
│  │ 4. Stop when visual match achieved                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Low-Level Tools (Python)

#### 1.1 PDF Comparison Tool
**File**: `src/resume_builder/tools/pdf_comparison_tool.py`

```python
class PdfComparisonTool(BaseTool):
    """Compare two PDFs and generate structured diff report."""
    
    def _compare_pdfs(self, reference_pdf: str, generated_pdf: str) -> Dict:
        """
        Returns:
        {
            "sections": {
                "header": {
                    "reference_text": "...",
                    "generated_text": "...",
                    "differences": ["missing icon", "wrong spacing"],
                    "visual_diff_score": 0.85
                },
                "summary": {...},
                ...
            },
            "layout_issues": [
                {"type": "spacing", "section": "header", "issue": "too much gap"},
                {"type": "alignment", "section": "links", "issue": "misaligned"}
            ],
            "formatting_differences": {
                "fonts": {...},
                "spacing": {...},
                "colors": {...}
            }
        }
        """
```

**Key Features**:
- Extract text with coordinates (PyMuPDF)
- Compare section structure
- Detect visual differences (spacing, alignment, fonts)
- Generate structured JSON report

#### 1.2 LaTeX Structure Analyzer
**File**: `src/resume_builder/tools/latex_structure_analyzer.py`

```python
class LaTeXStructureAnalyzerTool(BaseTool):
    """Analyze LaTeX structure and map to PDF sections."""
    
    def _analyze_latex(self, tex_path: str) -> Dict:
        """
        Returns:
        {
            "sections": {
                "header": {
                    "line_range": [45, 67],
                    "commands": ["\\name", "\\email", "\\customcventry"],
                    "markers": ["% === AUTO:HEADER ==="],
                    "custom_commands": ["\\customcventry", "\\awardentry"]
                },
                ...
            },
            "template_markers": [...],
            "custom_commands": {
                "\\customcventry": {
                    "definition": "...",
                    "usage_count": 5,
                    "line": 18
                }
            }
        }
        """
```

**Key Features**:
- Parse LaTeX structure
- Map sections to line numbers
- Identify custom commands
- Track template markers

### Phase 2: Crew Agent

#### 2.1 Template Fixer Agent
**File**: `src/resume_builder/config/agents.yaml`

```yaml
template_fixer:
  role: LaTeX Template Visual Matching Specialist
  goal: Fix LaTeX templates to match reference PDF visually while preserving data-driven design
  backstory: >
    You are an expert at matching LaTeX-generated resumes to reference PDFs.
    You compare PDFs, analyze differences, and fix LaTeX templates iteratively.
    
    Your process:
    1. Use pdf_comparison_tool to compare reference vs generated PDFs
    2. Use latex_structure_analyzer to understand current LaTeX structure
    3. Identify what needs to change (spacing, fonts, layout, commands)
    4. Generate LaTeX fixes that:
       - Match the reference visually
       - Preserve data model (use \name{}, \email{}, etc.)
       - Keep template generality
       - Don't hard-code personal info
    5. Validate fixes by recompiling and comparing again
    
    CRITICAL RULES:
    - Never hard-code personal information
    - Always use macros/commands for data fields
    - Preserve custom commands if they work
    - Comment out broken commands, don't delete
    - Maintain template markers (% === AUTO:... ===)
  tools:
    - read_latex_file
    - write_latex_file
    - pdf_comparison_tool
    - latex_structure_analyzer
    - latex_compile
  llm: gpt-4o  # Use stronger model for complex template matching
```

#### 2.2 Template Fixing Task
**File**: `src/resume_builder/config/tasks.yaml`

```yaml
fix_template_to_match_reference_task:
  description: >
    Compare reference_resume.pdf with generated_resume.pdf and fix LaTeX templates
    to match the reference visually.
    
    Steps:
    1. Use pdf_comparison_tool to generate diff report
    2. Use latex_structure_analyzer to understand current structure
    3. Fix header (remove leftover text, align icons, fix spacing)
    4. Fix links (ensure full URLs, no duplicates, correct labels)
    5. Fix section formatting (spacing, fonts, order)
    6. Recompile and verify
    
    Write fixed LaTeX to templates/main.tex (or custom template path).
    Preserve all data-driven macros and template markers.
  expected_output: >
    Fixed LaTeX template that produces PDF matching reference visually
  agent: template_fixer
  context: []
  output_file: output/template_fix_report.json
```

### Phase 3: Integration

#### 3.1 Add to Pipeline
**File**: `src/resume_builder/main.py`

```python
def run_template_matching(
    reference_pdf_path: str,
    generated_pdf_path: str,
    template_path: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Match generated PDF to reference PDF by fixing LaTeX templates.
    
    Returns:
        (fixed_latex_path, fix_report)
    """
    from resume_builder.crew import ResumeTeam
    from crewai import Crew, Process
    
    team = ResumeTeam()
    fixer = team.template_fixer()  # New agent
    
    # Create comparison task
    task = Task(
        description=f"""
        Compare {reference_pdf_path} with {generated_pdf_path}.
        Fix LaTeX template at {template_path or 'templates/main.tex'} to match reference.
        """,
        agent=fixer,
        expected_output="Fixed LaTeX template"
    )
    
    crew = Crew(
        agents=[fixer],
        tasks=[task],
        process=Process.sequential
    )
    
    result = crew.kickoff()
    return result
```

---

## Why This Approach?

### Low-Level Code Benefits:
1. **Fast**: PDF comparison is O(n) where n = pages
2. **Precise**: Exact text extraction, coordinate mapping
3. **Deterministic**: Same inputs → same outputs
4. **Reusable**: Tools can be used by multiple agents

### Crew-Level Benefits:
1. **Semantic Understanding**: Understands "header spacing" vs "section spacing"
2. **Intelligent Fixes**: Generates appropriate LaTeX, not just pattern matching
3. **Context Awareness**: Knows what to preserve (data model) vs change (layout)
4. **Iterative Refinement**: Can reason about multiple fixes together

### Hybrid Benefits:
1. **Best of Both**: Precision + Intelligence
2. **Cost Effective**: Expensive LLM calls only for fix generation, not comparison
3. **Maintainable**: Clear separation of concerns
4. **Testable**: Low-level tools can be unit tested

---

## Alternative: Pure Low-Level Approach

**Pros**:
- Faster execution
- More deterministic
- Easier to debug

**Cons**:
- Hard to handle semantic differences
- Requires extensive rule-based logic
- Less flexible for edge cases

**When to Use**: If you have well-defined, repetitive differences that can be pattern-matched.

---

## Alternative: Pure Crew Approach

**Pros**:
- Very flexible
- Handles edge cases well
- Can reason about complex differences

**Cons**:
- Expensive (many LLM calls)
- Slower
- Less deterministic
- Harder to debug

**When to Use**: If differences are highly variable and require semantic understanding.

---

## Recommendation

**Use the Hybrid Approach** because:
1. Template matching requires both precision (layout) and intelligence (semantic fixes)
2. PDF comparison is well-suited for deterministic code
3. LaTeX fix generation benefits from LLM reasoning
4. Cost-effective: compare once, fix intelligently
5. Maintainable: clear tool boundaries

---

## Implementation Priority

1. **Phase 1** (Low-level tools): Foundation - enables everything else
2. **Phase 2** (Crew agent): Core functionality - generates fixes
3. **Phase 3** (Integration): Polish - makes it usable

---

## Example Workflow

```python
# User workflow
1. Upload reference_resume.pdf
2. Generate resume (produces generated_resume.pdf)
3. Run template matching:
   result = run_template_matching(
       reference_pdf_path="reference_resume.pdf",
       generated_pdf_path="output/generated/final_resume.pdf",
       template_path="templates/main.tex"
   )
4. Review fixed template
5. Regenerate resume with fixed template
6. Verify match
```

---

## Tools to Create

1. `PdfComparisonTool` - Compare PDFs structurally
2. `LaTeXStructureAnalyzerTool` - Parse LaTeX structure
3. `TemplateFixerAgent` - Generate intelligent fixes
4. Integration function in `main.py`

---

## Next Steps

1. Implement `PdfComparisonTool` using PyMuPDF
2. Implement `LaTeXStructureAnalyzerTool` using regex/pylatex
3. Create `template_fixer` agent in `agents.yaml`
4. Create `fix_template_to_match_reference_task` in `tasks.yaml`
5. Add integration function to `main.py`
6. Test with real reference PDF

