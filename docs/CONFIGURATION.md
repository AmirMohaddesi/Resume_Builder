# Configuration Guide

This guide explains how to configure the AI Resume Builder, including API keys, LLM models, and environment variables.

## Environment Variables

All configuration is done through a `.env` file in the project root. Create this file if it doesn't exist:

```bash
# .env file
OPENAI_API_KEY=your-api-key-here
```

## API Keys

### OpenAI (Default)

The system uses OpenAI models by default. Set your API key:

```bash
OPENAI_API_KEY=sk-your-key-here
```

### Other Providers

CrewAI supports multiple LLM providers. See [LLM Models](#llm-models) section below.

## LLM Models

The system uses different LLM models for different agents. You can configure these in `src/resume_builder/config/agents.yaml`.

### Using OpenAI Models (Default)

No additional configuration needed if you have `OPENAI_API_KEY` set. The system uses:
- `gpt-4o` for complex tasks (content selection, writing)
- `gpt-4o-mini` for simpler tasks (validation, checking)

### Using Local/Private Models

For privacy-sensitive use cases, you can use local models like Llama, Ollama, or other compatible providers.

#### Option 1: Ollama (Local Llama Models)

1. **Install Ollama**: https://ollama.ai

2. **Pull a model**:
   ```bash
   ollama pull llama3.2
   # or
   ollama pull mistral
   ```

3. **Configure in agents.yaml**:
   ```yaml
   profile_validator:
     role: Profile Validator
     # ... other config ...
     llm: ollama/llama3.2  # Use Ollama model
   ```

4. **Set environment variable** (if needed):
   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   ```

#### Option 2: Custom LLM Provider

CrewAI supports any LLM provider that implements the LangChain LLM interface. To use a custom provider:

1. **Install the provider's SDK**:
   ```bash
   pip install langchain-anthropic  # Example: Anthropic
   ```

2. **Set provider-specific environment variables**:
   ```bash
   ANTHROPIC_API_KEY=your-key
   # or
   GOOGLE_API_KEY=your-key
   ```

3. **Update agents.yaml** to use the model identifier:
   ```yaml
   jd_analyst:
     llm: claude-3-opus  # Anthropic Claude
     # or
     llm: gemini-pro     # Google Gemini
   ```

#### Option 3: Custom LangChain LLM

For advanced users, you can create a custom LLM wrapper:

1. Create a file `src/resume_builder/custom_llm.py`:
   ```python
   from langchain.llms.base import LLM
   
   class CustomLLM(LLM):
       # Implement your custom LLM
       pass
   ```

2. Use it in `crew.py`:
   ```python
   from resume_builder.custom_llm import CustomLLM
   
   @agent
   def profile_validator(self) -> Agent:
       custom_llm = CustomLLM()
       config = self.agents_config["profile_validator"]
       config["llm"] = custom_llm
       return Agent(config=config, verbose=True)
   ```

## Model Selection Strategy

Different agents use different models based on task complexity:

| Agent | Default Model | Why |
|-------|--------------|-----|
| Profile Validator | gpt-4o-mini | Simple validation task |
| JD Analyst | gpt-4o | Complex parsing and extraction |
| Experience Selector | gpt-4o | Strategic content selection |
| Summary Writer | gpt-4o | Creative writing task |
| Template Validator | gpt-4o-mini | Simple package checking |

You can change these in `src/resume_builder/config/agents.yaml` by modifying the `llm:` field for each agent.

## Environment Variables Reference

### Required

- `OPENAI_API_KEY` - OpenAI API key (if using OpenAI models)

### Optional

- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO
- `GRADIO_SERVER_PORT` - Port for Gradio UI. Default: 7860
- `PORT` - Alternative port variable (used if GRADIO_SERVER_PORT not set)
- `TEMPLATE_PATH` - Custom default LaTeX template path
- `PROFILE_PATH` - Custom default profile JSON path

### Provider-Specific

- `ANTHROPIC_API_KEY` - For Anthropic Claude models
- `GOOGLE_API_KEY` - For Google Gemini models
- `OLLAMA_BASE_URL` - For Ollama local models (default: http://localhost:11434)
- `AZURE_OPENAI_API_KEY` - For Azure OpenAI
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL

## Example .env File

```bash
# OpenAI (default)
OPENAI_API_KEY=sk-proj-...

# Or use local Ollama for privacy
# OLLAMA_BASE_URL=http://localhost:11434

# Logging
LOG_LEVEL=INFO

# Server
GRADIO_SERVER_PORT=7860

# Paths (optional)
TEMPLATE_PATH=src/resume_builder/templates/main.tex
PROFILE_PATH=src/resume_builder/data/profile.json
```

## Privacy Considerations

### Using Local Models

For maximum privacy, use local models:

1. **Ollama** (Recommended for local):
   - Completely offline
   - No data sent to external services
   - Good performance with modern hardware

2. **Self-hosted API**:
   - Run your own LLM API server
   - Point CrewAI to your local endpoint
   - Full control over data

### Data Handling

- Resume data is processed locally
- Only LLM API calls send data (unless using local models)
- All generated files stay in `output/` directory
- No data is stored by the application itself

## Cost Optimization

### Using Smaller Models

Edit `src/resume_builder/config/agents.yaml` to use cheaper models:

```yaml
# Change from gpt-4o to gpt-4o-mini for cost savings
jd_analyst:
  llm: gpt-4o-mini  # Was: gpt-4o
```

### Rate Limiting

CrewAI has built-in rate limiting. You can adjust:
- `max_iter` in `crew.py` - Limits total iterations
- `max_execution_time` in `crew.py` - Timeout limit

## Verification

Test your configuration:

```bash
# Check environment variables are loaded
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('API Key set:', bool(os.getenv('OPENAI_API_KEY')))"

# Run the application
crewai run
```

## Next Steps

- [Quick Start Guide](QUICK_START.md) - Create your first resume
- [System Architecture](ARCHITECTURE.md) - Understand how it works
- [Troubleshooting](TROUBLESHOOTING.md) - Common configuration issues

---

**See Also**: [Installation](INSTALLATION.md) | [Deployment](DEPLOYMENT.md)

