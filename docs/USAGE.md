# User Guide

Complete guide to using the AI Resume Builder interface.

## Interface Overview

The application has a single-page interface with three main sections:

1. **Step 1: Upload Your Files** - Upload resume and optional templates
2. **Step 2: Review & Edit Your Profile** - Review and enhance extracted data
3. **Step 3: Generate Your Tailored Resume** - Generate the final PDF

## Step 1: Upload Your Files

### Supported File Types

- **Resume Files**: `.pdf`, `.docx`, `.doc`, `.txt`
- **Templates**: `.tex` (LaTeX template)
- **References**: `.pdf` (for style matching)

### Upload Process

1. **Click or drag & drop** files into the upload box
2. **Multiple files** can be uploaded at once
3. **Automatic parsing** happens immediately when you upload

### What Gets Extracted

- Personal information (name, email, phone)
- Work experience
- Education
- Skills
- Projects
- Awards

### Dynamic Field Detection

The system automatically:
- Shows **GitHub** field only if detected in your files
- Adds **Google Scholar** if found in .tex files
- Adds other links (Twitter, personal websites, etc.) as dynamic fields
- Extracts missing information from .tex templates

## Step 2: Review & Edit Your Profile

### Standard Fields

Always visible:
- First Name, Last Name
- Job Title
- Email, Phone
- Website/Portfolio
- LinkedIn

### Dynamic Fields

Automatically shown when detected:
- GitHub (if found)
- Google Scholar (if found in .tex)
- Other custom links

### Adding Custom Fields

1. Click **"➕ Add Custom Link"**
2. Enter field name (e.g., "Twitter", "Medium", "Portfolio")
3. Enter the URL
4. Click **"Save"**
5. The field appears in your profile

### Editing JSON Fields

For advanced users, you can edit:
- **Work Experience** (JSON format)
- **Education** (JSON format)
- **Projects** (JSON format)

See the accordion sections for these fields.

### Saving Your Profile

Click **"💾 Save Profile"** to save your information. This creates `output/user_profile.json` which is used for resume generation.

## Step 3: Generate Your Tailored Resume

### Job Description

1. **Paste the full job description** into the text box
2. Include:
   - Job title and company
   - Required skills
   - Responsibilities
   - Qualifications
   - Any other relevant details

3. **More detail = better results!**

### Advanced Options

- **Custom LaTeX Template**: Upload a `.tex` file
  - System validates packages automatically
  - Shows warnings for missing packages
  - Uses your template for formatting

- **Reference PDFs**: Upload example resumes
  - AI analyzes style preferences
  - Helps match formatting and structure

### Generation Process

When you click **"🚀 Generate Resume"**:

1. **AI Analysis** (30-60 seconds)
   - Parses job description
   - Selects relevant experiences
   - Chooses best skills and projects
   - Writes tailored summary

2. **LaTeX Generation** (5-10 seconds)
   - Python generates LaTeX from JSON
   - Applies your template (or default)
   - Validates packages

3. **PDF Compilation** (10-20 seconds)
   - Compiles LaTeX to PDF
   - Handles errors automatically

4. **Download** - Your PDF is ready!

### Output Files

After generation, you'll find:

- **📄 Resume PDF** - Download button in the UI
- **📝 LaTeX Source** - Download for manual editing
- **Status Message** - Shows any warnings or issues

## Understanding Status Messages

### Success Messages

```
✅ Resume parsed successfully!
🔗 Links extracted from .tex file!
✅ 1 LaTeX template(s) - AI will validate packages
```

### Warnings

```
⚠️ Missing LaTeX packages: fontawesome5
📦 Install with: tlmgr install fontawesome5
```

These are informational - the system will try to work around missing packages.

### Errors

If generation fails:
1. Check the error message
2. Look at `output/rendered_resume.tex` for LaTeX issues
3. Copy to Overleaf for detailed error checking
4. See [Troubleshooting](TROUBLESHOOTING.md)

## Best Practices

### For Best Results

1. **Complete Resume**: Include all relevant experiences, skills, and projects
2. **Detailed Job Description**: More context helps AI make better selections
3. **Custom Template**: Use your own .tex for consistent branding
4. **Review Output**: Check the generated PDF and adjust if needed

### Profile Management

- **Save Often**: Click "Save Profile" after making changes
- **Backup**: Your profile is saved in `output/user_profile.json`
- **Reuse**: The same profile can be used for multiple job applications

### Template Tips

- **Package Validation**: System checks for missing packages automatically
- **Font Issues**: If you see font errors, the system tries to fix them
- **Custom Formatting**: Your template's formatting is preserved

## Keyboard Shortcuts

- **Tab**: Navigate between fields
- **Enter**: Submit forms (where applicable)
- **Ctrl+C / Cmd+C**: Copy job description
- **Ctrl+V / Cmd+V**: Paste into text fields

## Next Steps

- [Custom Templates](CUSTOM_TEMPLATES.md) - Create your own LaTeX templates
- [Advanced Features](ADVANCED.md) - Multi-file uploads and reference PDFs
- [System Architecture](ARCHITECTURE.md) - Understand how it works

---

**See Also**: [Quick Start](QUICK_START.md) | [Troubleshooting](TROUBLESHOOTING.md)

