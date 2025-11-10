# crew.py - Register tools so CrewAI can load them from YAML
from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, tool

# Import tools
from resume_builder.tools.privacy_guard import PrivacyGuardTool
from resume_builder.tools.profile_reader import ProfileReaderTool
from resume_builder.tools.latex_package_checker import LaTeXPackageCheckerTool
from resume_builder.tools.tex_info_extractor import TexInfoExtractorTool


@CrewBase
class ResumeTeam:
    """Simplified crew for resume generation: parse → select → write → analyze."""

    # CrewAI will load these YAMLs as dicts
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

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

    # ---------------- Agents (names must match agents.yaml) ----------------
    @agent
    def profile_validator(self) -> Agent:
        return Agent(config=self.agents_config["profile_validator"], verbose=True)

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
    def summary_writer(self) -> Agent:
        return Agent(config=self.agents_config["summary_writer"], verbose=True)

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
    def planner(self) -> Agent:
        return Agent(config=self.agents_config["planner"], verbose=True)
    
    @agent
    def template_validator(self) -> Agent:
        return Agent(config=self.agents_config["template_validator"], verbose=True)
    
    @agent
    def file_collector(self) -> Agent:
        return Agent(config=self.agents_config["file_collector"], verbose=True)

    # ---------------- Tasks (names must match tasks.yaml) ------------------
    @task
    def profile_validation_task(self) -> Task:
        return Task(config=self.tasks_config["profile_validation_task"])
    
    @task
    def collect_file_info_task(self) -> Task:
        return Task(config=self.tasks_config["collect_file_info_task"])

    @task
    def parse_job_description_task(self) -> Task:
        return Task(config=self.tasks_config["parse_job_description_task"])

    # === CONTENT SELECTION TASKS ===
    @task
    def select_experiences_task(self) -> Task:
        return Task(config=self.tasks_config["select_experiences_task"])

    @task
    def select_projects_task(self) -> Task:
        return Task(config=self.tasks_config["select_projects_task"])

    @task
    def select_skills_task(self) -> Task:
        return Task(config=self.tasks_config["select_skills_task"])

    # === CONTENT WRITING TASKS ===
    @task
    def write_summary_task(self) -> Task:
        return Task(config=self.tasks_config["write_summary_task"])

    @task
    def write_education_section_task(self) -> Task:
        return Task(config=self.tasks_config["write_education_section_task"])

    # === QUALITY & COMPILATION TASKS ===
    @task
    def template_validation_task(self) -> Task:
        return Task(config=self.tasks_config["template_validation_task"])
    
    @task
    def ats_check_task(self) -> Task:
        return Task(config=self.tasks_config["ats_check_task"])

    @task
    def privacy_validation_task(self) -> Task:
        return Task(config=self.tasks_config["privacy_validation_task"])

    @task
    def tailor_plan_task(self) -> Task:
        return Task(config=self.tasks_config["tailor_plan_task"])

    # ---------------- Crew assembly ---------------------------------------
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=False,  # Disabled for speed
            verbose=True,
            max_iter=15,  # Increased to allow tool calls + processing
            max_execution_time=180,  # 3 minute timeout
        )
