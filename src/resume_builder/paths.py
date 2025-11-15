"""Centralized path management for resume builder.

All paths should be imported from this module to ensure consistency.
"""
from __future__ import annotations

from pathlib import Path

# Resolve once, reuse everywhere
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src" / "resume_builder"
OUTPUT_DIR = PROJECT_ROOT / "output"
BUILD_DIR = OUTPUT_DIR / "build"
GENERATED_DIR = OUTPUT_DIR / "generated"
LOG_DIR = OUTPUT_DIR / "logs"
TEMPLATES = SRC_DIR / "templates"


def resolve_under_root(p: str | Path) -> Path:
    """Resolve a path relative to PROJECT_ROOT if not absolute.
    
    Args:
        p: Path string or Path object
        
    Returns:
        Absolute Path object
    """
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def ensure_dirs():
    """Create all required output directories if they don't exist."""
    for d in (OUTPUT_DIR, BUILD_DIR, GENERATED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

