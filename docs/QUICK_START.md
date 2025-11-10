# Quick Start Guide

Get up and running with the AI Resume Builder in 5 minutes!

## Prerequisites

- ✅ Python 3.10+ installed
- ✅ LaTeX installed (MiKTeX/TeX Live)
- ✅ API key configured (see [Configuration](CONFIGURATION.md))

## Step 1: Start the Application

```bash
crewai run
```

Or:

```bash
python -m resume_builder.main
```

The Gradio UI will open automatically in your browser at `http://127.0.0.1:7860`

## Step 2: Upload Your Resume

1. **Upload Files** (Step 1):
   - Drag & drop your resume (PDF, DOCX, DOC, or TXT)
   - Optionally upload a custom LaTeX template (.tex)
   - Optionally upload reference PDFs for style matching
   - The system automatically parses your resume!

2. **Review Profile** (Step 2):
   - Check that your information was extracted correctly
   - Add any missing links (LinkedIn, GitHub, etc.)
   - Use the ➕ button to add custom fields if needed
   - Click **"Save Profile"**

3. **Generate Resume** (Step 3):
   - Paste the job description
   - Click **"Generate Resume"**
   - Wait for processing (usually 1-3 minutes)
   - Download your tailored PDF!

## What Happens Behind the Scenes

1. **Parsing**: AI extracts your information from the resume
2. **Analysis**: AI analyzes the job description
3. **Selection**: AI selects most relevant experiences, skills, and projects
4. **Writing**: AI writes a tailored summary
5. **Generation**: Python generates LaTeX and compiles to PDF

## Output Files

All generated files are in the `output/` directory:

- `final_resume.pdf` - Your tailored resume
- `rendered_resume.tex` - LaTeX source (for editing)
- `user_profile.json` - Your extracted profile data
- `selected_experiences.json` - Selected experiences for this job
- `tailor_plan.json` - AI's reasoning for selections

## Tips for Best Results

1. **Complete Profile**: Make sure your resume has all relevant information
2. **Detailed Job Description**: Paste the full job posting, not just the title
3. **Custom Template**: Upload your own .tex template for consistent formatting
4. **Reference PDFs**: Upload examples of resumes you like for style matching

## Next Steps

- [User Guide](USAGE.md) - Detailed usage instructions
- [Custom Templates](CUSTOM_TEMPLATES.md) - Using your own LaTeX templates
- [Advanced Features](ADVANCED.md) - Multi-file uploads and more

---

**Having Issues?** Check [Troubleshooting](TROUBLESHOOTING.md)

