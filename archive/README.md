# Archive Directory

This directory contains files that are no longer actively used in the project but are kept for reference.

## Archived Files

### Python Scripts (Replaced/Unused)

- **`orchestration_phased.py`** - Old version of orchestration logic, replaced by `src/resume_builder/orchestration.py`
- **`test_yaml_parse.py`** - Test script for YAML parsing, not used in production
- **`validate_config.py`** - Configuration validation script, replaced by integrated validation
- **`compile_tex.py`** - Legacy LaTeX compilation script
- **`timings.py`** - Legacy timing analysis script

### Orphaned JSON Files (Test/Example Data)

These JSON files were in the root directory but are not referenced by the codebase. The actual system uses files in the `output/` directory:

- **`expected_profile.json`** - Test/example profile data (system uses `output/user_profile.json`)
- **`input_resume.json`** - Test/example resume input data
- **`job_description.json`** - Test/example job description (system uses `output/parsed_jd.json`)
- **`parsed_job_description.json`** - Test/example parsed JD (system uses `output/parsed_jd.json`)
- **`profile.json`** - Test/example profile (system uses `src/resume_builder/data/profile.json` or `output/user_profile.json`)
- **`selected_experiences.json`** - Test/example experiences (system uses `output/selected_experiences.json`)

### Markdown Summary Files (Change Documentation)

These files document changes and improvements made during development:

- **`CLEANUP_AND_TESTS_DIFF.md`** - Documentation of cleanup and test changes
- **`CLEANUP_AND_TESTS_FINAL_DIFF.md`** - Final cleanup and test changes
- **`EDIT_ENGINE_INTEGRATION_DIFF.md`** - Edit engine integration changes
- **`EDIT_ENGINE_INTEGRATION_COMPLETE_DIFF.md`** - Complete edit engine integration
- **`LATEX_BUILDER_REFACTOR_DIFF.md`** - LaTeX builder refactoring documentation
- **`ORCHESTRATION_PHASED_DIFF.md`** - Orchestration phased execution changes
- **`ORCHESTRATION_PHASED_COMPLETE_DIFF.txt`** - Complete orchestration phased changes
- **`TASKS_SHORTENING_DIFF.md`** - Task shortening changes
- **`TASKS_DIFF_SUMMARY.txt`** - Task changes summary
- **`OPTIMIZATION_SUMMARY.md`** - Optimization summary
- **`REFACTORING_SUMMARY.md`** - Refactoring summary
- **`PROGRESS_BAR_PROBLEM.md`** - Progress bar issue documentation
- **`LLM_IMPROVEMENT_ANALYSIS.md`** - LLM improvement analysis
- **`HELPER_FUNCTIONS_DOCUMENTATION.md`** - Helper functions documentation (replaced by LLM tools)

## Why These Files Were Archived

1. **Replaced by Better Solutions**: Many scripts were replaced by integrated LLM-powered tools or improved implementations
2. **Development Documentation**: Markdown files were temporary documentation of changes during development
3. **Legacy Code**: Some scripts are from earlier versions of the project

## Note

These files are kept for historical reference and may be useful for understanding the evolution of the codebase. They are not imported or used by the current codebase.
