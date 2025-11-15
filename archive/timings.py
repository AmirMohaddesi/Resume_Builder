"""Timing utilities for performance tracking."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from .paths import OUTPUT_DIR, ensure_dirs


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self):
        self.t0: float | None = None
        self.ms: int | None = None
    
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self
    
    def __exit__(self, *exc):
        if self.t0 is not None:
            self.ms = int((time.perf_counter() - self.t0) * 1000)


def record_timing(**kv: Any) -> None:
    """Record timing data to output/timings.json.
    
    Args:
        **kv: Key-value pairs to record (e.g., step_ms=123, compile_ms=456)
    """
    ensure_dirs()
    p = OUTPUT_DIR / "timings.json"
    data: Dict[str, Any] = {}
    
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    
    data.update(kv)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

