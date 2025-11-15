#!/usr/bin/env python
"""Validate tasks.yaml and agents.yaml structure."""
import yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple

def validate_tasks(tasks: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Validate all tasks have required keys."""
    errors = []
    required_keys = {"description", "expected_output", "agent"}
    optional_keys = {"context", "output_file"}  # output_file is optional - some tasks use tools instead
    
    for task_name, task_config in tasks.items():
        if not task_name.endswith("_task"):
            continue
            
        if not isinstance(task_config, dict):
            errors.append((task_name, f"Task is not a dict, got {type(task_config).__name__}: {repr(task_config)[:100]}"))
            continue
            
        # Check required keys
        missing = required_keys - set(task_config.keys())
        if missing:
            errors.append((task_name, f"Missing required keys: {missing}"))
        
        # Check for scalar string (wrong format)
        if isinstance(task_config, str):
            errors.append((task_name, f"Task is a scalar string, not a mapping"))
        
        # Check agent exists
        agent_name = task_config.get("agent")
        if not agent_name:
            errors.append((task_name, "Missing 'agent' key"))
        elif not isinstance(agent_name, str):
            errors.append((task_name, f"Agent name is not a string: {type(agent_name).__name__}"))
    
    return errors

def validate_agents(agents: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Validate all agents have required keys."""
    errors = []
    required_keys = {"role", "goal", "backstory"}
    
    for agent_name, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            errors.append((agent_name, f"Agent is not a dict, got {type(agent_config).__name__}: {repr(agent_config)[:100]}"))
            continue
        
        missing = required_keys - set(agent_config.keys())
        if missing:
            errors.append((agent_name, f"Missing required keys: {missing}"))
    
    return errors

def cross_validate(tasks: Dict[str, Any], agents: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Cross-validate that all task agents exist."""
    errors = []
    agent_names = set(agents.keys())
    
    for task_name, task_config in tasks.items():
        if not task_name.endswith("_task") or not isinstance(task_config, dict):
            continue
        
        agent_name = task_config.get("agent")
        if agent_name and agent_name not in agent_names:
            errors.append((task_name, f"References non-existent agent: {agent_name}"))
    
    return errors

def main():
    """Run all validations."""
    print("=" * 80)
    print("Validating tasks.yaml and agents.yaml")
    print("=" * 80)
    
    # Load tasks
    tasks_file = Path("src/resume_builder/config/tasks.yaml")
    print(f"\nLoading {tasks_file}...")
    try:
        tasks = yaml.safe_load(tasks_file.read_text(encoding='utf-8'))
        print(f"[OK] Loaded {len([k for k in tasks.keys() if k.endswith('_task')])} tasks")
    except Exception as e:
        print(f"[ERROR] Failed to load tasks.yaml: {e}")
        return 1
    
    # Load agents
    agents_file = Path("src/resume_builder/config/agents.yaml")
    print(f"\nLoading {agents_file}...")
    try:
        agents = yaml.safe_load(agents_file.read_text(encoding='utf-8'))
        print(f"[OK] Loaded {len(agents)} agents")
    except Exception as e:
        print(f"[ERROR] Failed to load agents.yaml: {e}")
        return 1
    
    # Validate tasks
    print("\n" + "=" * 80)
    print("Validating tasks...")
    print("=" * 80)
    task_errors = validate_tasks(tasks)
    if task_errors:
        print(f"[ERROR] Found {len(task_errors)} task errors:")
        for task_name, error in task_errors:
            print(f"  - {task_name}: {error}")
    else:
        print("[OK] All tasks are valid")
    
    # Validate agents
    print("\n" + "=" * 80)
    print("Validating agents...")
    print("=" * 80)
    agent_errors = validate_agents(agents)
    if agent_errors:
        print(f"[ERROR] Found {len(agent_errors)} agent errors:")
        for agent_name, error in agent_errors:
            print(f"  - {agent_name}: {error}")
    else:
        print("[OK] All agents are valid")
    
    # Cross-validate
    print("\n" + "=" * 80)
    print("Cross-validating task->agent references...")
    print("=" * 80)
    cross_errors = cross_validate(tasks, agents)
    if cross_errors:
        print(f"[ERROR] Found {len(cross_errors)} cross-validation errors:")
        for task_name, error in cross_errors:
            print(f"  - {task_name}: {error}")
    else:
        print("[OK] All task->agent references are valid")
    
    # Check write_cover_letter_task specifically
    print("\n" + "=" * 80)
    print("Checking write_cover_letter_task specifically...")
    print("=" * 80)
    wcl = tasks.get("write_cover_letter_task")
    if wcl is None:
        print("[ERROR] write_cover_letter_task not found!")
    elif not isinstance(wcl, dict):
        print(f"[ERROR] write_cover_letter_task is not a dict, got {type(wcl).__name__}")
        print(f"   Value: {repr(wcl)[:200]}")
    else:
        print("[OK] write_cover_letter_task is a dict")
        print(f"   Keys: {list(wcl.keys())}")
        print(f"   Agent: {wcl.get('agent')}")
        print(f"   Has description: {'description' in wcl}")
        print(f"   Has expected_output: {'expected_output' in wcl}")
        print(f"   Has output_file: {'output_file' in wcl}")
        print(f"   Has context: {'context' in wcl}")
        if 'context' in wcl:
            print(f"   Context: {wcl['context']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    total_errors = len(task_errors) + len(agent_errors) + len(cross_errors)
    if total_errors == 0:
        print("[OK] All validations passed!")
        return 0
    else:
        print(f"[ERROR] Found {total_errors} total errors")
        return 1

if __name__ == "__main__":
    exit(main())

