"""Preflight checks for fast-fail validation."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from ..paths import OUTPUT_DIR, BUILD_DIR, ensure_dirs


class PreflightInput(BaseModel):
    """Input schema for PreflightTool."""
    model_config = ConfigDict(extra="forbid")
    require_engine: str = Field(default="xelatex", description="LaTeX engine to check for: 'xelatex' (preferred) or 'pdflatex' (fallback)")


class PreflightTool(BaseTool):
    """Verify LaTeX engine exists and output dirs are writable."""
    
    name: str = "preflight_check"
    description: str = "Verify LaTeX engine exists and output directories are writable. Returns error if checks fail."
    args_schema: Type[BaseModel] = PreflightInput
    
    def _run(self, require_engine: str = "xelatex") -> Dict[str, Any]:
        """Run preflight checks.
        
        Args:
            require_engine: LaTeX engine to check for (xelatex preferred, pdflatex fallback)
            
        Returns:
            Dict with 'ok' (bool), 'engine' (path if found), 'engine_type' (xelatex/pdflatex), 
            'warning' (if fallback used), 'error' (if failed)
        """
        ensure_dirs()
        
        # Check if preferred engine (xelatex) exists
        engine_path = shutil.which(require_engine)
        engine_type = require_engine
        
        # If xelatex not found, try pdflatex as fallback
        if not engine_path and require_engine == "xelatex":
            fallback_path = shutil.which("pdflatex")
            if fallback_path:
                engine_path = fallback_path
                engine_type = "pdflatex"
            else:
                return {
                    "ok": False,
                    "error": "Neither xelatex nor pdflatex found on PATH. Please install LaTeX distribution (MiKTeX or TeX Live)."
                }
        elif not engine_path:
            return {
                "ok": False,
                "error": f"{require_engine} not found on PATH. Please install LaTeX distribution."
            }
        
        # Check write permissions
        for d in (OUTPUT_DIR, BUILD_DIR):
            test_file = d / ".write_test"
            try:
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink(missing_ok=True)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"No write permission in {d}: {e}"
                }
        
        result = {
            "ok": True,
            "engine": engine_path,
            "engine_type": engine_type,
            "unicode_ready": engine_type == "xelatex",
            "output_dir": str(OUTPUT_DIR),
            "build_dir": str(BUILD_DIR)
        }
        
        if engine_type == "pdflatex" and require_engine == "xelatex":
            result["warning"] = "xelatex not found, using pdflatex fallback. Unicode characters may cause issues."
        
        return result

