# Custom LaTeX Templates

Guide to using your own LaTeX templates with the AI Resume Builder.

## Overview

You can upload your own LaTeX template (`.tex` file) to customize the resume formatting. The system automatically validates packages and handles compatibility issues.

## Template Requirements

### Required Markers

Your template should include these markers where content will be inserted:

```latex
% === AUTO:PREAMBLE ===
% (Identity information: \name{}, \email{}, etc.)

% === AUTO:SUMMARY ===
% (Professional summary)

% === AUTO:EXPERIENCE ===
% (Work experience entries)

% === AUTO:EDUCATION ===
% (Education entries)

% === AUTO:SKILLS ===
% (Skills list)

% === AUTO:ACHIEVEMENTS ===
% (Projects - optional)

% === AUTO:ADDITIONAL ===
% (Additional sections - optional)
```

### Example Template Structure

```latex
\documentclass[11pt,a4paper]{moderncv}
\moderncvstyle{banking}
\moderncvcolor{blue}

% Your packages
\usepackage{fontawesome5}
\usepackage{amssymb}

% === AUTO:PREAMBLE ===

\begin{document}
\makecvtitle

% === AUTO:SUMMARY ===

% === AUTO:EXPERIENCE ===

% === AUTO:EDUCATION ===

% === AUTO:SKILLS ===

\end{document}
```

## Automatic Package Detection

The system automatically:

1. **Detects missing packages**:
   - If you use `\mathbb{}` → adds `\usepackage{amssymb}`
   - If you use `\faIcon` → adds `\usepackage{fontawesome5}`

2. **Uncomments packages**:
   - If `fontawesome5` is commented out, it gets uncommented

3. **Fixes font issues**:
   - Disables font expansion for FontAwesome compatibility

## Package Validation

When you upload a template:

1. **Template Validator Agent** checks for missing packages
2. **Warnings** are shown if packages are missing
3. **Recommendations** are provided for installation

### Example Warning

```
⚠️ Missing LaTeX packages: fontawesome5
📦 Install with: tlmgr install fontawesome5
```

## Using Your Template

1. **Create your .tex file** with the required markers
2. **Upload it** in Step 1 (along with your resume)
3. **System validates** it automatically
4. **Generation uses** your template

## Template Best Practices

### 1. Use Standard Markers

Always use the exact marker format:
```latex
% === AUTO:SUMMARY ===
```

Not:
```latex
% AUTO:SUMMARY
% === SUMMARY ===
```

### 2. Preserve Document Structure

Keep your `\documentclass`, `\begin{document}`, and `\end{document}` intact.

### 3. Package Compatibility

- **FontAwesome**: System handles font expansion issues
- **Math Symbols**: System adds `amssymb` if needed
- **Other packages**: Install via MiKTeX/TeX Live

### 4. Custom Commands

You can define custom commands in your template:

```latex
\newcommand{\customsection}[1]{\section*{#1}}
```

These will be preserved in the generated LaTeX.

## Extracting Information from Templates

If you upload a `.tex` file along with your resume:

- **File Collector Agent** extracts:
  - Email, phone, website
  - LinkedIn, GitHub URLs
  - Other links (Google Scholar, etc.)

- **Merges with resume data**:
  - Fills missing fields
  - Fixes malformed data
  - Adds dynamic fields

## Template Examples

### Minimal Template

```latex
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{geometry}

% === AUTO:PREAMBLE ===

\begin{document}

% === AUTO:SUMMARY ===

% === AUTO:EXPERIENCE ===

% === AUTO:EDUCATION ===

% === AUTO:SKILLS ===

\end{document}
```

### ModernCV Template

See `src/resume_builder/templates/main.tex` for a complete ModernCV example.

## Troubleshooting Templates

### Missing Packages

**Error**: `! Undefined control sequence. \mathbb`

**Solution**: System automatically adds `\usepackage{amssymb}`. If it doesn't, check the rendered LaTeX file.

### Font Expansion Errors

**Error**: `pdfTeX error (font expansion): auto expansion is only possible with scalable fonts`

**Solution**: System automatically disables font expansion. This is handled automatically.

### Template Not Used

**Issue**: Default template is used instead of custom

**Solution**: 
1. Check file was uploaded correctly
2. Verify file is at `output/custom_template.tex`
3. Check template validation report

## Advanced: Template Variables

The system supports these variables in the preamble:

- `\firstname{}` - First name
- `\familyname{}` - Last name  
- `\email{}` - Email address
- `\phone{}` - Phone number
- `\address{}` - Address
- `\homepage{}` - Website
- `\social[linkedin]{}` - LinkedIn
- `\social[github]{}` - GitHub

These are automatically populated from your profile.

## Next Steps

- [Usage Guide](USAGE.md) - How to upload templates
- [Troubleshooting](TROUBLESHOOTING.md) - Template issues
- [System Architecture](ARCHITECTURE.md) - How templates are processed

---

**See Also**: [Installation](INSTALLATION.md) | [Advanced Features](ADVANCED.md)

