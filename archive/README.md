# Archive Folder

This folder contains scripts and utilities that are not currently used in the main codebase but may be useful for future reference or manual operations.

## Contents

### `compile_tex.py`
Standalone script for manually compiling LaTeX files to PDF. Useful for:
- Testing LaTeX compilation without running the full pipeline
- Debugging LaTeX issues
- Quick manual compilation

**Usage:**
```bash
python archive/compile_tex.py path/to/file.tex [--engine pdflatex|xelatex|auto]
```

### `timings.py`
Timing utilities for performance tracking. Contains:
- `Timer` class - Context manager for timing operations
- `record_timing()` function - Record timing data to JSON

**Note:** Not currently used in the main codebase, but may be useful for future performance analysis.

---

**Last Updated:** November 2025

