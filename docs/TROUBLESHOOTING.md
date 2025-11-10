# Troubleshooting Guide

Common issues and their solutions.

## Installation Issues

### Python Version

**Error**: `requires-python = ">=3.10,<3.14"`

**Solution**: 
```bash
python --version  # Check version
# Install Python 3.10-3.13 if needed
```

### LaTeX Not Found

**Error**: `pdflatex: command not found`

**Solution**:
1. **Windows**: Install MiKTeX, restart terminal
2. **Linux**: `sudo apt-get install texlive-full`
3. **macOS**: Install MacTeX
4. **Verify**: `pdflatex --version`

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'crewai'`

**Solution**:
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Or with uv
uv pip install -e .
```

## Configuration Issues

### API Key Not Working

**Error**: API authentication failed

**Solution**:
1. Check `.env` file exists in project root
2. Verify key format: `OPENAI_API_KEY=sk-...`
3. Test key: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(bool(os.getenv('OPENAI_API_KEY')))"`
4. Ensure no extra spaces or quotes

### LLM Model Not Found

**Error**: Model not available

**Solution**:
1. **OpenAI**: Check API key has access to the model
2. **Ollama**: Ensure model is pulled: `ollama pull llama3.2`
3. **Custom**: Verify provider SDK is installed

## Runtime Issues

### Crew Initialization Failed

**Error**: `KeyError: 'agent_name'`

**Solution**:
1. Clear Python cache:
   ```bash
   find . -type d -name __pycache__ -exec rm -r {} +  # Linux/Mac
   Get-ChildItem -Path . -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force  # Windows
   ```
2. Restart terminal
3. Verify `agents.yaml` and `tasks.yaml` are valid YAML

### Profile Not Parsing

**Error**: Resume parsing fails or returns empty data

**Solution**:
1. Check file format (PDF/DOCX/TXT supported)
2. Verify file is not corrupted
3. Try a different resume file
4. Check logs: `output/logs/latest.log`

### Fields Empty After Parsing

**Issue**: Website, LinkedIn, GitHub fields are empty

**Solution**:
1. **Upload .tex file** - System extracts links from LaTeX
2. **Manually add** using the ➕ button
3. **Check .tex file** has the links in `\href{}` or `\social[]{}` commands

## LaTeX Compilation Issues

### Missing Packages

**Error**: `! LaTeX Error: File 'package.sty' not found`

**Solution**:
1. System automatically detects and warns about missing packages
2. Install via MiKTeX Console or: `tlmgr install package-name`
3. Check `output/template_validation.json` for warnings

### Font Expansion Error

**Error**: `pdfTeX error (font expansion): auto expansion is only possible with scalable fonts`

**Solution**: System automatically fixes this by disabling font expansion. If error persists:
1. Check `output/rendered_resume.tex` has `\pdfprotrudechars=0`
2. Manually add before `\begin{document}` if missing

### Undefined Control Sequence

**Error**: `! Undefined control sequence. \mathbb`

**Solution**: System automatically adds `\usepackage{amssymb}`. If error persists:
1. Check `output/rendered_resume.tex` has the package
2. Verify template doesn't override package loading

### PDF Not Generated

**Error**: Compilation succeeds but no PDF

**Solution**:
1. Check `output/compile.log` for errors
2. Verify `pdflatex` is working: `pdflatex --version`
3. Check file permissions in `output/` directory
4. Try compiling manually: `pdflatex output/rendered_resume.tex`

## UI Issues

### Gradio Not Opening

**Error**: Browser doesn't open or connection refused

**Solution**:
1. Check port is available: `netstat -ano | findstr :7860` (Windows)
2. Change port: Set `GRADIO_SERVER_PORT=7861` in `.env`
3. Access manually: `http://127.0.0.1:7860`

### Files Not Uploading

**Issue**: Upload button doesn't work

**Solution**:
1. Check browser console for errors
2. Verify file types are supported
3. Try smaller files first
4. Check file permissions

### Fields Not Populating

**Issue**: Resume parsed but fields are empty

**Solution**:
1. Check upload status message
2. Verify resume has extractable text (not just images)
3. Try uploading .tex file to extract links
4. Manually add missing information

## Performance Issues

### Slow Generation

**Issue**: Resume generation takes too long

**Solution**:
1. **Use faster models**: Change `gpt-4o` to `gpt-4o-mini` in `agents.yaml`
2. **Reduce iterations**: Lower `max_iter` in `crew.py`
3. **Check API rate limits**: May be throttled
4. **Use local models**: Ollama for faster, local processing

### High API Costs

**Issue**: API costs are high

**Solution**:
1. **Use smaller models**: `gpt-4o-mini` instead of `gpt-4o`
2. **Reduce iterations**: Lower `max_iter` and `max_execution_time`
3. **Use local models**: Ollama for zero API costs
4. **Cache profiles**: Reuse parsed profiles for multiple jobs

## Getting Help

### Check Logs

Always check logs first:

```bash
# Latest log
cat output/logs/latest.log

# Or open in editor
code output/logs/latest.log
```

### Verify Configuration

```bash
# Check environment variables
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('API Key:', bool(os.getenv('OPENAI_API_KEY')))"

# Check LaTeX
pdflatex --version

# Check Python version
python --version
```

### Common Solutions Checklist

- [ ] Cleared Python cache (`__pycache__`)
- [ ] Restarted terminal/IDE
- [ ] Verified `.env` file exists and has correct format
- [ ] Checked LaTeX installation (`pdflatex --version`)
- [ ] Reviewed logs in `output/logs/`
- [ ] Verified file permissions
- [ ] Tested with default template first

## Next Steps

- [Installation Guide](INSTALLATION.md) - Reinstall if needed
- [Configuration](CONFIGURATION.md) - Check your setup
- [System Architecture](ARCHITECTURE.md) - Understand the system

---

**See Also**: [LaTeX Setup](LATEX_SETUP.md) | [Deployment](DEPLOYMENT.md)

