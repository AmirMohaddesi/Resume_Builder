"""Progress reporting tool for orchestrator to update progress bar during crew execution."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Type, Optional, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ProgressReporterInput(BaseModel):
    """Input schema for the ProgressReporterTool."""
    progress: float = Field(..., description="Progress value between 0.0 and 1.0, where 0.0 is start and 1.0 is complete")
    description: str = Field(..., description="Human-readable description of the current step being executed")
    progress_file: str = Field(default="output/progress.json", description="Path to the progress file (optional, defaults to output/progress.json)")
    task_name: Optional[str] = Field(default=None, description="Name of the current task (e.g., 'profile_validation_task')")
    task_duration_seconds: Optional[float] = Field(default=None, description="Duration of the task in seconds")
    model_config = ConfigDict(extra="ignore")


class ProgressReporterTool(BaseTool):
    """Tool for agents to report progress during execution.
    
    This tool allows agents to update a progress file that the main pipeline
    can read to update the Gradio progress bar in real-time.
    """
    name: str = "progress_reporter"
    description: str = (
        "Report progress of the current task to update the user interface. "
        "Use this tool to inform users about what step is currently being executed. "
        "Progress values should be between 0.0 and 1.0, where 0.0 is start and 1.0 is complete. "
        "For crew execution, use values between 0.2 and 0.6 (since crew is 20%-60% of total pipeline). "
        "Optionally include task_name and task_duration_seconds to track timing information."
    )
    args_schema: Type[BaseModel] = ProgressReporterInput

    def _run(
        self,
        progress: float,
        description: str,
        progress_file: str = "output/progress.json",
        task_name: Optional[str] = None,
        task_duration_seconds: Optional[float] = None
    ) -> str:
        """Report progress update with optional task timing information.
        
        Args:
            progress: Progress value between 0.0 and 1.0
            description: Human-readable description of current step
            progress_file: Path to progress file (default: output/progress.json)
            task_name: Optional name of the task (e.g., 'profile_validation_task')
            task_duration_seconds: Optional duration of the task in seconds
        
        Returns:
            Confirmation message
        """
        try:
            # Ensure progress is in valid range
            progress = max(0.0, min(1.0, float(progress)))
            
            # Log the progress update
            timing_info = ""
            if task_name and task_duration_seconds is not None:
                timing_info = f" [{task_name}: {task_duration_seconds:.1f}s]"
            logger.info(f"[TOOL] progress_reporter called: {progress*100:.1f}% - {description}{timing_info}")
            
            # Resolve progress file path
            progress_path = Path(progress_file)
            if not progress_path.is_absolute():
                # Try to find project root
                current = Path(__file__).resolve()
                for _ in range(5):
                    if (current / "output").exists() or (current / "pyproject.toml").exists():
                        progress_path = current / progress_file
                        break
                    if current.parent == current:
                        break
                    current = current.parent
                else:
                    # Fallback: use current working directory
                    progress_path = Path.cwd() / progress_file
            
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing progress data to preserve task history
            existing_data: Dict[str, Any] = {}
            if progress_path.exists():
                try:
                    with open(progress_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    pass  # Start fresh if file is corrupted
            
            # Create progress data
            progress_data: Dict[str, Any] = {
                "progress": progress,
                "description": str(description),
                "timestamp": datetime.now().isoformat(),
                "current_task": task_name if task_name else None
            }
            
            # Add task timing if provided
            if task_name and task_duration_seconds is not None:
                # Initialize tasks_history if it doesn't exist
                if "tasks_history" not in existing_data:
                    existing_data["tasks_history"] = []
                
                # Add or update task timing
                tasks_history: List[Dict[str, Any]] = existing_data.get("tasks_history", [])
                
                # Check if task already exists in history
                task_found = False
                for task_entry in tasks_history:
                    if task_entry.get("task_name") == task_name:
                        task_entry["duration_seconds"] = task_duration_seconds
                        task_entry["completed_at"] = datetime.now().isoformat()
                        task_found = True
                        break
                
                # Add new task entry if not found
                if not task_found:
                    tasks_history.append({
                        "task_name": task_name,
                        "duration_seconds": task_duration_seconds,
                        "completed_at": datetime.now().isoformat()
                    })
                
                progress_data["tasks_history"] = tasks_history
            
            # Merge with existing data (preserve tasks_history)
            if "tasks_history" in existing_data:
                progress_data["tasks_history"] = existing_data.get("tasks_history", [])
            
            # Write to file
            with open(progress_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
            
            logger.info(f"[TOOL] progress_reporter SUCCESS: Updated {progress_file} with {progress*100:.1f}%")
            return f"Progress updated: {progress*100:.1f}% - {description}"
        
        except Exception as e:
            logger.error(f"[TOOL] progress_reporter FAILED: {str(e)}")
            return f"Error updating progress: {str(e)}"

