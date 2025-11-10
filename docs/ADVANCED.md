# Advanced Features

Advanced usage and features of the AI Resume Builder.

## Multi-File Upload

### Uploading Multiple Files

You can upload multiple files at once:

1. **Resume + Template**: Upload both your resume and a custom .tex template
2. **Resume + References**: Upload resume and reference PDFs for style matching
3. **All Together**: Resume + template + multiple reference PDFs

### File Detection Logic

The system intelligently detects file types:

- **First .docx/.doc/.txt** → Treated as your resume
- **First .pdf** (if no other resume) → Treated as resume
- **All .tex files** → Custom templates (first one used)
- **Additional .pdf files** → Reference documents for style matching

## Reference PDFs

### How It Works

When you upload reference PDFs:

1. **AI analyzes** the PDFs for style preferences
2. **Planner agent** considers style when creating the tailoring plan
3. **Formatting insights** are used to guide resume generation

### Use Cases

- Match formatting from a previous resume
- Follow style guidelines from company examples
- Maintain consistent branding across applications

## Dynamic Field Detection

### Automatic Field Detection

The system automatically:

- **Shows GitHub** field only if detected in your files
- **Adds Google Scholar** if found in .tex files
- **Detects other URLs** and creates custom fields
- **Categorizes links** (Twitter/X, personal websites, etc.)

### Custom Fields

You can manually add fields:

1. Click **"➕ Add Custom Link"**
2. Enter field name (e.g., "Portfolio", "Medium", "Twitter")
3. Enter URL
4. Field is saved to your profile

## Information Merging

### From Multiple Sources

When you upload both resume and .tex:

1. **Resume is parsed** → Creates initial profile
2. **.tex is analyzed** → Extracts contact information
3. **Data is merged** → .tex data fills gaps in resume data
4. **Priority**: .tex data is used if resume data is missing or malformed

### Example

**Resume parsing** might miss or mangle:
- LinkedIn URL
- GitHub URL  
- Website URL

**.tex extraction** recovers:
- Clean LinkedIn URL from `\social[linkedin]{}`
- Clean GitHub URL from `\href{https://github.com/...}`
- Website from `\homepage{}`

## Template Package Validation

### Automatic Validation

When you upload a custom template:

1. **Template Validator** checks for missing packages
2. **Package Checker Tool** uses `kpsewhich` to verify installation
3. **Warnings** are shown for missing packages
4. **Recommendations** are provided

### Package Auto-Fix

The system automatically:

- Adds `\usepackage{amssymb}` if `\mathbb{}` is used
- Uncomments `\usepackage{fontawesome5}` if FontAwesome icons are used
- Disables font expansion to fix MiKTeX compatibility

## Profile Management

### Profile File

Your profile is saved in: `output/user_profile.json`

### Reusing Profiles

- **Same profile** can be used for multiple job applications
- **Edit profile** in the UI and save
- **Backup** the JSON file for future use

### Profile Structure

```json
{
  "identity": {
    "first": "John",
    "last": "Doe",
    "email": "john@example.com",
    "website": "https://johndoe.com",
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "google_scholar": "https://scholar.google.com/...",
    "education": [...]
  },
  "experience": [...],
  "skills": [...],
  "projects": [...],
  "awards": [...]
}
```

## Batch Processing

### Multiple Job Descriptions

To generate resumes for multiple jobs:

1. **Save your profile** once
2. **Generate resume** for Job 1
3. **Change job description** in the UI
4. **Generate resume** for Job 2
5. **Repeat** for as many jobs as needed

Each generation creates a new tailored resume based on the same profile.

## Output Files

### Generated Files

After each generation:

- `final_resume.pdf` - Your tailored resume (overwritten each time)
- `rendered_resume.tex` - LaTeX source (for manual editing)
- `tailor_plan.json` - AI's reasoning for this job
- `ats_report.json` - Keyword coverage analysis

### Preserving Outputs

To keep multiple versions:

1. **Rename files** after generation:
   ```bash
   cp output/final_resume.pdf output/resume_company_name.pdf
   cp output/tailor_plan.json output/plan_company_name.json
   ```

2. **Or use version control**:
   ```bash
   git add output/final_resume.pdf
   git commit -m "Resume for Company X"
   ```

## Customization

### Changing Agent Behavior

Edit `src/resume_builder/config/agents.yaml`:

```yaml
summary_writer:
  role: Professional Summary Writer
  goal: Write compelling 2-3 sentence professional summaries
  # Modify backstory to change behavior
  backstory: >
    You are a professional resume writer who...
```

### Changing Task Descriptions

Edit `src/resume_builder/config/tasks.yaml`:

```yaml
select_experiences_task:
  description: >
    Select the top 3-5 work experiences...
    # Modify to change selection criteria
```

### Adding New Agents

1. Add agent definition to `agents.yaml`
2. Register agent in `crew.py`:
   ```python
   @agent
   def my_new_agent(self) -> Agent:
       return Agent(config=self.agents_config["my_new_agent"])
   ```
3. Create task in `tasks.yaml`
4. Register task in `crew.py`

## Next Steps

- [System Architecture](ARCHITECTURE.md) - Understand the system
- [Configuration](CONFIGURATION.md) - Customize LLM models
- [Deployment](DEPLOYMENT.md) - Export and deploy

---

**See Also**: [Usage](USAGE.md) | [Custom Templates](CUSTOM_TEMPLATES.md)

