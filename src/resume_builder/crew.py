# crew.py - Register tools so CrewAI can load them from YAML
from __future__ import annotations
import logging
import os
import yaml
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, tool

logger = logging.getLogger(__name__)

# Import tools
from resume_builder.tools.privacy_guard import PrivacyGuardTool
from resume_builder.tools.profile_reader import ProfileReaderTool
from resume_builder.tools.latex_package_checker import LaTeXPackageCheckerTool
from resume_builder.tools.tex_info_extractor import TexInfoExtractorTool
from resume_builder.tools.progress_reporter import ProgressReporterTool
from resume_builder.tools.latex_file_editor import (
    ReadLatexFileTool,
    WriteLatexFileTool,
)
from resume_builder.tools.json_file_io import (
    ReadJsonFileTool,
    WriteJsonFileTool,
)
from resume_builder.tools.preflight import PreflightTool
from resume_builder.tools.ats_rules import ATSRulesTool
from resume_builder.tools.pdf_comparison_tool import PdfComparisonTool
from resume_builder.tools.latex_structure_analyzer import LaTeXStructureAnalyzerTool
from resume_builder.tools.latex_compile import LatexCompileTool


@CrewBase
class ResumeTeam:
    """Simplified crew for resume generation: parse → select → write → analyze."""

    # CrewAI will load these YAMLs as dicts
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    
    def __init__(self, *args, **kwargs):
        """Initialize ResumeTeam and load LLM model from environment variable."""
        # Don't call super().__init__() - CrewBase handles initialization differently
        # Get LLM model from environment variable (defaults to gpt-4o-mini for cost savings)
        self.llm_model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
        logger.info(f"[LLM CONFIG] Using model: {self.llm_model} (set LLM_MODEL or RESUME_BUILDER_LLM in .env to change)")
        
        # Store fast_mode if provided (for crew creation)
        self.fast_mode = kwargs.get('fast_mode', False)
        
        # Substitute environment variables in loaded configs
        # This will be called after CrewBase initializes the configs
        try:
            self._substitute_env_vars_in_configs()
        except AttributeError:
            # Configs might not be loaded yet, will be handled when accessed
            logger.debug("[CONFIG] Configs not yet loaded, will substitute when accessed")
    
    def _substitute_env_vars_in_configs(self):
        """
        Substitute environment variables in YAML configs after CrewAI loads them.
        Supports ${VAR_NAME} or ${VAR_NAME:default} syntax in YAML values.
        
        This allows agents.yaml to use ${LLM_MODEL:gpt-4o-mini} which will be replaced
        with the value from the LLM_MODEL environment variable (or the default).
        """
        def substitute_dict(d: dict) -> dict:
            """Recursively substitute environment variables in dict values."""
            result = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    result[key] = substitute_dict(value)
                elif isinstance(value, list):
                    result[key] = [
                        substitute_dict(item) if isinstance(item, dict) 
                        else self._substitute_env_var(item) if isinstance(item, str) 
                        else item
                        for item in value
                    ]
                elif isinstance(value, str):
                    result[key] = self._substitute_env_var(value)
                else:
                    result[key] = value
            return result
        
        # Process agents_config (CrewAI loads YAML files into dicts after super().__init__())
        if isinstance(self.agents_config, dict):
            self.agents_config = substitute_dict(self.agents_config)
            logger.debug(f"[CONFIG] Substituted env vars in agents_config ({len(self.agents_config)} agents)")
        elif isinstance(self.agents_config, str):
            # If still a string (file path), CrewAI hasn't loaded it yet - will be handled lazily
            logger.debug(f"[CONFIG] agents_config is still a file path, will substitute when accessed")
        
        # Process tasks_config (though tasks don't have llm, we support it for consistency)
        if isinstance(self.tasks_config, dict):
            self.tasks_config = substitute_dict(self.tasks_config)
            logger.debug(f"[CONFIG] Substituted env vars in tasks_config")
        elif isinstance(self.tasks_config, str):
            logger.debug(f"[CONFIG] tasks_config is still a file path, will substitute when accessed")
    
    def _substitute_env_var(self, value: str) -> str:
        """
        Substitute environment variable placeholders in a string.
        Supports ${VAR_NAME} or ${VAR_NAME:default} syntax.
        """
        import re
        # Pattern: ${VAR_NAME} or ${VAR_NAME:default_value}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) else None
            env_value = os.getenv(var_name, default)
            return env_value if env_value is not None else match.group(0)  # Keep original if not found
        
        return re.sub(pattern, replace, value)
    
    def _create_agent(self, agent_name: str, description: str = "") -> Agent:
        """
        Helper method to create an agent from configuration.
        LLM model is substituted from environment variable when accessed.

        Args:
            agent_name: Name of the agent (must match agents.yaml key)
            description: Optional description for logging

        Returns:
            Initialized Agent instance
        """
        log_desc = f" ({description})" if description else ""
        logger.info(f"[AGENT] Initializing: {agent_name}{log_desc}")
        try:
            # Ensure env vars are substituted before accessing config
            if not hasattr(self, 'llm_model'):
                self.llm_model = os.getenv("LLM_MODEL", os.getenv("RESUME_BUILDER_LLM", "gpt-4o-mini"))
            
            # Try to substitute env vars if configs are loaded
            try:
                self._substitute_env_vars_in_configs()
            except (AttributeError, TypeError):
                # Configs might not be loaded yet, that's okay
                pass
            
            config = self.agents_config[agent_name].copy()
            # Substitute env vars in this specific config if not already done
            if isinstance(config.get("llm"), str) and "${" in config.get("llm", ""):
                config["llm"] = self._substitute_env_var(config["llm"])
            
            # LLM model is already substituted from ${LLM_MODEL} in YAML
            model = config.get("llm", self.llm_model)
            agent = Agent(config=config, verbose=True)
            logger.info(f"[AGENT] Successfully initialized: {agent_name} (model: {model})")
            return agent
        except Exception as e:
            logger.error(f"[AGENT] Failed to initialize {agent_name}: {e}")
            raise
    
    def _create_task(self, task_name: str) -> Task:
        """
        Helper method to create a task from configuration.
        
        Args:
            task_name: Name of the task (must match tasks.yaml key)
        
        Returns:
            Initialized Task instance
        """
        logger.info(f"[TASK] Initializing: {task_name}")
        try:
            task = Task(config=self.tasks_config[task_name])
            logger.info(f"[TASK] Successfully initialized: {task_name}")
            return task
        except Exception as e:
            logger.error(f"[TASK] Failed to initialize {task_name}: {e}")
            raise

    # ---------------- Tool Registration (for YAML references) -------------
    @tool
    def profile_reader(self):
        """Read and parse user profile data"""
        return ProfileReaderTool()

    @tool
    def privacy_guard_tool(self):
        """Scan content for privacy violations"""
        return PrivacyGuardTool()
    
    @tool
    def latex_package_checker(self):
        """Check LaTeX template for missing packages"""
        return LaTeXPackageCheckerTool()
    
    @tool
    def tex_info_extractor(self):
        """Extract information from TeX files"""
        return TexInfoExtractorTool()
    
    @tool
    def progress_reporter(self):
        """Report progress updates during execution"""
        return ProgressReporterTool()
    
    @tool
    def read_latex_file(self):
        """Read a LaTeX file and return its contents for analysis"""
        return ReadLatexFileTool()
    
    @tool
    def write_latex_file(self):
        """Write LaTeX content to a file"""
        return WriteLatexFileTool()
    
    @tool
    def preflight_check(self):
        """Verify LaTeX engine exists and output directories are writable"""
        return PreflightTool()
    
    @tool
    def ats_rules_audit(self):
        """Run deterministic ATS checks on LaTeX file"""
        return ATSRulesTool()
    
    @tool
    def read_json_file(self):
        """Read a JSON file and return its parsed contents"""
        return ReadJsonFileTool()
    
    @tool
    def write_json_file(self):
        """Write data to a JSON file"""
        return WriteJsonFileTool()
    
    @tool
    def pdf_comparison_tool(self):
        """Compare two PDFs and return structured diff report"""
        return PdfComparisonTool()
    
    @tool
    def latex_structure_analyzer(self):
        """Analyze LaTeX structure, sections, and commands"""
        return LaTeXStructureAnalyzerTool()
    
    @tool
    def latex_compile_pdf(self):
        """Compile LaTeX file to PDF"""
        return LatexCompileTool()

    # ---------------- Agents (names must match agents.yaml) ----------------
    # NOTE: profile_validator, template_validator, file_collector, preflight_sentinel, 
    # ats_auditor, latex_resume_cleaner are archived - replaced by deterministic Python functions
    # See agents_archived.yaml for their definitions
    
    @agent
    def jd_analyst(self) -> Agent:
        return self._create_agent("jd_analyst")

    # === CONTENT SELECTION AGENTS ===
    @agent
    def experience_selector(self) -> Agent:
        return self._create_agent("experience_selector")

    @agent
    def project_selector(self) -> Agent:
        return self._create_agent("project_selector")

    @agent
    def skill_selector(self) -> Agent:
        return self._create_agent("skill_selector")

    # === CONTENT WRITING AGENTS ===
    @agent
    def header_writer(self) -> Agent:
        return self._create_agent("header_writer")
    
    @agent
    def summary_writer(self) -> Agent:
        return self._create_agent("summary_writer")

    @agent
    def education_writer(self) -> Agent:
        return self._create_agent("education_writer")

    # === QUALITY AGENTS ===
    @agent
    def ats_checker(self) -> Agent:
        return self._create_agent("ats_checker")

    @agent
    def privacy_guard(self) -> Agent:
        return self._create_agent("privacy_guard")

    @agent
    def pipeline_orchestrator(self) -> Agent:
        """Pipeline orchestrator - kept for LaTeX adjustments via UI."""
        return self._create_agent("pipeline_orchestrator", "for adjustments only")
    
    @agent
    def template_fixer(self) -> Agent:
        """LaTeX Template Visual Matching Specialist"""
        return self._create_agent("template_fixer")
    
    @agent
    def coverletter_generator(self) -> Agent:
        return self._create_agent("coverletter_generator")

    # ---------------- Tasks (names must match tasks.yaml) ------------------
    # NOTE: profile_validation_task, collect_file_info_task, template_validation_task,
    # pipeline_orchestration_task are archived - replaced by deterministic Python functions
    # See tasks_archived.yaml for their definitions
    
    @task
    def parse_job_description_task(self) -> Task:
        return self._create_task("parse_job_description_task")

    # === CONTENT SELECTION TASKS ===
    @task
    def select_experiences_task(self) -> Task:
        return self._create_task("select_experiences_task")

    @task
    def select_projects_task(self) -> Task:
        return self._create_task("select_projects_task")

    @task
    def select_skills_task(self) -> Task:
        return self._create_task("select_skills_task")

    # === CONTENT WRITING TASKS ===
    @task
    def write_header_task(self) -> Task:
        return self._create_task("write_header_task")
    
    @task
    def write_summary_task(self) -> Task:
        return self._create_task("write_summary_task")
    
    @task
    def write_education_section_task(self) -> Task:
        return self._create_task("write_education_section_task")

    # === QUALITY & COVER LETTER TASKS ===
    @task
    def ats_check_task(self) -> Task:
        return self._create_task("ats_check_task")

    @task
    def privacy_validation_task(self) -> Task:
        return self._create_task("privacy_validation_task")

    @task
    def write_cover_letter_task(self) -> Task:
        return self._create_task("write_cover_letter_task")
    
    @task
    def fix_template_to_match_reference_task(self) -> Task:
        """Template matching task - fixes LaTeX to match reference PDF visually."""
        return self._create_task("fix_template_to_match_reference_task")
    
    # NOTE: pipeline_orchestration_task is archived - replaced by deterministic_pipeline.compute_pipeline_status()
    # See tasks_archived.yaml for its definition
    #
    # NOTE: latex_repair_task, latex_final_edit_task, ats_rules_audit_task, and preflight_task
    # are archived - not used in current pipeline. See tasks_archived.yaml for their definitions.

    # ---------------- Crew assembly ---------------------------------------
    @crew
    def crew(self) -> Crew:
        # Enable tracing if configured (set CREWAI_TRACING=true in .env or environment)
        enable_tracing = os.getenv("CREWAI_TRACING", "false").lower() in ("true", "1", "yes")
        
        # Speed optimization: reduce verbose logging (adds overhead)
        verbose_mode = os.getenv("CREWAI_VERBOSE", "false").lower() in ("true", "1", "yes")
        
        # Get conditional flags from inputs (passed via kickoff)
        # These will be available when crew.kickoff(inputs=...) is called
        # For now, we'll filter in the kickoff wrapper, but we can also check here if inputs are available
        
        # Filter out deterministic tasks - these are now handled by Python functions
        # Deterministic tasks: preflight_task, profile_validation_task, collect_file_info_task,
        # template_validation_task, pipeline_orchestration_task
        # Also filter out fix_template_to_match_reference_task - it's only used in run_template_matching
        # and requires template variables not available in the main pipeline inputs
        excluded_task_keys = {
            "preflight_task",
            "profile_validation_task",
            "collect_file_info_task",
            "template_validation_task",
            "pipeline_orchestration_task",
            "fix_template_to_match_reference_task"
        }
        
        # Filter tasks by checking their config key or description
        final_tasks = []
        for task in self.tasks:
            # Check if this task should be excluded
            should_exclude = False
            try:
                # First, try to check by task key (if available)
                task_key = getattr(task, '_key', None)
                if task_key and task_key in excluded_task_keys:
                    should_exclude = True
                
                # Also check description for markers (this is a reliable fallback)
                if not should_exclude and hasattr(task, 'description'):
                    desc = str(task.description)
                    # Check for DETERMINISTIC marker or preflight
                    if 'DETERMINISTIC' in desc or 'preflight' in desc.lower():
                        should_exclude = True
                    # Check for template matching task by looking for its unique template variables
                    elif '{reference_pdf_path}' in desc and '{generated_pdf_path}' in desc:
                        should_exclude = True
            except Exception:
                pass
            
            if not should_exclude:
                final_tasks.append(task)
        
        # Fallback: if filtering failed, use all tasks (will be slower but still works)
        if not final_tasks:
            logger.warning("Task filtering failed, using all tasks (excluded tasks will be skipped by agents)")
            final_tasks = self.tasks
        else:
            logger.info(f"Filtered out {len(self.tasks) - len(final_tasks)} excluded tasks, {len(final_tasks)} tasks remaining")
        
        # Use manager_llm instead of manager_agent because:
        # 1. Manager agents cannot have tools (CrewAI requirement)
        # 2. The orchestrator needs tools (read_json_file, write_json_file, progress_reporter) to execute its task
        # 3. By using manager_llm, we keep the orchestrator as a regular agent with tools
        # 4. The manager_llm coordinates task execution, while the orchestrator executes its own task
        # 
        # NOTE: The orchestrator task is now handled by Python (compute_pipeline_status),
        # but we keep the agent definition for potential future use (e.g., adjustments)
        manager_llm = self.llm_model  # Use same LLM model from environment variable
        
        # Apply fast mode optimizations if enabled
        fast_mode = getattr(self, 'fast_mode', False)
        if fast_mode:
            max_iter_value = 2  # Reduced iterations for faster execution
            max_execution_time_value = 600  # 10 minutes
            logger.info("[FAST MODE] Applying speed optimizations: max_iter=2, max_execution_time=600s")
        else:
            max_iter_value = 3  # Default: Maximum number of iterations/retries
            max_execution_time_value = 900  # Default: 15 minutes
        
        # Build Crew with parameters - check which parameters are supported
        crew_params = {
            "agents": self.agents,
            "tasks": final_tasks,  # Only non-deterministic tasks
            "process": Process.hierarchical,  # Enables parallel execution where dependencies allow
            "manager_llm": manager_llm,  # Use LLM-based manager
            "memory": False,  # Disabled for speed
            "verbose": verbose_mode,  # Only verbose if explicitly enabled (reduces logging overhead)
            "tracing": enable_tracing,  # Enable tracing for debugging (requires CrewAI AMP account)
        }
        
        # Add max_iter and max_execution_time if supported by CrewAI version
        # These may not be available in all CrewAI versions
        try:
            import inspect
            crew_sig = inspect.signature(Crew.__init__)
            if 'max_iter' in crew_sig.parameters:
                crew_params['max_iter'] = max_iter_value
            if 'max_execution_time' in crew_sig.parameters:
                crew_params['max_execution_time'] = max_execution_time_value
        except Exception:
            # If inspection fails, try adding them anyway - CrewAI will ignore unsupported params
            crew_params['max_iter'] = max_iter_value
            crew_params['max_execution_time'] = max_execution_time_value
        
        return Crew(**crew_params)
