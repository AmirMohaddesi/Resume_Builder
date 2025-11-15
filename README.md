# AI Resume Builder

Generate tailored resumes for any job description using AI-powered multi-agent systems.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python -m resume_builder.main
# Or
crewai run
```

Opens at: http://127.0.0.1:7860

## ✨ Features

- **Multi-format Resume Parsing**: PDF, DOCX, DOC, TXT
- **Intelligent Content Selection**: AI selects most relevant experiences for each job
- **Custom LaTeX Templates**: Use your own templates with automatic package validation
- **Privacy-First**: Support for local LLM models (Llama, Ollama, etc.)
- **Dynamic Fields**: Automatically detects and adds fields based on your resume
- **Reference PDFs**: Match style preferences from existing resumes

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) folder:

- **[Installation Guide](docs/INSTALLATION.md)** - Step-by-step setup
- **[Quick Start Guide](docs/QUICK_START.md)** - Get running in 5 minutes
- **[Configuration](docs/CONFIGURATION.md)** - API keys, LLM models, environment variables
- **[User Guide](docs/USAGE.md)** - Complete usage instructions
- **[System Architecture](docs/ARCHITECTURE.md)** - How the system works
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Exporting and deploying the project
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

See [docs/README.md](docs/README.md) for the full documentation index.

## 🎯 How It Works

1. **Upload Your Resume** - PDF, DOCX, DOC, or TXT (auto-extracts info)
2. **Review & Edit Profile** - Add missing links, customize fields
3. **Paste Job Description** - AI analyzes and tailors your resume
4. **Download PDF** - Professional, ATS-friendly resume ready!

## 📋 Requirements

- Python 3.10 - 3.13
- LaTeX (MiKTeX/TeX Live/MacTeX)
- API Key (OpenAI or other LLM provider)

See [Installation Guide](docs/INSTALLATION.md) for detailed setup.

## 🔧 Configuration

Create a `.env` file in the project root:

```bash
# 1. REQUIRED: OpenAI API Key
OPENAI_API_KEY=your-api-key-here

# 2. OPTIONAL: LLM Model (Cost Control)
# Set this to control which model ALL agents use
# Default: gpt-4o-mini (cheapest, ~$0.15 per 1M tokens)
# Options: gpt-4o-mini, gpt-4o, gpt-3.5-turbo, ollama/llama3.2
LLM_MODEL=gpt-4o-mini

# 3. OPTIONAL: Logging & Server
LOG_LEVEL=INFO
GRADIO_SERVER_PORT=7860
```

**💡 Cost Savings Tip**: Set `LLM_MODEL=gpt-4o-mini` to reduce costs by ~94% compared to using `gpt-4o`!

For local/private models (Llama, Ollama) and advanced configuration, see [Configuration Guide](docs/CONFIGURATION.md).

## 📁 Output Files

All generated files are in the `output/` directory:

- `final_resume.pdf` - Your tailored resume
- `rendered_resume.tex` - LaTeX source (for editing)
- `user_profile.json` - Your extracted profile data
- `tailor_plan.json` - AI's reasoning for selections

## 🏗️ System Architecture

The system uses **11 specialized AI agents** working together:

- **Input Processing**: Profile validation, file collection, template validation, JD analysis
- **Content Selection**: Experience, project, and skill selection
- **Content Writing**: Summary and education section generation
- **Quality Assurance**: ATS checking, privacy validation, strategic planning

See [System Architecture](docs/ARCHITECTURE.md) for details.

## 🤝 Contributing

Found an issue or want to improve the project? Contributions welcome!

## 📄 License

[Add your license here]

---

**Need Help?** Check the [Documentation](docs/README.md) or [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
