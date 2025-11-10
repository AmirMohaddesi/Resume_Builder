# GitHub Repository Setup

Guide to connecting your AI Resume Builder project to GitHub.

## Prerequisites

- Git installed on your system
- GitHub account
- Project already initialized with git (already done ✅)

## Step 1: Create GitHub Repository

1. **Go to GitHub**: https://github.com
2. **Click "New repository"** (or go to https://github.com/new)
3. **Repository settings**:
   - **Name**: `Resume_Builder` (or your preferred name)
   - **Description**: "AI-powered resume builder using CrewAI"
   - **Visibility**: Choose Public or Private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
4. **Click "Create repository"**

## Step 2: Verify .gitignore

Your `.gitignore` should exclude sensitive files. Verify it includes:

```
# Environment variables
.env
.env.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/

# Output files (optional - you may want to track some)
output/logs/
output/*.pdf
output/*.tex
output/*.json

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

## Step 3: Add Remote Repository

After creating the GitHub repository, GitHub will show you commands. Use these:

```bash
# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/Resume_Builder.git

# Or if using SSH:
git remote add origin git@github.com:YOUR_USERNAME/Resume_Builder.git
```

**Verify remote was added**:
```bash
git remote -v
```

## Step 4: Stage and Commit Files

```bash
# Stage all files
git add .

# Commit
git commit -m "Initial commit: AI Resume Builder with documentation"
```

## Step 5: Push to GitHub

```bash
# Push to main/master branch
git branch -M main  # Rename branch to 'main' if needed
git push -u origin main
```

If your default branch is `master`:
```bash
git push -u origin master
```

## Step 6: Verify

1. **Refresh your GitHub repository page**
2. **All files should be visible**
3. **README.md should render with formatting**

## Common Issues

### Authentication Required

If you get authentication errors:

**Option 1: Personal Access Token (Recommended)**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Use token as password when pushing:
   ```bash
   git push -u origin main
   # Username: your-username
   # Password: your-token
   ```

**Option 2: SSH Keys**
1. Generate SSH key: `ssh-keygen -t ed25519 -C "your_email@example.com"`
2. Add to GitHub: Settings → SSH and GPG keys → New SSH key
3. Use SSH URL: `git@github.com:USERNAME/REPO.git`

### Branch Name Mismatch

If GitHub uses `main` but you have `master`:
```bash
git branch -M main
git push -u origin main
```

### Large Files

If you get errors about large files:
```bash
# Remove large files from history (if needed)
git rm --cached output/large_file.pdf

# Or use Git LFS for large files
git lfs install
git lfs track "*.pdf"
git add .gitattributes
```

## Updating Repository

After making changes:

```bash
# Stage changes
git add .

# Commit
git commit -m "Description of changes"

# Push
git push
```

## Protecting Sensitive Information

### Before First Push

**Check for sensitive data**:
```bash
# Search for API keys in files
grep -r "sk-" . --exclude-dir=.git
grep -r "OPENAI_API_KEY" . --exclude-dir=.git

# Make sure .env is in .gitignore
cat .gitignore | grep .env
```

### If You Already Pushed Secrets

1. **Rotate your API keys immediately**
2. **Remove from history**:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push** (⚠️ Warning: This rewrites history):
   ```bash
   git push origin --force --all
   ```

## Repository Settings

### Recommended GitHub Settings

1. **Branch Protection** (Settings → Branches):
   - Protect `main` branch
   - Require pull request reviews (optional)

2. **Secrets** (Settings → Secrets and variables → Actions):
   - Add `OPENAI_API_KEY` for CI/CD (if using)

3. **Topics** (Repository page → ⚙️ → Topics):
   - Add: `ai`, `resume-builder`, `crewai`, `gradio`, `latex`

4. **Description**: Update with project description

## Next Steps

- **Add License**: Create `LICENSE` file (MIT, Apache, etc.)
- **Add Contributing Guide**: Create `CONTRIBUTING.md` (optional)
- **Set up GitHub Actions**: For CI/CD (optional)
- **Create Releases**: Tag versions for releases

## Quick Reference

```bash
# Initial setup
git remote add origin https://github.com/USERNAME/REPO.git
git add .
git commit -m "Initial commit"
git push -u origin main

# Regular updates
git add .
git commit -m "Update description"
git push

# Check status
git status
git remote -v
```

---

**See Also**: [Deployment Guide](DEPLOYMENT.md) | [Configuration](CONFIGURATION.md)

