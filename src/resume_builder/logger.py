"""
Centralized logging configuration for the Resume Builder.

This module sets up structured logging with file and console output,
making it easy to debug issues quickly.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logging(
    log_dir: Path,
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_dir: Directory where log files will be stored
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        
    Returns:
        Configured logger instance
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("resume_builder")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)8s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    simple_formatter = logging.Formatter(
        fmt="[%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # File handler - detailed logs
    if log_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"resume_builder_{timestamp}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File gets everything
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Also create a "latest.log" symlink for easy access
        latest_log = log_dir / "latest.log"
        if latest_log.exists():
            latest_log.unlink()
        try:
            latest_log.write_text(str(log_file.name))  # Store reference
        except Exception:
            pass
    
    # Console handler - simpler output
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Optional logger name (defaults to 'resume_builder')
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"resume_builder.{name}")
    return logging.getLogger("resume_builder")


# Initialize default logger (will be configured by main.py)
_logger: Optional[logging.Logger] = None


def init_logger(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Initialize the global logger."""
    global _logger
    _logger = setup_logging(log_dir, log_level)
    return _logger

