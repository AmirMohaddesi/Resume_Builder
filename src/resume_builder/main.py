#!/usr/bin/env python
"""
Resume Builder main entry point with streamlined UI.
Simplified version for better user experience.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import traceback

# Load .env once
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Import ResumeTeam; allow running as package or script
try:
    from resume_builder.crew import ResumeTeam
    from resume_builder.logger import init_logger, get_logger
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from crew import ResumeTeam  # type: ignore
    from logger import init_logger, get_logger  # type: ignore

# ---------- Paths & defaults ----------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = OUTPUT_DIR / "logs"

# Initialize logging
_logger = init_logger(LOG_DIR, log_level=os.getenv("LOG_LEVEL", "INFO"))

DEFAULT_TEMPLATE_PATH = Path(
    os.getenv("TEMPLATE_PATH", PROJECT_ROOT / "src" / "resume_builder" / "templates" / "main.tex")
)
DEFAULT_PROFILE_PATH = Path(
    os.getenv("PROFILE_PATH", PROJECT_ROOT / "src" / "resume_builder" / "data" / "profile.json")
)

FINAL_PDF = OUTPUT_DIR / "final_resume.pdf"
PDF_REVIEW_JSON = OUTPUT_DIR / "pdf_review_report.json"


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline(jd_text: str, profile_path: Optional[str], custom_template_path: Optional[str] = None, reference_pdf_paths: Optional[list] = None, progress_callback=None) -> Tuple[Optional[str], str]:
    """
    Run the full resume generation pipeline.
    
    Args:
        jd_text: Job description text
        profile_path: Path to user profile JSON
        custom_template_path: Optional custom LaTeX template path
        reference_pdf_paths: Optional list of reference PDF paths for style matching
    
    Returns:
        Tuple of (pdf_path, status_message)
    """
    _ensure_output_dir()
    logger = get_logger()
    
    if not jd_text or not jd_text.strip():
        return None, "[error] Job description cannot be empty."
    
    # Use provided profile path or default
    if profile_path is None:
        profile_path = str(DEFAULT_PROFILE_PATH)
    
    profile_path_obj = Path(profile_path)
    if not profile_path_obj.exists():
        return None, f"[error] Profile not found at: {profile_path}"
    
    # Use provided template or default
    if custom_template_path:
        template_path = Path(custom_template_path)
        if not template_path.exists():
            logger.warning(f"Custom template not found: {custom_template_path}, using default")
            template_path = DEFAULT_TEMPLATE_PATH
    else:
        template_path = DEFAULT_TEMPLATE_PATH
    
    # Detect mode based on provided files
    mode = "standard"
    has_reference_pdfs = reference_pdf_paths and len(reference_pdf_paths) > 0
    
    if custom_template_path and has_reference_pdfs:
        mode = "custom_with_reference"
    elif custom_template_path:
        mode = "custom_template"
    elif has_reference_pdfs:
        mode = "with_reference"
    
    logger.info("="*80)
    logger.info(f"Starting resume generation pipeline at {datetime.now()}")
    logger.info(f"Mode: {mode}")
    logger.info(f"Profile: {profile_path}")
    logger.info(f"Template: {template_path}")
    if custom_template_path:
        logger.info(f"Custom template: {custom_template_path}")
    if has_reference_pdfs:
        logger.info(f"Reference PDFs: {len(reference_pdf_paths)} file(s)")
        for i, pdf_path in enumerate(reference_pdf_paths, 1):
            logger.info(f"  - PDF {i}: {pdf_path}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("="*80)
    
    # Create crew instance
    try:
        team = ResumeTeam()
    except Exception as e:
        logger.error(f"Failed to create ResumeTeam: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] Failed to initialize crew: {str(e)}"
    
    # Prepare inputs
    inputs = {
        "job_description": jd_text,
        "profile_path": str(profile_path),
        "template_path": str(template_path),
        "mode": mode,
        "has_custom_template": custom_template_path is not None,
        "has_reference_pdfs": has_reference_pdfs,
        "reference_pdf_count": len(reference_pdf_paths) if has_reference_pdfs else 0
    }
    
    if has_reference_pdfs:
        inputs["reference_pdf_paths"] = reference_pdf_paths
    
    # Execute crew (agents output JSON, no LaTeX yet)
    try:
        logger.info("Launching crew...")
        if progress_callback:
            progress_callback(0.2, desc="AI agents analyzing job description and profile...")
        result = team.crew().kickoff(inputs=inputs)
        logger.info(f"Crew execution completed")
        logger.info(f"Result type: {type(result)}")
        if progress_callback:
            progress_callback(0.6, desc="AI agents completed analysis. Generating LaTeX...")
        
    except Exception as e:
        logger.error(f"Crew execution failed: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] Crew execution failed:\n{str(e)}\n\n{traceback.format_exc()}"
    
    # Check template validation results
    template_warnings = []
    template_validation_path = OUTPUT_DIR / "template_validation.json"
    if template_validation_path.exists():
        try:
            import json
            with open(template_validation_path, 'r') as f:
                validation_data = json.load(f)
                if validation_data.get("status") == "warning":
                    missing_pkgs = validation_data.get("missing_packages", [])
                    if missing_pkgs:
                        pkg_names = [p.get("package", "unknown") for p in missing_pkgs]
                        template_warnings.append(f"⚠️ Missing LaTeX packages: {', '.join(pkg_names)}")
                        if validation_data.get("recommendation"):
                            template_warnings.append(f"📦 {validation_data['recommendation']}")
                    logger.warning(f"Template validation warnings: {template_warnings}")
        except Exception as e:
            logger.warning(f"Could not read template validation: {e}")
    
    # Step 2: Generate LaTeX using Python builder (no agents involved)
    try:
        logger.info("="*80)
        logger.info("Building LaTeX resume from JSON data...")
        logger.info("="*80)
        if progress_callback:
            progress_callback(0.7, desc="Building LaTeX resume from AI-generated content...")
        
        from resume_builder.latex_builder import build_resume_from_json_files
        import json
        
        # Load JSON outputs from agents
        identity_json = OUTPUT_DIR / "user_profile.json"
        summary_json = OUTPUT_DIR / "summary_block.json"
        experience_json = OUTPUT_DIR / "selected_experiences.json"
        education_json = OUTPUT_DIR / "education_block.json"
        skills_json = OUTPUT_DIR / "selected_skills.json"
        projects_json = OUTPUT_DIR / "selected_projects.json"
        rendered_tex = OUTPUT_DIR / "rendered_resume.tex"
        
        # Verify all required files exist
        missing_files = []
        for file_path in [identity_json, summary_json, experience_json, education_json, skills_json]:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            logger.error(f"Missing required JSON files: {missing_files}")
            return None, f"[error] Agent output files missing: {', '.join(missing_files)}"
        
        # Build LaTeX using Python
        latex_content = build_resume_from_json_files(
            identity_path=identity_json,
            summary_path=summary_json,
            experience_path=experience_json,
            education_path=education_json,
            skills_path=skills_json,
            projects_path=projects_json if projects_json.exists() else None,
            template_path=template_path,
            output_path=rendered_tex
        )
        
        logger.info(f"✅ LaTeX generated: {rendered_tex}")
        
    except Exception as e:
        logger.error(f"LaTeX generation failed: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] LaTeX generation failed:\n{str(e)}\n\n{traceback.format_exc()}"
    
    # Step 3: Compile LaTeX to PDF
    try:
        logger.info("="*80)
        logger.info("Compiling LaTeX to PDF...")
        logger.info("="*80)
        if progress_callback:
            progress_callback(0.85, desc="Compiling LaTeX to PDF...")
        
        from resume_builder.tools.latex_compile import LatexCompileTool
        
        compiler = LatexCompileTool()
        compile_result = compiler._run(
            tex_path=str(rendered_tex),
            out_name="final_resume.pdf",
            workdir=".",
            engine="pdflatex"
        )
        
        logger.info(f"Compilation result: {compile_result}")
        
        # Check if PDF was created
        if FINAL_PDF.exists():
            pdf_size = FINAL_PDF.stat().st_size
            logger.info(f"✅ PDF generated successfully: {FINAL_PDF} ({pdf_size} bytes)")
            if progress_callback:
                progress_callback(0.95, desc="✅ PDF compiled successfully!")
            
            # Build success message with warnings if any
            success_msg = f"[success] Resume generated successfully!\n\nMode: {mode}\nOutput: {FINAL_PDF}\n"
            
            if has_reference_pdfs:
                success_msg += f"\n📄 {len(reference_pdf_paths)} reference PDF(s) analyzed for style insights\n"
            
            if template_warnings:
                success_msg += "\n⚠️ TEMPLATE WARNINGS:\n" + "\n".join(template_warnings)
                success_msg += "\n\nThe resume was generated but may have compilation issues in other LaTeX environments."
            
            # Return absolute path to PDF
            pdf_absolute_path = str(FINAL_PDF.resolve())
            return pdf_absolute_path, success_msg
        else:
            logger.error("Compilation finished but no PDF was found")
            return None, f"[error] PDF compilation failed. Check compile.log for details.\n\nCompiler output: {compile_result}"
    
    except Exception as e:
        logger.error(f"PDF compilation failed: {e}")
        logger.error(traceback.format_exc())
        return None, f"[error] PDF compilation failed:\n{str(e)}\n\n{traceback.format_exc()}"


# ---------- Gradio UI ----------
def build_ui():
    """Build streamlined UI."""
    import gradio as gr
    import json
    
    # Import profile builder
    try:
        from resume_builder.profile_builder import (
            build_profile_from_upload,
            build_profile_from_form,
            save_profile,
            load_profile_template,
        )
        PROFILE_BUILDER_AVAILABLE = True
        template = load_profile_template()
    except ImportError:
        PROFILE_BUILDER_AVAILABLE = False
        template = {}
    
    with gr.Blocks(
        title="AI Resume Builder",
        theme=gr.themes.Default(primary_hue="sky")
    ) as demo:
        gr.Markdown("""
        # 🚀 AI Resume Builder
        
        Generate tailored resumes for any job description using AI.
        """)
        
        # Section 1: Upload Files
        gr.Markdown("## 📄 Step 1: Upload Your Files")
        gr.Markdown("""
        Upload any combination of files:
        - **Your resume** (.pdf, .docx, .doc, .txt) - AI will parse and extract your information
        - **Custom LaTeX template** (.tex) - AI will validate packages
        - **Reference PDFs** (.pdf) - AI will analyze for style matching
        """)
        
        files_upload = gr.File(
            label="Upload Files - Drag & drop or click to select multiple files",
            file_types=[".pdf", ".docx", ".doc", ".txt", ".tex"],
            file_count="multiple",
            type="filepath"
        )
        upload_status = gr.Textbox(label="Upload Status", interactive=False, lines=3, max_lines=10, show_label=False)
        
        # Section 2: Review Profile
        gr.Markdown("---")
        gr.Markdown("## ✏️ Step 2: Review & Edit Your Profile")
        
        with gr.Row():
            with gr.Column():
                first_name = gr.Textbox(label="First Name *", lines=1, max_lines=1)
                last_name = gr.Textbox(label="Last Name *", lines=1, max_lines=1)
                title = gr.Textbox(label="Job Title", lines=1, max_lines=2)
                email = gr.Textbox(label="Email *", type="email", lines=1, max_lines=1)
                phone = gr.Textbox(label="Phone", lines=1, max_lines=1)
            
            with gr.Column():
                website = gr.Textbox(label="Website/Portfolio", lines=1, max_lines=1)
                linkedin = gr.Textbox(label="LinkedIn", lines=1, max_lines=1)
                github = gr.Textbox(label="GitHub", visible=False, lines=1, max_lines=1)
        
        # Dynamic fields container
        gr.Markdown("### 🔗 Additional Links")
        dynamic_links_state = gr.State(value={})  # Store dynamic fields
        
        with gr.Column() as dynamic_fields_container:
            # These will be populated dynamically
            dynamic_field_1 = gr.Textbox(label="", visible=False, lines=1, max_lines=1)
            dynamic_field_2 = gr.Textbox(label="", visible=False, lines=1, max_lines=1)
            dynamic_field_3 = gr.Textbox(label="", visible=False, lines=1, max_lines=1)
            dynamic_field_4 = gr.Textbox(label="", visible=False, lines=1, max_lines=1)
            dynamic_field_5 = gr.Textbox(label="", visible=False, lines=1, max_lines=1)
        
        with gr.Row():
            add_field_btn = gr.Button("➕ Add Custom Link", size="sm")
            new_field_name = gr.Textbox(label="Field Name", placeholder="e.g., Google Scholar, Twitter", scale=2, visible=False, lines=1, max_lines=1)
            new_field_value = gr.Textbox(label="URL", placeholder="https://...", scale=3, visible=False, lines=1, max_lines=1)
            save_new_field_btn = gr.Button("Save", size="sm", visible=False)
        
        with gr.Accordion("📋 Work Experience (JSON)", open=False):
            experience_json = gr.Textbox(
                label="Experience",
                value="[]",
                lines=6,
                max_lines=20,
                placeholder="[]",
                show_label=False
            )
        
        with gr.Accordion("🎓 Education (JSON)", open=False):
            education_json = gr.Textbox(
                label="Education",
                value="[]",
                lines=4,
                max_lines=15,
                placeholder="[]",
                show_label=False
            )
        
        with gr.Accordion("💡 Skills", open=False):
            skills_text = gr.Textbox(
                label="Skills (one per line or comma-separated)",
                placeholder="Python, JavaScript, React...",
                lines=3,
                max_lines=15,
                show_label=False
            )
        
        with gr.Accordion("🚀 Projects (JSON)", open=False):
            projects_json = gr.Textbox(
                label="Projects",
                value="[]",
                lines=4,
                max_lines=15,
                placeholder="[]",
                show_label=False
            )
        
        with gr.Accordion("🏆 Awards", open=False):
            awards_text = gr.Textbox(
                label="Awards (one per line)", 
                lines=2,
                max_lines=10,
                show_label=False
            )
        
        
        # Section 3: Generate Resume
        gr.Markdown("---")
        gr.Markdown("## 🎯 Step 3: Generate Your Tailored Resume")
        
        jd_text = gr.Textbox(
            label="Job Description *",
            lines=12,
            max_lines=30,
            placeholder="Paste the full job description here...",
            show_copy_button=True,
        )
        
        generate_btn = gr.Button("🚀 Generate Resume", variant="primary", size="lg")
        
        with gr.Row():
            pdf_file = gr.File(label="📄 Resume PDF", interactive=False)
            tex_file = gr.File(label="📝 LaTeX Source", interactive=False)
        
        status = gr.Textbox(label="Generation Status", lines=8, max_lines=20)
        
        # Event handlers
        def handle_files_upload_combined(files):
            if not files:
                return {
                    first_name: "", last_name: "", title: "", email: "", phone: "",
                    website: "", linkedin: "", github: gr.update(visible=False),
                    experience_json: "[]", education_json: "[]", skills_text: "",
                    projects_json: "[]", awards_text: "",
                    dynamic_field_1: gr.update(visible=False), 
                    dynamic_field_2: gr.update(visible=False),
                    dynamic_field_3: gr.update(visible=False),
                    dynamic_field_4: gr.update(visible=False),
                    dynamic_field_5: gr.update(visible=False),
                    dynamic_links_state: {},
                    upload_status: ""
                }
            
            # Separate files by type
            resume_file = None
            tex_file = None
            tex_count = 0
            pdf_count = 0
            resume_count = 0
            
            for file_path in files:
                file_ext = Path(file_path).suffix.lower()
                if file_ext in ['.docx', '.doc', '.txt']:
                    if resume_file is None:
                        resume_file = file_path
                    resume_count += 1
                elif file_ext == '.tex':
                    if tex_file is None:
                        tex_file = file_path
                    tex_count += 1
                elif file_ext == '.pdf':
                    if resume_file is None:
                        resume_file = file_path
                        resume_count += 1
                    else:
                        pdf_count += 1
            
            # Build status message
            status_parts = []
            if resume_count > 0:
                status_parts.append(f"📄 {resume_count} resume file(s) detected")
            if tex_count > 0:
                status_parts.append(f"✅ {tex_count} LaTeX template(s) - AI will validate packages")
            if pdf_count > 0:
                status_parts.append(f"✅ {pdf_count} PDF(s) - Will be analyzed as references")
            
            # Parse resume
            profile = None
            if PROFILE_BUILDER_AVAILABLE and resume_file:
                try:
                    profile, msg = build_profile_from_upload(resume_file)
                    if profile:
                        status_parts.insert(0, "✅ Resume parsed successfully!")
                    else:
                        status_parts.insert(0, f"⚠️ Failed to parse resume: {msg}")
                except Exception as e:
                    status_parts.insert(0, f"⚠️ Error parsing resume: {str(e)}")
            elif not PROFILE_BUILDER_AVAILABLE and resume_count > 0:
                status_parts.insert(0, "❌ Profile builder not available for resume parsing")
            
            # Extract info from .tex file if available
            if tex_file:
                try:
                    from resume_builder.tools.tex_info_extractor import TexInfoExtractorTool
                    tool = TexInfoExtractorTool()
                    tex_result = tool._run(tex_file)
                    tex_data = json.loads(tex_result)
                    tex_identity = tex_data.get("identity", {})
                    
                    # Merge .tex info into profile
                    if profile:
                        identity = profile.get("identity", {})
                        if not identity.get("website") and tex_identity.get("website"):
                            identity["website"] = tex_identity["website"]
                        if not identity.get("linkedin") and tex_identity.get("linkedin"):
                            identity["linkedin"] = tex_identity["linkedin"]
                        if not identity.get("github") and tex_identity.get("github"):
                            identity["github"] = tex_identity["github"]
                        
                        # Save merged profile
                        save_profile(profile)
                        status_parts.insert(1, "🔗 Links extracted from .tex file!")
                except Exception as e:
                    status_parts.append(f"⚠️ Could not extract from .tex: {str(e)}")
            
            # Build output
            if profile:
                # Auto-save profile after parsing (silent, no path shown to user)
                save_profile(profile)
                identity = profile.get("identity", {})
                
                # Detect dynamic fields
                dynamic_fields = {}
                dynamic_updates = []
                field_idx = 1
                
                # Check for GitHub
                github_val = identity.get("github", "")
                github_visible = bool(github_val)
                
                # Check for other URLs from .tex
                if tex_file:
                    other_urls = tex_data.get("other_urls", [])
                    for url in other_urls[:5]:  # Max 5 additional fields
                        if "scholar.google.com" in url:
                            dynamic_fields[f"field_{field_idx}"] = {"label": "Google Scholar", "value": url}
                            field_idx += 1
                        elif "twitter.com" in url or "x.com" in url:
                            dynamic_fields[f"field_{field_idx}"] = {"label": "Twitter/X", "value": url}
                            field_idx += 1
                        elif field_idx <= 5:
                            # Generic URL
                            dynamic_fields[f"field_{field_idx}"] = {"label": f"Link {field_idx}", "value": url}
                            field_idx += 1
                
                # Build dynamic field updates
                for i in range(1, 6):
                    if f"field_{i}" in dynamic_fields:
                        field_data = dynamic_fields[f"field_{i}"]
                        dynamic_updates.append(gr.update(
                            label=field_data["label"],
                            value=field_data["value"],
                            visible=True
                        ))
                    else:
                        dynamic_updates.append(gr.update(visible=False))
                
                return {
                    first_name: identity.get("first", ""),
                    last_name: identity.get("last", ""),
                    title: identity.get("title", ""),
                    email: identity.get("email", ""),
                    phone: identity.get("phone", ""),
                    website: identity.get("website", ""),
                    linkedin: identity.get("linkedin", ""),
                    github: gr.update(value=github_val, visible=github_visible),
                    experience_json: json.dumps(profile.get("experience", []), indent=2),
                    education_json: json.dumps(identity.get("education", []), indent=2),
                    skills_text: "\n".join(profile.get("skills", [])),
                    projects_json: json.dumps(profile.get("projects", []), indent=2),
                    awards_text: "\n".join(profile.get("awards", [])),
                    dynamic_field_1: dynamic_updates[0],
                    dynamic_field_2: dynamic_updates[1],
                    dynamic_field_3: dynamic_updates[2],
                    dynamic_field_4: dynamic_updates[3],
                    dynamic_field_5: dynamic_updates[4],
                    dynamic_links_state: dynamic_fields,
                    upload_status: "\n".join(status_parts)
                }
            else:
                return {
                    first_name: "", last_name: "", title: "", email: "", phone: "",
                    website: "", linkedin: "", github: gr.update(visible=False),
                    experience_json: "[]", education_json: "[]", skills_text: "",
                    projects_json: "[]", awards_text: "",
                    dynamic_field_1: gr.update(visible=False),
                    dynamic_field_2: gr.update(visible=False),
                    dynamic_field_3: gr.update(visible=False),
                    dynamic_field_4: gr.update(visible=False),
                    dynamic_field_5: gr.update(visible=False),
                    dynamic_links_state: {},
                    upload_status: "\n".join(status_parts)
                }
        
        # Automatic parsing on file upload (triggered when files are selected)
        files_upload.change(
            handle_files_upload_combined,
            inputs=[files_upload],
            outputs=[first_name, last_name, title, email, phone, website, linkedin, github,
                    experience_json, education_json, skills_text, projects_json, awards_text,
                    dynamic_field_1, dynamic_field_2, dynamic_field_3, dynamic_field_4, dynamic_field_5,
                    dynamic_links_state, upload_status]
        )
        
        # Add custom field button handlers
        def show_add_field_form():
            return {
                new_field_name: gr.update(visible=True),
                new_field_value: gr.update(visible=True),
                save_new_field_btn: gr.update(visible=True)
            }
        
        def save_custom_field(field_name, field_url, current_state):
            if not field_name or not field_url:
                return {
                    new_field_name: gr.update(value="", visible=False),
                    new_field_value: gr.update(value="", visible=False),
                    save_new_field_btn: gr.update(visible=False),
                    dynamic_links_state: current_state
                }
            
            # Find first available slot
            updates = []
            for i in range(1, 6):
                if f"field_{i}" not in current_state:
                    current_state[f"field_{i}"] = {"label": field_name, "value": field_url}
                    break
            
            # Update UI
            for i in range(1, 6):
                if f"field_{i}" in current_state:
                    field_data = current_state[f"field_{i}"]
                    updates.append(gr.update(
                        label=field_data["label"],
                        value=field_data["value"],
                        visible=True
                    ))
                else:
                    updates.append(gr.update(visible=False))
            
            return {
                dynamic_field_1: updates[0],
                dynamic_field_2: updates[1],
                dynamic_field_3: updates[2],
                dynamic_field_4: updates[3],
                dynamic_field_5: updates[4],
                new_field_name: gr.update(value="", visible=False),
                new_field_value: gr.update(value="", visible=False),
                save_new_field_btn: gr.update(visible=False),
                dynamic_links_state: current_state
            }
        
        add_field_btn.click(
            show_add_field_form,
            outputs=[new_field_name, new_field_value, save_new_field_btn]
        )
        
        save_new_field_btn.click(
            save_custom_field,
            inputs=[new_field_name, new_field_value, dynamic_links_state],
            outputs=[dynamic_field_1, dynamic_field_2, dynamic_field_3, dynamic_field_4, dynamic_field_5,
                    new_field_name, new_field_value, save_new_field_btn, dynamic_links_state]
        )
        
        def auto_save_profile(first, last, title_val, email_val, phone_val, 
                              website_val, linkedin_val, github_val,
                              exp_json, edu_json, skills, proj_json, awards,
                              dyn_field_1, dyn_field_2, dyn_field_3, dyn_field_4, dyn_field_5,
                              dyn_state):
            """Auto-save profile when fields change (silent, no UI feedback)."""
            if not PROFILE_BUILDER_AVAILABLE:
                return
            
            # Only save if we have at least a name
            if not (first.strip() or last.strip()):
                return
            
            try:
                # Merge dynamic fields with their values
                additional_links = {}
                if dyn_state:
                    for field_id, field_info in dyn_state.items():
                        additional_links[field_id] = field_info
                
                profile, _ = build_profile_from_form(
                    first, last, title_val, email_val, phone_val,
                    website_val, linkedin_val, github_val,
                    exp_json, edu_json, skills, proj_json, awards,
                    additional_links
                )
                if profile:
                    save_profile(profile)
            except Exception:
                pass  # Silent failure for auto-save
        
        # Auto-save profile when any field changes
        # Use a debounced approach - save after user stops typing
        all_profile_inputs = [
            first_name, last_name, title, email, phone, website, linkedin, github,
            experience_json, education_json, skills_text, projects_json, awards_text,
            dynamic_field_1, dynamic_field_2, dynamic_field_3, dynamic_field_4, dynamic_field_5,
            dynamic_links_state
        ]
        
        # Attach auto-save to all profile fields
        for field in all_profile_inputs:
            if hasattr(field, 'change'):
                field.change(
                    auto_save_profile,
                    inputs=all_profile_inputs,
                    outputs=[],
                    show_progress=False
                )
        
        async def handle_generate(jd, uploaded_files, progress=gr.Progress()):
            if not jd.strip():
                return None, None, "❌ Please paste a job description."
            
            import shutil
            
            progress(0.05, desc="Processing uploaded files...")
            
            # Separate uploaded files by type
            custom_template_path = None
            reference_pdfs = []
            
            if uploaded_files:
                for file_path in uploaded_files:
                    try:
                        uploaded_path = Path(file_path)
                        if not uploaded_path.exists():
                            continue
                        
                        file_ext = uploaded_path.suffix.lower()
                        
                        if file_ext == '.tex':
                            # Use the first .tex file as the main template
                            if custom_template_path is None:
                                custom_template_path = OUTPUT_DIR / "custom_template.tex"
                                shutil.copy2(uploaded_path, custom_template_path)
                                _logger.info(f"Custom template uploaded: {custom_template_path}")
                        
                        elif file_ext == '.pdf':
                            # Copy all PDFs with numbered names
                            pdf_num = len(reference_pdfs) + 1
                            dest_path = OUTPUT_DIR / f"reference_resume_{pdf_num}.pdf"
                            shutil.copy2(uploaded_path, dest_path)
                            reference_pdfs.append(str(dest_path))
                            _logger.info(f"Reference PDF {pdf_num} uploaded: {dest_path}")
                    
                    except Exception as e:
                        _logger.warning(f"Error processing file {file_path}: {e}")
            
            # Use saved profile
            profile_path = OUTPUT_DIR / "user_profile.json"
            if not profile_path.exists():
                profile_path = DEFAULT_PROFILE_PATH
            
            progress(0.1, desc="Initializing AI agents...")
            
            # Create a progress callback function that can be used in run_pipeline
            def update_progress(step: float, desc: str):
                """Update progress from within run_pipeline"""
                try:
                    progress(step, desc=desc)
                except Exception:
                    pass  # Ignore progress update errors
            
            # Run pipeline with list of PDFs and progress callback
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Wrap run_pipeline to accept progress callback
            def run_with_progress():
                return run_pipeline(
                    jd,
                    str(profile_path),
                    str(custom_template_path) if custom_template_path else None,
                    reference_pdfs if reference_pdfs else None,
                    progress_callback=update_progress
                )
            
            pdf_path, msg = await loop.run_in_executor(None, run_with_progress)
            
            progress(0.95, desc="Finalizing...")
            
            # Check if PDF was actually generated
            if pdf_path and Path(pdf_path).exists():
                progress(1.0, desc="✅ Complete! PDF generated successfully.")
            else:
                progress(1.0, desc="⚠️ Pipeline completed but PDF not generated. Check status message.")
            
            tex_path = OUTPUT_DIR / "rendered_resume.tex"
            tex_file_path = str(tex_path) if tex_path.exists() else None
            
            return pdf_path, tex_file_path, msg
        
        generate_btn.click(
            handle_generate,
            inputs=[jd_text, files_upload],
            outputs=[pdf_file, tex_file, status]
        )
        
        demo.css = ".gradio-container { max-width: 1200px !important; }"
    
    return demo


def run_ui():
    demo = build_ui()
    demo.queue()
    port = int(os.getenv("GRADIO_SERVER_PORT") or os.getenv("PORT") or "7860")
    demo.launch(server_name="127.0.0.1", server_port=port, inbrowser=True)


def run() -> None:
    """CrewAI CLI entrypoint."""
    jd_path = PROJECT_ROOT / "job_description.txt"
    if not jd_path.exists():
        example = PROJECT_ROOT / "job_description.example.txt"
        jd_text = example.read_text(encoding="utf-8") if example.exists() else ""
    else:
        jd_text = jd_path.read_text(encoding="utf-8")

    pdf_path, msg = run_pipeline(jd_text=jd_text, profile_path=None)
    print(msg)
    if pdf_path:
        print(f"PDF: {pdf_path}")


def run_crew() -> int:
    """Console entry used by `crewai run`."""
    run_ui()
    return 0


if __name__ == "__main__":
    run_ui()

