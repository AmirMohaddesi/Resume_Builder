# Deployment Guide

How to export and deploy the AI Resume Builder project.

## Exporting the Project

### Option 1: Git Repository

If using Git:

```bash
git add .
git commit -m "Export project"
git push
```

### Option 2: Archive

Create a zip/tar archive:

```bash
# Exclude unnecessary files
zip -r resume_builder.zip . \
  -x "*.pyc" \
  -x "__pycache__/*" \
  -x ".venv/*" \
  -x "output/logs/*" \
  -x ".git/*"
```

### Option 3: Package Distribution

Build a distributable package:

```bash
# Using uv
uv build

# Or using pip
pip install build
python -m build
```

This creates a wheel (`.whl`) file in `dist/` that can be installed elsewhere.

## Deployment Options

### Local Deployment

For personal use:

1. **Clone/Download** the project
2. **Follow Installation Guide** ([INSTALLATION.md](INSTALLATION.md))
3. **Configure** `.env` file
4. **Run**: `crewai run`

### Cloud Deployment

#### Option A: Gradio Spaces (Hugging Face)

1. **Create account** at https://huggingface.co
2. **Create new Space** (Gradio template)
3. **Upload project files**
4. **Set secrets** (API keys) in Space settings
5. **Deploy** - Gradio Spaces handles hosting

**Requirements file** for Spaces:
```python
# requirements.txt
crewai[tools]==1.2.1
gradio>=4.44.0
pypdf>=6.1.3
python-docx>=1.2.0
python-dotenv>=1.0.1
```

**Note**: LaTeX compilation requires a server with `pdflatex` installed. Consider using Overleaf API or pre-compiling templates.

#### Option B: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

# Install LaTeX
RUN apt-get update && apt-get install -y \
    texlive-full \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 7860

# Run application
CMD ["python", "-m", "resume_builder.main"]
```

Build and run:

```bash
docker build -t resume-builder .
docker run -p 7860:7860 -e OPENAI_API_KEY=your-key resume-builder
```

#### Option C: Cloud VM (AWS, GCP, Azure)

1. **Launch VM** with Python 3.12+
2. **Install LaTeX**:
   ```bash
   sudo apt-get install texlive-full  # Ubuntu/Debian
   ```
3. **Clone project**:
   ```bash
   git clone <repo-url>
   cd Resume_Builder
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Configure** `.env` file
6. **Run with screen/tmux**:
   ```bash
   screen -S resume-builder
   crewai run
   # Detach: Ctrl+A, D
   ```

### Serverless Deployment

For serverless (AWS Lambda, Google Cloud Functions):

**Note**: LaTeX compilation requires system binaries, which may not be available in serverless environments. Consider:

1. **Pre-compile templates** to PDF
2. **Use Overleaf API** for LaTeX compilation
3. **Separate services**: API for AI, separate service for PDF generation

## Environment Configuration

### Production .env

```bash
# API Keys
OPENAI_API_KEY=sk-proj-...

# Or use local models for privacy
OLLAMA_BASE_URL=http://localhost:11434

# Server Configuration
GRADIO_SERVER_PORT=7860
GRADIO_SERVER_NAME=0.0.0.0  # Allow external access

# Logging
LOG_LEVEL=INFO

# Security (if exposing publicly)
GRADIO_AUTH=username:password  # Optional: Basic auth
```

### Environment Variables in Cloud

- **Hugging Face Spaces**: Use "Secrets" tab
- **Docker**: Use `-e` flags or `.env` file
- **Cloud VMs**: Set in system environment or use `.env`

## Security Considerations

### API Key Protection

1. **Never commit** `.env` files to Git
2. **Use secrets management** in cloud platforms
3. **Rotate keys** regularly
4. **Use local models** for sensitive data

### Access Control

For public deployments:

```python
# In main.py, modify run_ui():
demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
    share=False,  # Don't create public link
    auth=("username", "password")  # Basic auth
)
```

### Data Privacy

- **Local models**: No data leaves your server
- **Cloud models**: Data sent to API provider
- **Generated files**: Stored in `output/` directory
- **Logs**: May contain resume data - review before sharing

## Scaling Considerations

### Single User

- Current setup is sufficient
- No additional configuration needed

### Multiple Users

Consider:

1. **User isolation**: Separate `output/` directories per user
2. **Queue system**: Use Gradio's queue feature
3. **Database**: Store profiles in database instead of files
4. **Caching**: Cache parsed profiles to reduce API calls

### High Traffic

1. **Load balancer**: Distribute requests
2. **Multiple instances**: Run multiple app instances
3. **Async processing**: Use background jobs for generation
4. **CDN**: Serve static assets via CDN

## Monitoring

### Logs

Logs are stored in `output/logs/`:

- `latest.log` - Most recent log
- `resume_builder_YYYYMMDD_HHMMSS.log` - Timestamped logs

### Health Checks

Create a simple health check endpoint:

```python
# In main.py
def health_check():
    return {"status": "ok", "version": "0.1.0"}

# Add to Gradio app
demo.load(health_check, None, None)
```

## Backup Strategy

### Important Files to Backup

1. **User profiles**: `output/user_profile.json`
2. **Custom templates**: `output/custom_template.tex`
3. **Configuration**: `.env` (securely)
4. **Generated resumes**: `output/final_resume.pdf`

### Automated Backups

```bash
# Example backup script
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp output/user_profile.json "$BACKUP_DIR/"
cp output/custom_template.tex "$BACKUP_DIR/" 2>/dev/null
tar -czf "$BACKUP_DIR/output.tar.gz" output/
```

## Troubleshooting Deployment

### Port Already in Use

```bash
# Find process using port
lsof -i :7860  # Linux/Mac
netstat -ano | findstr :7860  # Windows

# Kill process or change port
GRADIO_SERVER_PORT=7861 crewai run
```

### LaTeX Not Found in Docker

Ensure LaTeX is installed in Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y texlive-full
```

### API Key Not Working

1. Check `.env` file is loaded
2. Verify API key is correct
3. Check API key has sufficient credits/quota
4. Test with: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"`

## Next Steps

- [Installation](INSTALLATION.md) - Setup instructions
- [Configuration](CONFIGURATION.md) - Environment setup
- [Troubleshooting](TROUBLESHOOTING.md) - Common deployment issues

---

**See Also**: [System Architecture](ARCHITECTURE.md) | [Usage](USAGE.md)

