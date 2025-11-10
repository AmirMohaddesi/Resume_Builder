# Installation Guide

This guide will walk you through installing the AI Resume Builder on your system.

## Prerequisites

- **Python 3.10 - 3.13** (Python 3.12 recommended)
- **LaTeX Distribution** (MiKTeX on Windows, TeX Live on Linux/Mac)
- **Git** (for cloning the repository)

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Resume_Builder
```

## Step 2: Set Up Python Environment

### Option A: Using uv (Recommended)

```bash
# Install uv if you don't have it
pip install uv

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Option B: Using pip

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Install LaTeX

### Windows (MiKTeX)

1. Download MiKTeX from: https://miktex.org/download
2. Run the installer
3. Ensure "Add MiKTeX to PATH" is checked during installation
4. Verify installation:
   ```powershell
   pdflatex --version
   ```

### Linux (TeX Live)

```bash
sudo apt-get install texlive-full  # Ubuntu/Debian
# OR
sudo yum install texlive-scheme-full  # CentOS/RHEL
```

### macOS (MacTeX)

1. Download MacTeX from: https://www.tug.org/mactex/
2. Run the installer
3. Verify installation:
   ```bash
   pdflatex --version
   ```

## Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example if it exists
cp .env.example .env
```

See [Configuration Guide](CONFIGURATION.md) for details on setting up API keys and LLM models.

## Step 5: Verify Installation

Run the application:

```bash
crewai run
```

Or directly:

```bash
python -m resume_builder.main
```

The Gradio UI should open at `http://127.0.0.1:7860`

## Optional: Install Additional Dependencies

For resume parsing (PDF/DOCX):

```bash
pip install pypdf python-docx
```

These are already included in `requirements.txt` but can be installed separately if needed.

## Troubleshooting

### Python Version Issues

Ensure you're using Python 3.10 or higher:

```bash
python --version
```

### LaTeX Not Found

If `pdflatex` is not found:

1. **Windows**: Restart your terminal after installing MiKTeX
2. **Linux/Mac**: Ensure TeX Live/MacTeX is in your PATH
3. Verify: `which pdflatex` (Linux/Mac) or `where pdflatex` (Windows)

### Import Errors

If you get import errors:

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +  # Linux/Mac
Get-ChildItem -Path . -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force  # Windows

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

## Next Steps

- Read the [Quick Start Guide](QUICK_START.md) to create your first resume
- Configure your [LLM models](CONFIGURATION.md) for privacy or cost optimization
- Learn about [Custom Templates](CUSTOM_TEMPLATES.md)

---

**See Also**: [Troubleshooting](TROUBLESHOOTING.md) | [LaTeX Setup](LATEX_SETUP.md)

