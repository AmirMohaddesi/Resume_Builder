# LaTeX Setup Guide

Complete guide to installing and configuring LaTeX for the AI Resume Builder.

## Why LaTeX?

LaTeX produces professional, ATS-friendly PDFs with consistent formatting. The AI Resume Builder uses LaTeX to generate high-quality resumes.

## Installation by Platform

### Windows: MiKTeX

1. **Download**: https://miktex.org/download
2. **Install**: Run installer, choose "Add MiKTeX to PATH"
3. **Verify**:
   ```powershell
   pdflatex --version
   ```
4. **First Run**: MiKTeX may prompt to install packages on first use - click "Install"

### Linux: TeX Live

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install texlive-full
```

**CentOS/RHEL**:
```bash
sudo yum install texlive-scheme-full
```

**Verify**:
```bash
pdflatex --version
```

### macOS: MacTeX

1. **Download**: https://www.tug.org/mactex/
2. **Install**: Run the installer (large download, ~4GB)
3. **Verify**:
   ```bash
   pdflatex --version
   ```

## Required Packages

The system automatically installs/validates these packages, but you may need:

### Core Packages (Usually Pre-installed)

- `moderncv` - Resume document class
- `fontawesome5` - Icons
- `amssymb` - Math symbols (`\mathbb{}`)
- `hyperref` - Links
- `xcolor` - Colors
- `geometry` - Page layout

### Installing Missing Packages

**MiKTeX**:
1. Open **MiKTeX Console**
2. Go to **Packages** tab
3. Search for package name
4. Click **Install**

**TeX Live**:
```bash
sudo tlmgr install package-name
```

**MacTeX**:
```bash
sudo tlmgr install package-name
```

## Package Installation Commands

If the system warns about missing packages:

```bash
# MiKTeX (Windows)
# Use MiKTeX Console GUI

# TeX Live (Linux)
sudo tlmgr install fontawesome5
sudo tlmgr install moderncv

# MacTeX (macOS)
sudo tlmgr install fontawesome5
sudo tlmgr install moderncv
```

## Verifying Installation

Test LaTeX compilation:

```bash
# Create test file
echo '\documentclass{article}\begin{document}Test\end{document}' > test.tex

# Compile
pdflatex test.tex

# Check output
ls test.pdf  # Should exist
```

## Common Issues

### Package Not Found

**Error**: `File 'package.sty' not found`

**Solution**:
1. Install package via package manager
2. Run `pdflatex` again (may need to refresh package database)
3. On MiKTeX: Use "Refresh FNDB" in Console

### Font Issues

**Error**: Font expansion errors with FontAwesome

**Solution**: System automatically fixes this. If issues persist:
1. Update MiKTeX/TeX Live to latest version
2. Reinstall `fontawesome5` package
3. Check `output/rendered_resume.tex` has `\pdfprotrudechars=0`

### PATH Issues

**Error**: `pdflatex: command not found`

**Solution**:
1. **Windows**: Restart terminal after MiKTeX installation
2. **Linux/Mac**: Add to PATH:
   ```bash
   export PATH="/usr/local/texlive/2024/bin/x86_64-linux:$PATH"
   ```
3. **Verify**: `which pdflatex` should show path

## Minimal Installation

If you want a smaller installation:

**MiKTeX**: Choose "Basic MiKTeX" - packages install on-demand

**TeX Live**: Install `texlive-base` instead of `texlive-full` (packages install as needed)

**Note**: First compilation may be slower as packages install automatically.

## Updating LaTeX

### MiKTeX

1. Open **MiKTeX Console**
2. Click **Update** tab
3. Click **Check for updates**
4. Install updates

### TeX Live

```bash
sudo tlmgr update --self
sudo tlmgr update --all
```

### MacTeX

```bash
sudo tlmgr update --self
sudo tlmgr update --all
```

## Testing with AI Resume Builder

After installation:

1. **Run the application**: `crewai run`
2. **Upload a resume** and generate
3. **Check for warnings**: System shows missing package warnings
4. **Install packages** as needed

## Alternative: Overleaf

If LaTeX installation is problematic:

1. **Use Overleaf**: https://www.overleaf.com
2. **Generate LaTeX** in the app
3. **Copy** `output/rendered_resume.tex` to Overleaf
4. **Compile** there
5. **Download** PDF

The system generates Overleaf-compatible LaTeX.

## Next Steps

- [Installation Guide](INSTALLATION.md) - Complete setup
- [Troubleshooting](TROUBLESHOOTING.md) - LaTeX issues
- [Custom Templates](CUSTOM_TEMPLATES.md) - Using templates

---

**See Also**: [Configuration](CONFIGURATION.md) | [Usage](USAGE.md)

