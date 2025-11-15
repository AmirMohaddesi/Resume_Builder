#!/usr/bin/env python
import yaml
from pathlib import Path

tasks_file = Path("src/resume_builder/config/tasks.yaml")
tasks = yaml.safe_load(tasks_file.read_text(encoding='utf-8'))

task_name = "write_cover_letter_task"
if task_name in tasks:
    task_config = tasks[task_name]
    print(f"Type: {type(task_config)}")
    print(f"Is dict: {isinstance(task_config, dict)}")
    if isinstance(task_config, dict):
        print(f"Keys: {list(task_config.keys())}")
    else:
        print(f"Value (first 200 chars): {repr(task_config)[:200]}")
else:
    print(f"Task '{task_name}' not found in tasks")
    print(f"Available tasks: {[k for k in tasks.keys() if k.endswith('_task')]}")

