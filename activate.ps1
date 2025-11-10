# Quick activation script for Resume Builder virtual environment
# Usage: .\activate.ps1

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Activate virtual environment
& "$scriptDir\.venv\Scripts\Activate.ps1"

# Change to project directory (if not already there)
Set-Location $scriptDir

# Display welcome message
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Resume Builder - Virtual Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host "Project directory: $scriptDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
Write-Host "  - Run pipeline:    crewai run" -ForegroundColor White
Write-Host "  - Clean logs:     python cleanup.py" -ForegroundColor White
Write-Host "  - Run tests:       pytest tests/" -ForegroundColor White
Write-Host ""

