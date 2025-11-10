# Environment Setup

Production and development environment configuration guide.

## Overview

This guide covers environment setup for both development and production deployments. For basic configuration, see [Configuration Guide](CONFIGURATION.md).

## Development Environment

### Local Setup

1. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate      # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure `.env`**:
   ```bash
   OPENAI_API_KEY=your-key-here
   LOG_LEVEL=DEBUG  # For development
   ```

### Development Tools

Optional development dependencies:

```bash
pip install pytest ipykernel jupyter
```

## Production Environment

### Environment Variables

Production `.env` file:

```bash
# API Configuration
OPENAI_API_KEY=sk-proj-...

# Server Configuration
GRADIO_SERVER_PORT=7860
GRADIO_SERVER_NAME=0.0.0.0  # Allow external access

# Logging
LOG_LEVEL=INFO  # Use INFO or WARNING in production

# Security (if exposing publicly)
GRADIO_AUTH=username:password  # Optional: Basic auth

# Paths (optional)
TEMPLATE_PATH=/path/to/default/template.tex
PROFILE_PATH=/path/to/default/profile.json
```

### Security Best Practices

1. **Never commit `.env` files**:
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use secrets management**:
   - Cloud platforms: Use built-in secrets (AWS Secrets Manager, Azure Key Vault, etc.)
   - Docker: Use Docker secrets or environment variables
   - Kubernetes: Use ConfigMaps and Secrets

3. **Rotate API keys** regularly

4. **Use local models** for sensitive data:
   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   ```

## Platform-Specific Setup

### Windows

```powershell
# Set environment variables
$env:OPENAI_API_KEY="your-key"
$env:LOG_LEVEL="INFO"

# Or use .env file (recommended)
```

### Linux

```bash
# System-wide (not recommended for API keys)
export OPENAI_API_KEY="your-key"

# Or use .env file (recommended)
```

### macOS

```bash
# Same as Linux
export OPENAI_API_KEY="your-key"

# Or use .env file (recommended)
```

## Docker Environment

### Dockerfile Environment

```dockerfile
# Set default environment variables
ENV GRADIO_SERVER_PORT=7860
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV LOG_LEVEL=INFO

# Override at runtime
docker run -e OPENAI_API_KEY=your-key resume-builder
```

### Docker Compose

```yaml
version: '3.8'
services:
  resume-builder:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=INFO
    env_file:
      - .env
    ports:
      - "7860:7860"
```

## Cloud Platform Environments

### Hugging Face Spaces

Set secrets in Space settings:
- `OPENAI_API_KEY`
- `GRADIO_SERVER_PORT` (optional)

### AWS/GCP/Azure

Use environment variables or secrets management:
- AWS: Systems Manager Parameter Store or Secrets Manager
- GCP: Secret Manager
- Azure: Key Vault

## Environment Validation

Test your environment:

```python
# test_env.py
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = ['OPENAI_API_KEY']
missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print(f"Missing: {', '.join(missing)}")
else:
    print("✅ All required environment variables set")
```

Run:
```bash
python test_env.py
```

## Troubleshooting

### Variables Not Loading

1. **Check `.env` location**: Must be in project root
2. **Verify format**: `KEY=value` (no spaces around `=`)
3. **Restart application**: Environment variables load at startup

### Port Conflicts

```bash
# Find process using port
lsof -i :7860  # Linux/Mac
netstat -ano | findstr :7860  # Windows

# Change port
GRADIO_SERVER_PORT=7861 python -m resume_builder.main
```

## Next Steps

- [Configuration Guide](CONFIGURATION.md) - API keys and LLM setup
- [Deployment Guide](DEPLOYMENT.md) - Production deployment
- [Installation Guide](INSTALLATION.md) - Complete setup

---

**See Also**: [Troubleshooting](TROUBLESHOOTING.md) | [System Architecture](ARCHITECTURE.md)

