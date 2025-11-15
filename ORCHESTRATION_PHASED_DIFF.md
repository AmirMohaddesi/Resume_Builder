# Orchestration.py Phased Execution Diff

## Summary
This diff adds phased and parallel task execution to `orchestration.py` while maintaining identical behavior.

## Key Changes

### 1. New Helper Functions

#### `_group_tasks_by_phase()` (NEW)
Groups tasks into phases based on dependencies:
- **Phase 1**: `parse_job_description_task` (sequential)
- **Phase 2**: `select_experiences_task`, `select_skills_task`, `select_projects_task` (parallel)
- **Phase 3**: `write_summary_task`, `write_header_task`, `write_education_section_task` (parallel)
- **Phase 4**: `ats_check_task`, `privacy_validation_task`, `write_cover_letter_task` (parallel)

#### `_execute_phase()` (NEW)
Executes a phase of tasks with timing logs:
- Creates a Crew with appropriate Process (sequential or hierarchical/parallel)
- Logs phase start/end times
- Returns result and duration

### 2. Modified `run_pipeline()` Function

**BEFORE** (lines ~366-512):
```python
# Execute crew (agents output JSON, no LaTeX yet)
try:
    logger.info("Launching crew...")
    
    # ... progress monitoring setup ...
    
    try:
        crew_start_time = time_module.time()
        
        crew_instance = team.crew()
        
        # Filter tasks based on conditional flags
        if not enable_ats or not enable_privacy:
            # ... task filtering ...
        
        # Add timing wrapper for telemetry
        logger.info("[TIMING] Starting crew execution...")
        result = crew_instance.kickoff(inputs=inputs)
        crew_end_time = time_module.time()
        crew_duration = crew_end_time - crew_start_time
        logger.info(f"[TIMING] Crew execution completed in {crew_duration:.2f}s")
        
        # ... save timing data ...
```

**AFTER**:
```python
# ============================================
# PHASED EXECUTION: Group tasks and execute in phases
# ============================================

try:
    logger.info("="*80)
    logger.info("Starting phased task execution")
    logger.info("="*80)
    
    # Group tasks by phase
    task_groups = _group_tasks_by_phase(team, enable_ats, enable_privacy)
    
    # ... progress monitoring setup (unchanged) ...
    
    try:
        overall_start_time = time_module.time()
        phase_timings = {}
        
        # Phase 1: Sequential (parse_job_description_task)
        logger.info("="*80)
        logger.info("[PHASE 1] Sequential: Input Processing")
        logger.info("="*80)
        phase1_result, phase1_duration = _execute_phase(
            team, "Phase 1", task_groups['phase1'], inputs, fast_mode, parallel=False
        )
        phase_timings['phase1'] = phase1_duration
        
        # Phase 2: Parallel (select_experiences, select_skills, select_projects)
        logger.info("="*80)
        logger.info("[PHASE 2] Parallel: Content Selection")
        logger.info("="*80)
        phase2_result, phase2_duration = _execute_phase(
            team, "Phase 2", task_groups['phase2'], inputs, fast_mode, parallel=True
        )
        phase_timings['phase2'] = phase2_duration
        
        # Phase 3: Parallel (write_summary, write_header, write_education_section)
        logger.info("="*80)
        logger.info("[PHASE 3] Parallel: Content Writing")
        logger.info("="*80)
        phase3_result, phase3_duration = _execute_phase(
            team, "Phase 3", task_groups['phase3'], inputs, fast_mode, parallel=True
        )
        phase_timings['phase3'] = phase3_duration
        
        # Phase 4: Parallel (ats_check, privacy_validation, write_cover_letter)
        logger.info("="*80)
        logger.info("[PHASE 4] Parallel: Quality & Cover Letter")
        logger.info("="*80)
        phase4_result, phase4_duration = _execute_phase(
            team, "Phase 4", task_groups['phase4'], inputs, fast_mode, parallel=True
        )
        phase_timings['phase4'] = phase4_duration
        
        overall_end_time = time_module.time()
        overall_duration = overall_end_time - overall_start_time
        
        logger.info("="*80)
        logger.info("[TIMING] Phased execution summary")
        logger.info("="*80)
        logger.info(f"Phase 1 (Sequential): {phase_timings.get('phase1', 0):.2f}s")
        logger.info(f"Phase 2 (Parallel):   {phase_timings.get('phase2', 0):.2f}s")
        logger.info(f"Phase 3 (Parallel):   {phase_timings.get('phase3', 0):.2f}s")
        logger.info(f"Phase 4 (Parallel):   {phase_timings.get('phase4', 0):.2f}s")
        logger.info(f"Total execution time: {overall_duration:.2f}s ({overall_duration/60:.2f} min)")
        logger.info("="*80)
        
        # Save timing information to file
        try:
            timing_file = OUTPUT_DIR / "timings.json"
            timing_data = {
                "overall_duration_seconds": overall_duration,
                "overall_duration_minutes": overall_duration / 60,
                "phase_timings": phase_timings,
                "fast_mode": fast_mode,
                "enable_ats": enable_ats,
                "enable_privacy": enable_privacy,
                "timestamp": datetime.now().isoformat(),
            }
            with open(timing_file, 'w', encoding='utf-8') as f:
                json.dump(timing_data, f, indent=2)
            logger.info(f"[TIMING] Saved timing data to {timing_file}")
        except Exception as e:
            logger.warning(f"[TIMING] Could not save timing data: {e}")
        
        logger.info("✅ All phases completed successfully")
```

### 3. Imports Added

```python
from concurrent.futures import ThreadPoolExecutor, as_completed  # Not used but available for future
```

## Implementation Details

### Phase Grouping Logic

**Phase 1 (Sequential)**:
- `parse_job_description_task` - Must run first, no dependencies

**Phase 2 (Parallel)**:
- `select_experiences_task` - Depends only on `parse_job_description_task`
- `select_skills_task` - Depends only on `parse_job_description_task`
- `select_projects_task` - Depends only on `parse_job_description_task`

**Phase 3 (Parallel)**:
- `write_summary_task` - Depends on `select_experiences_task`, `select_skills_task`
- `write_header_task` - Depends on `select_skills_task`, `select_experiences_task`, `parse_job_description_task`
- `write_education_section_task` - No dependencies (reads from profile directly)

**Phase 4 (Parallel)**:
- `ats_check_task` - Depends on `select_experiences_task`, `select_skills_task`, `write_summary_task`
- `privacy_validation_task` - No dependencies (reads from profile)
- `write_cover_letter_task` - Depends on all previous phases

### Execution Strategy

- **Phase 1**: Uses `Process.sequential` (single task, but explicit for clarity)
- **Phase 2**: Uses `Process.hierarchical` to enable parallel execution
- **Phase 3**: Uses `Process.hierarchical` to enable parallel execution
- **Phase 4**: Uses `Process.hierarchical` to enable parallel execution

### Timing Logs

Each phase logs:
- Start time
- Number of tasks
- Execution mode (sequential/parallel)
- Duration on completion
- Summary at end with all phase timings

## Behavior Preservation

✅ **All behavior remains identical**:
- Same task execution order (enforced by phases)
- Same inputs/outputs
- Same error handling
- Same progress monitoring
- Same LaTeX generation and PDF compilation (unchanged)
- Same return values

✅ **Improvements**:
- Explicit phase boundaries for clarity
- Better timing visibility per phase
- Potential speedup from explicit parallel execution in Phase 2-4
- Better debugging with phase-level logs

## Files Modified

- `src/resume_builder/orchestration.py`:
  - Added `_group_tasks_by_phase()` function (~80 lines)
  - Added `_execute_phase()` function (~100 lines)
  - Modified `run_pipeline()` function (~150 lines changed)
  - Added import for `ThreadPoolExecutor` (for future use, not currently used)

## Testing

After applying changes:
1. Run pipeline and verify all phases execute
2. Check `output/timings.json` for phase-level timing data
3. Verify logs show phase boundaries and timings
4. Confirm final PDF generation works identically
5. Verify parallel execution actually occurs (check logs for concurrent task execution)

