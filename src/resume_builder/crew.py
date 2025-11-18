# crew.py - Register tools so CrewAI can load them from YAML
from __future__ import annotations
import logging
import os

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
# LLM-powered intelligent tools
from resume_builder.tools.project_summarizer import ProjectSummarizerTool
from resume_builder.tools.summary_editor import SummaryEditorTool
from resume_builder.tools.cover_letter_editor import CoverLetterEditorTool
from resume_builder.tools.latex_error_analyzer import LatexErrorAnalyzerTool
from resume_builder.tools.content_validator import ContentValidatorTool
from resume_builder.tools.latex_package_recommendation import LatexPackageRecommendationTool
from resume_builder.tools.content_rank_analyzer import ContentRankAnalyzerTool


@CrewBase
class ResumeTeam:
    """Simplified crew for resume generation: parse → select → write → analyze."""

    # CrewAI will load these YAMLs as dicts
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    
    def __init__(
        self,
        fast_mode: bool = False,
        enable_cover_letter: bool = True,
        enable_ats: bool = True,
        enable_privacy: bool = True,
        *args,
        **kwargs
    ):
        """Initialize ResumeTeam.
        
        Args:
            fast_mode: Enable fast mode optimizations
            enable_cover_letter: Include cover letter generation tasks
            enable_ats: Include ATS check task
            enable_privacy: Include privacy validation task
        """
        # Don't call super().__init__() - CrewBase handles initialization differently
        self.fast_mode = fast_mode
        self.enable_cover_letter = enable_cover_letter
        self.enable_ats = enable_ats
        self.enable_privacy = enable_privacy

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
    
    # ---------------- LLM-Powered Intelligent Tools ----------------
    @tool
    def project_summarizer(self):
        """Intelligently summarize project bullet points"""
        return ProjectSummarizerTool()
    
    @tool
    def summary_editor(self):
        """Refine and shorten summary text"""
        return SummaryEditorTool()
    
    @tool
    def cover_letter_editor(self):
        """Refine and shorten cover letter"""
        return CoverLetterEditorTool()
    
    @tool
    def latex_error_analyzer(self):
        """Analyze LaTeX compilation errors and suggest fixes"""
        return LatexErrorAnalyzerTool()
    
    @tool
    def content_validator(self):
        """Validate resume content for factuality and privacy"""
        return ContentValidatorTool()
    
    @tool
    def latex_package_recommendation(self):
        """Recommend missing LaTeX packages and fixes"""
        return LatexPackageRecommendationTool()
    
    @tool
    def design_error_checker(self):
        """Check for known design errors before generating content"""
        from resume_builder.tools.design_error_checker import DesignErrorCheckerTool
        return DesignErrorCheckerTool()
    
    @tool
    def content_rank_analyzer(self):
        """Analyze resume content and rank items by importance, suggest removals"""
        return ContentRankAnalyzerTool()
    
    @tool
    def latex_gap_analyzer(self):
        """Analyze LaTeX source to detect gaps, excessive whitespace, and removable sections"""
        from resume_builder.tools.latex_gap_analyzer import LaTeXGapAnalyzerTool
        return LaTeXGapAnalyzerTool()
    
    @tool
    def content_removal_tool(self):
        """Remove specific content from JSON files to reduce resume length"""
        from resume_builder.tools.content_removal_tool import ContentRemovalTool
        return ContentRemovalTool()

    # ---------------- Agents (names must match agents.yaml) ----------------
    # NOTE: profile_validator, template_validator, file_collector, preflight_sentinel, 
    # ats_auditor, latex_resume_cleaner are archived - replaced by deterministic Python functions
    # See agents_archived.yaml for their definitions
    
    @agent
    def jd_analyst(self) -> Agent:
        return Agent(config=self.agents_config["jd_analyst"], verbose=True)

    # === CONTENT SELECTION AGENTS ===
    @agent
    def experience_selector(self) -> Agent:
        return Agent(config=self.agents_config["experience_selector"], verbose=True)

    @agent
    def project_selector(self) -> Agent:
        return Agent(config=self.agents_config["project_selector"], verbose=True)

    @agent
    def skill_selector(self) -> Agent:
        return Agent(config=self.agents_config["skill_selector"], verbose=True)

    # === CONTENT WRITING AGENTS ===
    @agent
    def header_writer(self) -> Agent:
        return Agent(config=self.agents_config["header_writer"], verbose=True)
    
    @agent
    def summary_creator(self) -> Agent:
        return Agent(config=self.agents_config["summary_creator"], verbose=True)
    
    @agent
    def summary_refiner(self) -> Agent:
        return Agent(config=self.agents_config["summary_refiner"], verbose=True)

    @agent
    def education_writer(self) -> Agent:
        return Agent(config=self.agents_config["education_writer"], verbose=True)

    # === QUALITY AGENTS ===
    @agent
    def ats_checker(self) -> Agent:
        return Agent(config=self.agents_config["ats_checker"], verbose=True)

    @agent
    def privacy_guard(self) -> Agent:
        return Agent(config=self.agents_config["privacy_guard"], verbose=True)

    @agent
    def pipeline_orchestrator(self) -> Agent:
        """Pipeline orchestrator - kept for LaTeX adjustments via UI."""
        return Agent(config=self.agents_config["pipeline_orchestrator"], verbose=True)
    
    @agent
    def template_fixer(self) -> Agent:
        """LaTeX Template Visual Matching Specialist (DEBUG-ONLY)"""
        return Agent(config=self.agents_config["template_fixer"], verbose=True)
    
    @agent
    def cover_letter_creator(self) -> Agent:
        return Agent(config=self.agents_config["cover_letter_creator"], verbose=True)
    
    @agent
    def cover_letter_refiner(self) -> Agent:
        return Agent(config=self.agents_config["cover_letter_refiner"], verbose=True)

    # ---------------- Tasks (names must match tasks.yaml) ------------------
    # NOTE: profile_validation_task, collect_file_info_task, template_validation_task,
    # pipeline_orchestration_task are archived - replaced by deterministic Python functions
    # See tasks_archived.yaml for their definitions
    
    @task
    def parse_job_description_task(self) -> Task:
        return Task(config=self.tasks_config["parse_job_description_task"])

    # === CONTENT SELECTION TASKS ===
    @task
    def select_experiences_task(self) -> Task:
        config = self.tasks_config["select_experiences_task"]
        config = self._apply_design_error_prevention("select_experiences_task", config)
        optimized_config = self._apply_fast_mode_optimizations("select_experiences_task", config)
        return Task(config=optimized_config)
    
    @task
    def select_projects_task(self) -> Task:
        config = self.tasks_config["select_projects_task"]
        config = self._apply_design_error_prevention("select_projects_task", config)
        optimized_config = self._apply_fast_mode_optimizations("select_projects_task", config)
        return Task(config=optimized_config)
    
    @task
    def select_skills_task(self) -> Task:
        config = self.tasks_config["select_skills_task"]
        config = self._apply_design_error_prevention("select_skills_task", config)
        optimized_config = self._apply_fast_mode_optimizations("select_skills_task", config)
        return Task(config=optimized_config)

    # === CONTENT WRITING TASKS ===
    @task
    def write_header_task(self) -> Task:
        config = self.tasks_config["write_header_task"]
        config = self._apply_design_error_prevention("write_header_task", config)
        optimized_config = self._apply_fast_mode_optimizations("write_header_task", config)
        return Task(config=optimized_config)
    
    @task
    def write_summary_task(self) -> Task:
        config = self.tasks_config["write_summary_task"]
        config = self._apply_design_error_prevention("write_summary_task", config)
        optimized_config = self._apply_fast_mode_optimizations("write_summary_task", config)
        return Task(config=optimized_config)
    
    @task
    def write_education_section_task(self) -> Task:
        config = self.tasks_config["write_education_section_task"]
        config = self._apply_design_error_prevention("write_education_section_task", config)
        optimized_config = self._apply_fast_mode_optimizations("write_education_section_task", config)
        return Task(config=optimized_config)

    # === QUALITY & COVER LETTER TASKS ===
    @task
    def ats_check_task(self) -> Task:
        return Task(config=self.tasks_config["ats_check_task"])

    @task
    def privacy_validation_task(self) -> Task:
        return Task(config=self.tasks_config["privacy_validation_task"])

    @task
    def write_cover_letter_task(self) -> Task:
        return Task(config=self.tasks_config["write_cover_letter_task"])
    
    # ---------------- Refinement Tasks (LLM-Powered) ----------------
    @task
    def refine_summary_task(self) -> Task:
        """Refine summary using LLM-powered summary_editor tool."""
        return Task(config=self.tasks_config["refine_summary_task"])
    
    @task
    def refine_cover_letter_task(self) -> Task:
        """Refine cover letter using LLM-powered cover_letter_editor tool."""
        return Task(config=self.tasks_config["refine_cover_letter_task"])
    
    @task
    def analyze_latex_errors_task(self) -> Task:
        """Analyze LaTeX compilation errors using LLM-powered latex_error_analyzer tool."""
        return Task(config=self.tasks_config["analyze_latex_errors_task"])
    
    @task
    def fix_template_to_match_reference_task(self) -> Task:
        """Template matching task - fixes LaTeX to match reference PDF visually."""
        return Task(config=self.tasks_config["fix_template_to_match_reference_task"])
    
    # NOTE: pipeline_orchestration_task is archived - replaced by deterministic_pipeline.compute_pipeline_status()
    # See tasks_archived.yaml for its definition
    #
    # NOTE: latex_repair_task, latex_final_edit_task, ats_rules_audit_task, and preflight_task
    # are archived - not used in current pipeline. See tasks_archived.yaml for their definitions.

    def _apply_fast_mode_optimizations(self, task_name: str, task_config: dict) -> dict:
        """Apply fast mode optimizations to a task config.
        
        In fast mode:
        - Reduces prompt sizes (truncates JD/profile)
        - Adds instructions to skip refinement loops
        - Adds single-pass instructions
        """
        if not self.fast_mode:
            return task_config
        
        # Create a copy to avoid modifying original
        optimized_config = task_config.copy()
        
        # Modify description to include fast mode instructions
        description = optimized_config.get("description", "")
        
        # Add fast mode instructions based on task type
        if task_name == "write_summary_task":
            # In fast mode, write_summary_task should produce final summary (no refinement)
            description = description.replace(
                "Do NOT call summary_editor tool - you are creating, not refining.",
                "FAST MODE: Write the final summary directly (2-3 sentences, ≤90 words). Do NOT use summary_editor tool - produce the final version in one pass."
            )
        elif task_name in ["select_experiences_task", "select_projects_task", "select_skills_task"]:
            # Single-pass selection tasks
            description = description + "\n\nFAST MODE: Produce final selection in one pass. Do NOT iterate or refine."
        elif task_name == "write_header_task":
            description = description + "\n\nFAST MODE: Write header in one pass. Do NOT iterate."
        elif task_name == "write_education_section_task":
            description = description + "\n\nFAST MODE: Write education section in one pass. Do NOT iterate."
        
        optimized_config["description"] = description
        
        return optimized_config
    
    def _apply_design_error_prevention(self, task_name: str, task_config: dict) -> dict:
        """Apply design error prevention guidance to a task config.
        
        Adds warnings about known design errors to prevent recurring issues.
        """
        try:
            from resume_builder.design_error_memory import get_prevention_guidance
            
            # Map task names to contexts
            task_context_map = {
                "write_header_task": "header",
                "write_summary_task": "summary",
                "select_experiences_task": "experience",
                "select_projects_task": "projects",
                "select_skills_task": "skills",
                "write_education_section_task": "education",
            }
            
            context = task_context_map.get(task_name)
            if not context:
                return task_config
            
            # Get prevention guidance for this context
            guidance = get_prevention_guidance(context)
            if guidance:
                # Create a copy to avoid modifying original
                optimized_config = task_config.copy()
                description = optimized_config.get("description", "")
                
                # Add prevention guidance at the beginning
                description = f"{guidance}\n\n{description}"
                optimized_config["description"] = description
                
                logger.debug(f"Added design error prevention to {task_name}: {guidance[:50]}...")
                return optimized_config
            
        except Exception as e:
            logger.debug(f"Failed to apply design error prevention: {e}")
        
        return task_config
    
    # ---------------- Crew assembly ---------------------------------------
    @crew
    def crew(self) -> Crew:
        """Main resume pipeline crew.
        
        Builds filtered task list BEFORE constructing Crew based on enable flags.
        """
        enable_tracing = os.getenv("CREWAI_TRACING", "false").lower() in ("true", "1", "yes")
        verbose_mode = os.getenv("CREWAI_VERBOSE", "false").lower() in ("true", "1", "yes")
        fast_mode = getattr(self, 'fast_mode', False)
        enable_cover_letter = getattr(self, 'enable_cover_letter', True)
        enable_ats = getattr(self, 'enable_ats', True)
        enable_privacy = getattr(self, 'enable_privacy', True)
        
        # Build filtered task list BEFORE constructing Crew
        # Core tasks (always included)
        filtered_tasks = [
            self.parse_job_description_task(),
            self.select_experiences_task(),
            self.select_projects_task(),
            self.select_skills_task(),
            self.write_header_task(),
            self.write_summary_task(),
            self.write_education_section_task(),
        ]
        
        # Optional tasks based on flags
        if enable_ats:
            filtered_tasks.append(self.ats_check_task())
        
        if enable_privacy:
            filtered_tasks.append(self.privacy_validation_task())
        
        if enable_cover_letter:
            filtered_tasks.append(self.write_cover_letter_task())
            if not fast_mode:  # Skip refinement in fast mode
                filtered_tasks.append(self.refine_cover_letter_task())
            logger.info("Cover letter tasks ENABLED: write_cover_letter_task" + (", refine_cover_letter_task" if not fast_mode else " (refinement skipped in fast mode)"))
        else:
            logger.info("Cover letter tasks DISABLED (UI checkbox unchecked) - skipping write_cover_letter_task and refine_cover_letter_task")
        
        # Refinement tasks - skip in fast mode for speed
        if not fast_mode:
            filtered_tasks.append(self.refine_summary_task())
            filtered_tasks.append(self.analyze_latex_errors_task())
            logger.info("Refinement tasks ENABLED: refine_summary_task, analyze_latex_errors_task")
        else:
            logger.info("FAST MODE: Skipping refine_summary_task and analyze_latex_errors_task for speed")
        
        # Optional template matching task (not typically used in normal runs)
        # filtered_tasks.append(self.fix_template_to_match_reference_task())
        
        logger.info(f"Task filtering: {len(filtered_tasks)} tasks (CoverLetter={enable_cover_letter}, ATS={enable_ats}, Privacy={enable_privacy})")
        
        # 3) Get LLM model from first agent's config (all agents use same model)
        manager_llm = self.agents_config.get(list(self.agents_config.keys())[0], {}).get("llm", "gpt-4o-mini")
        
        # 4) Apply fast mode optimizations if enabled
        if fast_mode:
            max_iter_value = 2
            max_execution_time_value = 600
        else:
            max_iter_value = 3
            max_execution_time_value = 900
        
        # 5) Build Crew with filtered tasks (BEFORE construction)
        crew_params = {
            "agents": self.agents,
            "tasks": filtered_tasks,  # Use filtered list, not self.tasks
            "process": Process.hierarchical,
            "manager_llm": manager_llm,
            "memory": False,
            "verbose": verbose_mode,
            "tracing": enable_tracing,
        }
        
        # Add max_iter and max_execution_time if supported by CrewAI version
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
