"""
Gradio UI for the Resume Builder.

This module contains all UI-related code, including:
- Gradio interface construction
- UI event handlers
- File upload processing
- Profile management
- PDF preview generation
"""

from __future__ import annotations

import os
import json
import shutil
import asyncio
import queue
import base64
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# Import paths and constants
from resume_builder.paths import (
    PROJECT_ROOT, OUTPUT_DIR, GENERATED_DIR, LOG_DIR, TEMPLATES, ensure_dirs
)
from resume_builder.logger import get_logger

# Import orchestration functions
from resume_builder.orchestration import run_pipeline

# Path constants
FINAL_PDF = GENERATED_DIR / "final_resume.pdf"
RENDERED_TEX = GENERATED_DIR / "rendered_resume.tex"
COVER_LETTER_PDF = GENERATED_DIR / "cover_letter.pdf"
COVER_LETTER_TEX = GENERATED_DIR / "cover_letter.tex"

# Default paths
DEFAULT_TEMPLATE_PATH = Path(
    os.getenv("TEMPLATE_PATH", TEMPLATES / "main.tex")
)
DEFAULT_PROFILE_PATH = Path(
    os.getenv("PROFILE_PATH", PROJECT_ROOT / "src" / "resume_builder" / "data" / "profile.json")
)

logger = get_logger()


def build_ui():
    """Build streamlined UI."""
    import gradio as gr
    
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
            # These will be populated dynamically with remove buttons
            with gr.Row(visible=False) as dynamic_row_1:
                dynamic_field_1 = gr.Textbox(label="", scale=4, lines=1, max_lines=1)
                remove_field_1 = gr.Button("🗑️ Remove", size="sm", scale=1, min_width=100)
            with gr.Row(visible=False) as dynamic_row_2:
                dynamic_field_2 = gr.Textbox(label="", scale=4, lines=1, max_lines=1)
                remove_field_2 = gr.Button("🗑️ Remove", size="sm", scale=1, min_width=100)
            with gr.Row(visible=False) as dynamic_row_3:
                dynamic_field_3 = gr.Textbox(label="", scale=4, lines=1, max_lines=1)
                remove_field_3 = gr.Button("🗑️ Remove", size="sm", scale=1, min_width=100)
            with gr.Row(visible=False) as dynamic_row_4:
                dynamic_field_4 = gr.Textbox(label="", scale=4, lines=1, max_lines=1)
                remove_field_4 = gr.Button("🗑️ Remove", size="sm", scale=1, min_width=100)
            with gr.Row(visible=False) as dynamic_row_5:
                dynamic_field_5 = gr.Textbox(label="", scale=4, lines=1, max_lines=1)
                remove_field_5 = gr.Button("🗑️ Remove", size="sm", scale=1, min_width=100)
        
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
        
        with gr.Row():
            debug_mode = gr.Checkbox(
                label="🐛 Debug Mode",
                value=False,
                info="Enable debug mode to generate detailed orchestration trace (pipeline_status_debug.json)"
            )
            fast_mode = gr.Checkbox(
                label="⚡ Fast Mode",
                value=False,
                info="Optimize for speed: reduces retries and execution time limits (may reduce quality)"
            )
        
        with gr.Row():
            enable_ats = gr.Checkbox(
                label="✅ ATS Check",
                value=True,
                info="Run ATS compatibility analysis (can be disabled for faster execution)"
            )
            enable_privacy = gr.Checkbox(
                label="🔒 Privacy Validation",
                value=True,
                info="Check for sensitive data like SSN, passport numbers (can be disabled for faster execution)"
            )
        
        with gr.Row():
            generate_btn = gr.Button("🚀 Generate Resume", variant="primary", size="lg", interactive=False)
            generate_btn_info = gr.Markdown("⚠️ Please upload and parse a resume first", visible=True, elem_classes=["button-info"])
        
        # Progress status with increased height
        progress_status = gr.Textbox(
            label="Status", 
            value="Ready to generate...", 
            interactive=False, 
            lines=6, 
            max_lines=12,
            min_width=600
        )
        
        # Task timing display (only shown in debug mode)
        task_timing_display = gr.HTML(
            label="⏱️ Task Execution Times",
            visible=False,  # Hidden by default, only shown in debug mode
            value="<div style='padding: 10px; text-align: center; color: #666;'>Timing information will appear here during generation...</div>"
        )
        
        # Download files (hidden until ready)
        with gr.Row(visible=False) as download_section:
            with gr.Column(scale=2):
                # Tabbed PDF viewer for Resume and Cover Letter
                with gr.Tabs() as pdf_tabs:
                    with gr.Tab("📄 Resume", id="resume_tab"):
                        pdf_preview = gr.HTML(label="Resume Preview", visible=True, value="<div style='padding: 20px; text-align: center; color: #666;'>Resume will appear here after generation...</div>")
                    with gr.Tab("📧 Cover Letter", id="cover_letter_tab"):
                        cover_letter_preview = gr.HTML(label="Cover Letter Preview", visible=True, value="<div style='padding: 20px; text-align: center; color: #666;'>Cover letter will appear here after generation...</div>")
                
                # Download buttons
                with gr.Row():
                    pdf_file = gr.File(label="📥 Download Resume PDF", interactive=False, visible=True)
                    cover_letter_file = gr.File(label="📥 Download Cover Letter PDF", interactive=False, visible=False)
            with gr.Column(scale=1):
                tex_file = gr.File(label="📝 LaTeX Source", interactive=False)
        
        # Chat interface for adjustments (hidden until PDF is generated)
        with gr.Column(visible=False) as adjustment_chat_section:
            gr.Markdown("---")
            gr.Markdown("## 💬 Request Adjustments")
            gr.Markdown("Ask the orchestrator to make adjustments to your resume or cover letter.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    adjustment_document = gr.Radio(
                        choices=["Resume", "Cover Letter"],
                        value="Resume",
                        label="📄 Document to Adjust",
                        info="Select which document you want to modify"
                    )
                with gr.Column(scale=2):
                    adjustment_status = gr.Textbox(
                        label="⚙️ Status", 
                        value="Ready to process adjustments...",
                        interactive=False, 
                        lines=2,
                        show_label=True
                    )
            
            adjustment_chat = gr.Chatbot(
                label="💬 Chat with Orchestrator",
                height=450,
                show_label=True,
                show_copy_button=True,
                avatar_images=(None, "🤖")
            )
            
            with gr.Row():
                adjustment_input = gr.Textbox(
                    label="Your Request",
                    placeholder="Example: 'Add a newline after the summary section' or 'Fix the spacing in the experience section' or 'Make the cover letter opening more engaging'",
                    lines=3,
                    scale=4
                )
                adjustment_btn = gr.Button("📤 Send Request", variant="primary", scale=1, size="lg")
        
        status = gr.Textbox(label="Generation Status", lines=8, max_lines=20, visible=False)
        
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
                
                # Build dynamic field updates (with rows)
                row_updates = []
                field_updates = []
                for i in range(1, 6):
                    if f"field_{i}" in dynamic_fields:
                        field_data = dynamic_fields[f"field_{i}"]
                        row_updates.append(gr.update(visible=True))
                        field_updates.append(gr.update(
                            label=field_data["label"],
                            value=field_data["value"]
                        ))
                    else:
                        row_updates.append(gr.update(visible=False))
                        field_updates.append(gr.update(value="", label=""))
                
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
                    dynamic_row_1: row_updates[0],
                    dynamic_field_1: field_updates[0],
                    dynamic_row_2: row_updates[1],
                    dynamic_field_2: field_updates[1],
                    dynamic_row_3: row_updates[2],
                    dynamic_field_3: field_updates[2],
                    dynamic_row_4: row_updates[3],
                    dynamic_field_4: field_updates[3],
                    dynamic_row_5: row_updates[4],
                    dynamic_field_5: field_updates[4],
                    dynamic_links_state: dynamic_fields,
                    upload_status: "\n".join(status_parts)
                }
            else:
                return {
                    first_name: "", last_name: "", title: "", email: "", phone: "",
                    website: "", linkedin: "", github: gr.update(visible=False),
                    experience_json: "[]", education_json: "[]", skills_text: "",
                    projects_json: "[]", awards_text: "",
                    dynamic_row_1: gr.update(visible=False),
                    dynamic_field_1: gr.update(value="", label=""),
                    dynamic_row_2: gr.update(visible=False),
                    dynamic_field_2: gr.update(value="", label=""),
                    dynamic_row_3: gr.update(visible=False),
                    dynamic_field_3: gr.update(value="", label=""),
                    dynamic_row_4: gr.update(visible=False),
                    dynamic_field_4: gr.update(value="", label=""),
                    dynamic_row_5: gr.update(visible=False),
                    dynamic_field_5: gr.update(value="", label=""),
                    dynamic_links_state: {},
                    upload_status: "\n".join(status_parts)
                }
        
        # Automatic parsing on file upload (triggered when files are selected)
        def handle_files_upload_with_button_state(files):
            """Handle file upload and update button state."""
            result = handle_files_upload_combined(files)
            # Check if resume was parsed successfully - get upload_status value from dict
            upload_status_text = ""
            if upload_status in result:
                upload_status_text = result[upload_status]
            resume_parsed = "✅ Resume parsed successfully!" in str(upload_status_text)
            # Convert dict to list in correct output order - access values directly
            return [
                result.get(first_name, ""),
                result.get(last_name, ""),
                result.get(title, ""),
                result.get(email, ""),
                result.get(phone, ""),
                result.get(website, ""),
                result.get(linkedin, ""),
                result.get(github, gr.update(visible=False)),
                result.get(experience_json, "[]"),
                result.get(education_json, "[]"),
                result.get(skills_text, ""),
                result.get(projects_json, "[]"),
                result.get(awards_text, ""),
                result.get(dynamic_row_1, gr.update(visible=False)),
                result.get(dynamic_field_1, gr.update(visible=False)),
                result.get(dynamic_row_2, gr.update(visible=False)),
                result.get(dynamic_field_2, gr.update(visible=False)),
                result.get(dynamic_row_3, gr.update(visible=False)),
                result.get(dynamic_field_3, gr.update(visible=False)),
                result.get(dynamic_row_4, gr.update(visible=False)),
                result.get(dynamic_field_4, gr.update(visible=False)),
                result.get(dynamic_row_5, gr.update(visible=False)),
                result.get(dynamic_field_5, gr.update(visible=False)),
                result.get(dynamic_links_state, {}),
                result.get(upload_status, ""),
                gr.update(interactive=resume_parsed),  # generate_btn
                gr.update(visible=not resume_parsed, value="⚠️ Please upload and parse a resume first" if not resume_parsed else "")  # generate_btn_info
            ]
        
        files_upload.change(
            handle_files_upload_with_button_state,
            inputs=[files_upload],
            outputs=[first_name, last_name, title, email, phone, website, linkedin, github,
                    experience_json, education_json, skills_text, projects_json, awards_text,
                    dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5,
                    dynamic_links_state, upload_status, generate_btn, generate_btn_info]
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
            for i in range(1, 6):
                if f"field_{i}" not in current_state:
                    current_state[f"field_{i}"] = {"label": field_name, "value": field_url}
                    break
            
            # Update UI with rows
            row_updates = []
            field_updates = []
            for i in range(1, 6):
                if f"field_{i}" in current_state:
                    field_data = current_state[f"field_{i}"]
                    row_updates.append(gr.update(visible=True))
                    field_updates.append(gr.update(
                        label=field_data["label"],
                        value=field_data["value"]
                    ))
                else:
                    row_updates.append(gr.update(visible=False))
                    field_updates.append(gr.update(value="", label=""))
            
            return {
                dynamic_row_1: row_updates[0],
                dynamic_field_1: field_updates[0],
                dynamic_row_2: row_updates[1],
                dynamic_field_2: field_updates[1],
                dynamic_row_3: row_updates[2],
                dynamic_field_3: field_updates[2],
                dynamic_row_4: row_updates[3],
                dynamic_field_4: field_updates[3],
                dynamic_row_5: row_updates[4],
                dynamic_field_5: field_updates[4],
                new_field_name: gr.update(value="", visible=False),
                new_field_value: gr.update(value="", visible=False),
                save_new_field_btn: gr.update(visible=False),
                dynamic_links_state: current_state
            }
        
        def remove_dynamic_field(field_num, current_state):
            """Remove a dynamic field by its number (1-5)"""
            field_key = f"field_{field_num}"
            if field_key in current_state:
                del current_state[field_key]
            
            # Rebuild UI state
            row_updates = []
            field_updates = []
            for i in range(1, 6):
                if f"field_{i}" in current_state:
                    field_data = current_state[f"field_{i}"]
                    row_updates.append(gr.update(visible=True))
                    field_updates.append(gr.update(
                        label=field_data["label"],
                        value=field_data["value"]
                    ))
                else:
                    row_updates.append(gr.update(visible=False))
                    field_updates.append(gr.update(value="", label=""))
            
            return {
                dynamic_row_1: row_updates[0],
                dynamic_field_1: field_updates[0],
                dynamic_row_2: row_updates[1],
                dynamic_field_2: field_updates[1],
                dynamic_row_3: row_updates[2],
                dynamic_field_3: field_updates[2],
                dynamic_row_4: row_updates[3],
                dynamic_field_4: field_updates[3],
                dynamic_row_5: row_updates[4],
                dynamic_field_5: field_updates[4],
                dynamic_links_state: current_state
            }
        
        add_field_btn.click(
            show_add_field_form,
            outputs=[new_field_name, new_field_value, save_new_field_btn]
        )
        
        save_new_field_btn.click(
            save_custom_field,
            inputs=[new_field_name, new_field_value, dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5,
                    new_field_name, new_field_value, save_new_field_btn, dynamic_links_state]
        )
        
        # Remove button handlers
        remove_field_1.click(
            lambda state: remove_dynamic_field(1, state),
            inputs=[dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5, dynamic_links_state]
        )
        remove_field_2.click(
            lambda state: remove_dynamic_field(2, state),
            inputs=[dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5, dynamic_links_state]
        )
        remove_field_3.click(
            lambda state: remove_dynamic_field(3, state),
            inputs=[dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5, dynamic_links_state]
        )
        remove_field_4.click(
            lambda state: remove_dynamic_field(4, state),
            inputs=[dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5, dynamic_links_state]
        )
        remove_field_5.click(
            lambda state: remove_dynamic_field(5, state),
            inputs=[dynamic_links_state],
            outputs=[dynamic_row_1, dynamic_field_1, dynamic_row_2, dynamic_field_2,
                    dynamic_row_3, dynamic_field_3, dynamic_row_4, dynamic_field_4,
                    dynamic_row_5, dynamic_field_5, dynamic_links_state]
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
        
        # Also trigger auto-save when fields are removed
        for remove_btn in [remove_field_1, remove_field_2, remove_field_3, remove_field_4, remove_field_5]:
            remove_btn.click(
                auto_save_profile,
                inputs=all_profile_inputs,
                outputs=[],
                show_progress=False
            )
        
        # Attach auto-save to all profile fields
        for field in all_profile_inputs:
            if hasattr(field, 'change'):
                field.change(
                    auto_save_profile,
                    inputs=all_profile_inputs,
                    outputs=[],
                    show_progress=False
                )
        
        async def handle_generate(jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy, progress=gr.Progress()):
            if not jd.strip():
                yield {
                    progress_status: gr.update(value="❌ Please paste a job description."),
                    download_section: gr.update(visible=False),
                    adjustment_chat_section: gr.update(visible=False),
                    task_timing_display: gr.update(visible=False, value=""),
                    pdf_preview: "",
                    pdf_file: None,
                    tex_file: None,
                    status: gr.update(value="❌ Please paste a job description.", visible=True)
                }
                return
            
            # Initialize progress bar and status - ensure it's visible from the start
            try:
                progress(0.0, desc="Starting resume generation...")
            except Exception:
                pass  # Progress bar might not be available, continue anyway
            
            yield {
                progress_status: gr.update(value="Starting resume generation..."),
                download_section: gr.update(visible=False),
                adjustment_chat_section: gr.update(visible=False),
                task_timing_display: gr.update(visible=debug, value="<div style='padding: 10px; text-align: center; color: #666;'>⏳ Collecting timing information...</div>"),
                pdf_preview: "",
                status: gr.update(visible=False)
            }
            
            try:
                progress(0.02, desc="Processing uploaded files...")
            except Exception:
                pass
            yield {
                progress_status: gr.update(value="Processing uploaded files...")
            }
            
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
                                logger.info(f"Custom template uploaded: {custom_template_path}")
                        
                        elif file_ext == '.pdf':
                            # Copy all PDFs with numbered names
                            pdf_num = len(reference_pdfs) + 1
                            dest_path = OUTPUT_DIR / f"reference_resume_{pdf_num}.pdf"
                            shutil.copy2(uploaded_path, dest_path)
                            reference_pdfs.append(str(dest_path))
                            logger.info(f"Reference PDF {pdf_num} uploaded: {dest_path}")
                    
                    except Exception as e:
                        logger.warning(f"Error processing file {file_path}: {e}")
            
            # Use saved profile from output/ if it exists, otherwise use default
            # Note: user_profile.json in output/ is preserved by _clean_json_files()
            # because it can be an input file from previous runs
            saved_profile = OUTPUT_DIR / "user_profile.json"
            if saved_profile.exists():
                profile_path = str(saved_profile)
                logger.info(f"Using saved profile from output: {profile_path}")
            else:
                profile_path = str(DEFAULT_PROFILE_PATH)
                logger.info(f"Using default profile: {profile_path}")
            
            try:
                progress(0.05, desc="Initializing AI agents...")
            except Exception:
                pass
            yield {
                progress_status: gr.update(value="Initializing AI agents...")
            }
            
            # Create a progress callback that uses asyncio to update from background thread
            progress_queue = queue.Queue()
            status_queue = queue.Queue()
            
            def update_progress(step: float, desc: str):
                """Update progress from within run_pipeline - puts update in queue"""
                try:
                    progress_queue.put((step, desc), block=False)
                    status_queue.put(desc, block=False)
                except Exception:
                    pass  # Ignore queue errors
            
            # Start async progress monitor with smooth interpolation
            async def monitor_progress_queue():
                """Monitor progress queue and update Gradio progress bar smoothly"""
                import queue as queue_module
                last_progress = 0.05
                target_progress = 0.05
                last_desc = "Initializing..."
                pipeline_complete = False
                
                while not pipeline_complete:
                    try:
                        # Check queue for new target
                        try:
                            step, desc = progress_queue.get(timeout=0.1)
                            target_progress = max(target_progress, step)  # Only move forward
                            if desc:
                                last_desc = desc
                        except queue_module.Empty:
                            # No new progress, but keep updating to maintain visibility
                            pass
                        
                        # Check for task timing updates from progress.json
                        try:
                            progress_file = OUTPUT_DIR / "progress.json"
                            if progress_file.exists():
                                import json as json_lib
                                with open(progress_file, 'r', encoding='utf-8') as f:
                                    progress_data = json_lib.load(f)
                                    if "tasks_history" in progress_data and progress_data["tasks_history"]:
                                        # Build HTML table of task timings
                                        tasks = progress_data["tasks_history"]
                                        total_time = sum(t.get("duration_seconds", 0) for t in tasks)
                                        html_parts = [
                                            "<div style='font-family: monospace; font-size: 12px;'>",
                                            "<table style='width: 100%; border-collapse: collapse;'>",
                                            "<thead><tr style='background: #f0f0f0;'>",
                                            "<th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Task</th>",
                                            "<th style='text-align: right; padding: 4px; border: 1px solid #ddd;'>Duration</th>",
                                            "</tr></thead><tbody>"
                                        ]
                                        for task in tasks:
                                            task_name = task.get("task_name", "unknown")
                                            duration = task.get("duration_seconds", 0)
                                            # Format task name (remove _task suffix, add spaces)
                                            display_name = task_name.replace("_task", "").replace("_", " ").title()
                                            html_parts.append(
                                                f"<tr><td style='padding: 4px; border: 1px solid #ddd;'>{display_name}</td>"
                                                f"<td style='text-align: right; padding: 4px; border: 1px solid #ddd;'>{duration:.1f}s</td></tr>"
                                            )
                                        if total_time > 0:
                                            html_parts.append(
                                                f"<tr style='background: #e8f4f8; font-weight: bold;'>"
                                                f"<td style='padding: 4px; border: 1px solid #ddd;'>Total</td>"
                                                f"<td style='text-align: right; padding: 4px; border: 1px solid #ddd;'>{total_time:.1f}s</td></tr>"
                                            )
                                        html_parts.extend(["</tbody></table>", "</div>"])
                                        task_timing_html = "".join(html_parts)
                        except Exception:
                            pass  # Ignore errors reading timing data
                        
                        # Smooth interpolation towards target
                        if last_progress < target_progress:
                            # Increment by small steps for smooth animation
                            step_size = 0.005  # 0.5% increments
                            current_progress = min(last_progress + step_size, target_progress)
                            # Always show description to keep progress bar visible
                            progress(current_progress, desc=last_desc)
                            last_progress = current_progress
                        elif last_progress >= 0.99:
                            # Pipeline is complete
                            pipeline_complete = True
                            break
                        else:
                            # No progress change, but still update to keep bar visible
                            progress(last_progress, desc=last_desc)
                        
                        await asyncio.sleep(0.05)  # Update every 50ms for smooth animation
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        # Error - continue monitoring, but log for debugging
                        await asyncio.sleep(0.05)
                
                # Ensure final update before stopping
                if not pipeline_complete:
                    progress(min(target_progress, 1.0), desc=last_desc)
            
            # Start progress monitor task
            monitor_task = asyncio.create_task(monitor_progress_queue())
            
            # Run pipeline in background and periodically yield status updates
            loop = asyncio.get_event_loop()
            
            # Wrap run_pipeline to accept progress callback
            def run_with_progress():
                return run_pipeline(
                    jd,
                    str(profile_path),
                    str(custom_template_path) if custom_template_path else None,
                    reference_pdfs if reference_pdfs else None,
                    progress_callback=update_progress,
                    debug=debug,
                    fast_mode=fast_mode,
                    enable_ats=enable_ats,
                    enable_privacy=enable_privacy
                )
            
            # Start pipeline in executor
            pipeline_task = loop.run_in_executor(None, run_with_progress)
            
            # Periodically check status queue and yield updates
            import queue as queue_module
            while not pipeline_task.done():
                try:
                    # Check for status updates
                    try:
                        status_desc = status_queue.get_nowait()
                        yield {
                            progress_status: gr.update(value=status_desc)
                        }
                    except queue_module.Empty:
                        pass
                    
                    await asyncio.sleep(0.2)  # Check every 200ms
                except Exception:
                    await asyncio.sleep(0.2)
            
            # Wait for pipeline to complete
            try:
                result = await pipeline_task
                if isinstance(result, tuple) and len(result) == 3:
                    pdf_path, msg, cover_letter_pdf_path = result
                else:
                    # Backward compatibility
                    pdf_path, msg = result if isinstance(result, tuple) else (None, str(result))
                    cover_letter_pdf_path = None
            finally:
                # Ensure progress bar is visible before stopping monitor
                try:
                    progress(0.95, desc="Finalizing...")
                except Exception:
                    pass
                
                # Stop progress monitor gracefully
                monitor_task.cancel()
                try:
                    await asyncio.wait_for(monitor_task, timeout=0.5)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Smooth final progress update - ensure progress bar stays visible
            for final_step in [0.96, 0.98, 1.0]:
                try:
                    progress(final_step, desc="Finalizing...")
                except Exception:
                    pass  # Progress bar might be closed, continue anyway
                yield {
                    progress_status: gr.update(value="Finalizing...")
                }
                await asyncio.sleep(0.1)
            
            # Check if PDF was actually generated
            tex_path = RENDERED_TEX
            tex_file_path = str(tex_path) if tex_path.exists() else None
            
            if pdf_path and Path(pdf_path).exists():
                # Ensure PDF file is properly closed and accessible
                pdf_absolute = str(Path(pdf_path).resolve())
                # Force file system sync to ensure file is written
                try:
                    os.sync() if hasattr(os, 'sync') else None
                except Exception:
                    pass
                
                # Helper function to create PDF preview HTML
                def create_pdf_preview_html(pdf_path: str, pdf_name: str = "PDF") -> str:
                    """Create HTML preview for a PDF file using base64 encoding."""
                    try:
                        pdf_abs = str(Path(pdf_path).resolve())
                        with open(pdf_abs, 'rb') as f:
                            pdf_bytes = f.read()
                            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                            return f"""
                            <iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="800px" style="border: 1px solid #ccc; border-radius: 4px;">
                                <p>Your browser does not support PDFs. <a href="{pdf_abs}" target="_blank">Download the {pdf_name}</a> instead.</p>
                            </iframe>
                            """
                    except Exception as e:
                        logger.warning(f"Could not create base64 PDF preview for {pdf_name}: {e}, using file link")
                        pdf_abs = str(Path(pdf_path).resolve())
                        return f"""
                        <div style="padding: 20px; text-align: center;">
                            <p>{pdf_name} Preview</p>
                            <a href="{pdf_abs}" target="_blank" style="display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">Open {pdf_name} in New Tab</a>
                        </div>
                        """
                
                # Create resume PDF preview
                pdf_preview_html = create_pdf_preview_html(pdf_absolute, "Resume PDF")
                
                # Show download section and hide status
                cover_letter_absolute = None
                cover_letter_preview_html = "<div style='padding: 20px; text-align: center; color: #666;'>Cover letter not generated</div>"
                if cover_letter_pdf_path:
                    try:
                        cover_letter_path_obj = Path(cover_letter_pdf_path)
                        if cover_letter_path_obj.exists():
                            cover_letter_absolute = str(cover_letter_path_obj.resolve())
                            cover_letter_preview_html = create_pdf_preview_html(cover_letter_absolute, "Cover Letter PDF")
                    except Exception as e:
                        logger.debug(f"Could not resolve cover letter PDF path in UI: {e}")
                # Load task timing data for final display (only in debug mode)
                task_timing_html_final = ""
                if debug:
                    try:
                        progress_file = OUTPUT_DIR / "progress.json"
                        if progress_file.exists():
                            import json as json_lib
                            with open(progress_file, 'r', encoding='utf-8') as f:
                                progress_data = json_lib.load(f)
                                if "tasks_history" in progress_data and progress_data["tasks_history"]:
                                    tasks = progress_data["tasks_history"]
                                    total_time = sum(t.get("duration_seconds", 0) for t in tasks)
                                    
                                    # Find max duration for scaling progress bars
                                    max_duration = max((t.get("duration_seconds", 0) for t in tasks), default=1)
                                    
                                    html_parts = [
                                        "<div style='font-family: system-ui, -apple-system, sans-serif; font-size: 13px;'>",
                                        "<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border-radius: 8px 8px 0 0; margin-bottom: 0;'>",
                                        "<strong>⏱️ Task Execution Timeline</strong>",
                                        f"<span style='float: right; font-size: 11px; opacity: 0.9;'>Total: {total_time:.1f}s ({total_time/60:.1f} min)</span>",
                                        "</div>",
                                        "<table style='width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>",
                                        "<thead><tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>",
                                        "<th style='text-align: left; padding: 10px; border: none; font-weight: 600; color: #495057;'>Task</th>",
                                        "<th style='text-align: center; padding: 10px; border: none; font-weight: 600; color: #495057; width: 200px;'>Duration</th>",
                                        "<th style='text-align: right; padding: 10px; border: none; font-weight: 600; color: #495057;'>Time</th>",
                                        "</tr></thead><tbody>"
                                    ]
                                    
                                    for idx, task in enumerate(tasks):
                                        task_name = task.get("task_name", "unknown")
                                        duration = task.get("duration_seconds", 0)
                                        display_name = task_name.replace("_task", "").replace("_", " ").title()
                                        
                                        # Calculate percentage for progress bar
                                        bar_width = (duration / max_duration * 100) if max_duration > 0 else 0
                                        
                                        # Color coding based on duration
                                        if duration > 60:
                                            bar_color = "#dc3545"  # Red for long tasks
                                        elif duration > 30:
                                            bar_color = "#ffc107"  # Yellow for medium tasks
                                        else:
                                            bar_color = "#28a745"  # Green for short tasks
                                        
                                        # Alternating row colors
                                        row_bg = "#ffffff" if idx % 2 == 0 else "#f8f9fa"
                                        
                                        html_parts.append(
                                            f"<tr style='background: {row_bg}; border-bottom: 1px solid #e9ecef;'>"
                                            f"<td style='padding: 10px; border: none;'>"
                                            f"<span style='font-weight: 500; color: #212529;'>{display_name}</span>"
                                            f"</td>"
                                            f"<td style='padding: 10px; border: none; text-align: center;'>"
                                            f"<div style='background: #e9ecef; border-radius: 4px; height: 20px; position: relative; overflow: hidden;'>"
                                            f"<div style='background: {bar_color}; height: 100%; width: {bar_width:.1f}%; border-radius: 4px; transition: width 0.3s ease;'></div>"
                                            f"<span style='position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); font-size: 11px; font-weight: 600; color: #212529;'>{duration:.1f}s</span>"
                                            f"</div>"
                                            f"</td>"
                                            f"<td style='padding: 10px; border: none; text-align: right; color: #6c757d; font-size: 12px;'>{duration:.1f}s</td>"
                                            f"</tr>"
                                        )
                                    
                                    if total_time > 0:
                                        html_parts.append(
                                            f"<tr style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-weight: bold; border-top: 2px solid #764ba2;'>"
                                            f"<td style='padding: 12px; border: none;'>Total Execution Time</td>"
                                            f"<td style='padding: 12px; border: none; text-align: center;'>"
                                            f"<div style='background: rgba(255,255,255,0.2); border-radius: 4px; height: 24px; display: flex; align-items: center; justify-content: center;'>"
                                            f"{total_time:.1f}s ({total_time/60:.1f} min)"
                                            f"</div>"
                                            f"</td>"
                                            f"<td style='padding: 12px; border: none; text-align: right;'>{total_time:.1f}s</td>"
                                            f"</tr>"
                                        )
                                    html_parts.extend(["</tbody></table>", "</div>"])
                                    task_timing_html_final = "".join(html_parts)
                    except Exception:
                        pass
                
                yield {
                    progress_status: gr.update(value="✅ Resume generated successfully!"),
                    download_section: gr.update(visible=True),
                    adjustment_chat_section: gr.update(visible=True),
                    task_timing_display: gr.update(
                        value=task_timing_html_final if task_timing_html_final else "<div style='padding: 10px; text-align: center; color: #666;'>Timing information not available</div>", 
                        visible=debug  # Only show timeline in debug mode
                    ),
                    pdf_preview: pdf_preview_html,
                    cover_letter_preview: cover_letter_preview_html,
                    pdf_file: pdf_absolute,
                    tex_file: tex_file_path if tex_file_path else None,
                    cover_letter_file: gr.update(value=cover_letter_absolute, visible=cover_letter_absolute is not None),
                    status: gr.update(visible=False)
                }
            else:
                # Show error in status, hide download section
                yield {
                    progress_status: gr.update(value="❌ Generation failed"),
                    download_section: gr.update(visible=False),
                    adjustment_chat_section: gr.update(visible=False),
                    task_timing_display: gr.update(visible=False, value=""),
                    pdf_preview: "",
                    cover_letter_preview: "",
                    pdf_file: None,
                    tex_file: None,
                    cover_letter_file: gr.update(visible=False),
                    status: gr.update(value=msg, visible=True)
                }
        
        def handle_adjustment(history, user_message, current_pdf, document_type="Resume", current_cover_letter_pdf=None, status_text="", current_pdf_preview="", current_cover_letter_preview=""):
            """Handle user adjustment requests by editing JSON files and regenerating LaTeX."""
            if not user_message.strip():
                return history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, "Please enter a request."
            
            try:
                import json
                
                # Add user message to chat
                history.append([f"[{document_type}] {user_message}", None])
                
                # Update status (preserve current previews)
                status_update = f"🔄 Processing your request for {document_type}..."
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                
                # Determine which files to check based on document type
                if document_type == "Cover Letter":
                    pdf_path = COVER_LETTER_PDF
                    required_json = OUTPUT_DIR / "cover_letter.json"
                    doc_type_lower = "cover letter"
                else:  # Resume
                    pdf_path = FINAL_PDF
                    # Check if at least one JSON file exists (required for regeneration)
                    required_json = OUTPUT_DIR / "summary_block.json"
                    doc_type_lower = "resume"
                
                # Check if JSON files exist (required for pipeline re-run)
                if not required_json.exists():
                    history[-1][1] = f"❌ Error: Required JSON files not found. Please regenerate the {doc_type_lower} first."
                    status_update = f"❌ Error: JSON files not found. Please generate the {doc_type_lower} first."
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                # Step 1: Apply edit request to JSON files using edit_engine
                status_update = f"📝 Applying edit to JSON files..."
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                
                from resume_builder.edit_engine import apply_edit_request
                
                edit_result = apply_edit_request(user_message)
                
                if not edit_result.get("ok"):
                    reason = edit_result.get("reason", "Unknown error")
                    history[-1][1] = f"❌ Could not apply edit: {reason}"
                    status_update = f"❌ Edit not possible: {reason}"
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                changed_fields = edit_result.get("changed_fields", [])
                if not changed_fields:
                    history[-1][1] = f"ℹ️ No changes were made. The {doc_type_lower} may already match your request."
                    status_update = f"ℹ️ No changes detected."
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                logger.info(f"[ADJUSTMENT] Edit applied successfully. Changed fields: {changed_fields}")
                
                # Step 2: Regenerate LaTeX from updated JSON files (skip full pipeline, just LaTeX generation)
                status_update = f"🔄 Regenerating LaTeX from updated JSON files..."
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                
                from resume_builder.latex_builder import build_resume_from_json_files
                
                # Load JSON files (same as pipeline does)
                identity_json = OUTPUT_DIR / "user_profile.json"
                summary_json = OUTPUT_DIR / "summary_block.json"
                experience_json = OUTPUT_DIR / "selected_experiences.json"
                education_json = OUTPUT_DIR / "education_block.json"
                skills_json = OUTPUT_DIR / "selected_skills.json"
                projects_json = OUTPUT_DIR / "selected_projects.json"  # Optional
                header_json = OUTPUT_DIR / "header_block.json"  # Optional
                
                # Check required files exist
                required_files = {
                    "user_profile.json": identity_json,
                    "summary_block.json": summary_json,
                    "selected_experiences.json": experience_json,
                    "selected_skills.json": skills_json,
                }
                
                missing_files = []
                for name, file_path in required_files.items():
                    if not file_path.exists():
                        missing_files.append(name)
                
                if missing_files:
                    history[-1][1] = f"❌ Error: Required JSON files missing: {', '.join(missing_files)}. Please regenerate the {doc_type_lower} first."
                    status_update = f"❌ Error: Missing required files."
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                # Regenerate LaTeX
                try:
                    if document_type == "Cover Letter":
                        # For cover letter, we need to handle it differently
                        from resume_builder.orchestration import _generate_cover_letter_pdf
                        from resume_builder.json_loaders import load_cover_letter
                        
                        cover_letter_data = load_cover_letter(OUTPUT_DIR / "cover_letter.json")
                        cover_letter_pdf_path = _generate_cover_letter_pdf(cover_letter_data, OUTPUT_DIR)
                        
                        if cover_letter_pdf_path and Path(cover_letter_pdf_path).exists():
                            updated_cover_letter_pdf = str(Path(cover_letter_pdf_path).resolve())
                            status_update = f"✅ Cover letter successfully regenerated!"
                            
                            # Update preview
                            import time
                            time.sleep(0.1)
                            
                            try:
                                with open(updated_cover_letter_pdf, 'rb') as f:
                                    pdf_bytes = f.read()
                                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                                    pdf_abs_for_link = str(Path(updated_cover_letter_pdf).resolve())
                                    updated_cover_letter_preview = f"""
                                    <iframe src="data:application/pdf;base64,{pdf_base64}#toolbar=1&navpanes=1&scrollbar=1" width="100%" height="800px" style="border: 1px solid #ccc; border-radius: 4px;">
                                        <p>Your browser does not support PDFs. <a href="{pdf_abs_for_link}" target="_blank">Download the PDF</a> instead.</p>
                                    </iframe>
                                    """
                            except Exception as e:
                                logger.warning(f"Could not create PDF preview: {e}")
                                updated_cover_letter_preview = f"""
                                <div style="padding: 20px; text-align: center;">
                                    <p>Cover letter updated successfully!</p>
                                    <a href="{updated_cover_letter_pdf}" target="_blank" style="display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">Open Cover Letter in New Tab</a>
                                </div>
                                """
                            
                            history[-1][1] = f"✅ Cover letter updated and regenerated successfully! Changed fields: {', '.join(changed_fields)}"
                            yield history, "", current_pdf, current_pdf_preview, updated_cover_letter_pdf, updated_cover_letter_preview, status_update
                            return
                        else:
                            history[-1][1] = f"❌ Error: Failed to regenerate cover letter PDF."
                            status_update = f"❌ Error: PDF generation failed."
                            yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                    else:
                        # Resume: regenerate LaTeX and compile
                        rendered_tex = RENDERED_TEX
                        
                        latex_content = build_resume_from_json_files(
                            identity_path=identity_json,
                            summary_path=summary_json,
                            experience_path=experience_json,
                            education_path=education_json,
                            skills_path=skills_json,
                            projects_path=projects_json if projects_json.exists() else None,
                            header_path=header_json if header_json.exists() else None,
                            template_path=None,  # Use default template
                            output_path=rendered_tex
                        )
                        
                        logger.info(f"[ADJUSTMENT] LaTeX regenerated: {rendered_tex}")
                        
                        # Step 3: Compile LaTeX to PDF
                        status_update = f"📄 Compiling updated {document_type} PDF..."
                        yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                        
                        from resume_builder.tools.latex_compile import LatexCompileTool
                        compile_tool = LatexCompileTool()
                        compile_result = compile_tool._run(
                            tex_path=str(rendered_tex),
                            out_name="final_resume.pdf"
                        )
                        
                        compile_success = (
                            isinstance(compile_result, dict) and compile_result.get("success", False)
                        ) or pdf_path.exists()
                        
                        if compile_success and pdf_path.exists():
                            updated_pdf_path = str(pdf_path.resolve())
                            status_update = f"✅ {document_type} successfully updated and regenerated!"
                            
                            # Small delay to ensure file is fully written
                            import time
                            time.sleep(0.1)
                            
                            # Update preview
                            try:
                                max_retries = 3
                                pdf_bytes = None
                                for attempt in range(max_retries):
                                    try:
                                        with open(updated_pdf_path, 'rb') as pdf_file_handle:
                                            pdf_bytes = pdf_file_handle.read()
                                        break
                                    except (IOError, OSError) as e:
                                        if attempt < max_retries - 1:
                                            time.sleep(0.2)
                                            continue
                                        raise
                                
                                if pdf_bytes:
                                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                                    pdf_abs_for_link = str(Path(updated_pdf_path).resolve())
                                    updated_preview = f"""
                                    <iframe src="data:application/pdf;base64,{pdf_base64}#toolbar=1&navpanes=1&scrollbar=1" width="100%" height="800px" style="border: 1px solid #ccc; border-radius: 4px;">
                                        <p>Your browser does not support PDFs. <a href="{pdf_abs_for_link}" target="_blank">Download the PDF</a> instead.</p>
                                    </iframe>
                                    """
                                    updated_pdf = updated_pdf_path
                                else:
                                    raise Exception("Failed to read PDF file after compilation")
                            except Exception as e:
                                logger.warning(f"Could not create PDF preview: {e}")
                                updated_preview = f"""
                                <div style="padding: 20px; text-align: center;">
                                    <p>{document_type} updated successfully!</p>
                                    <a href="{updated_pdf_path}" target="_blank" style="display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">Open {document_type} in New Tab</a>
                                </div>
                                """
                                updated_pdf = updated_pdf_path
                            
                            history[-1][1] = f"✅ {document_type} updated and regenerated successfully! Changed fields: {', '.join(changed_fields)}. The PDF preview has been refreshed."
                            yield history, "", updated_pdf, updated_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                        else:
                            error_info = ""
                            if isinstance(compile_result, dict):
                                error_info = compile_result.get("error", "Unknown error")
                            history[-1][1] = f"⚠️ {document_type} JSON was updated but PDF compilation failed:\n{error_info}\n\nCheck compile.log for details."
                            status_update = f"⚠️ Compilation failed. Check compile.log for details."
                            yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                            
                except Exception as e:
                    logger.error(f"[ADJUSTMENT] Error regenerating {document_type}: {e}", exc_info=True)
                    history[-1][1] = f"❌ Error regenerating {document_type}: {str(e)}\n\nPlease check the logs for more details."
                    status_update = f"❌ Error: {str(e)[:100]}"
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
            except Exception as e:
                error_msg = f"❌ Error processing adjustment: {str(e)}"
                logger.error(error_msg, exc_info=True)
                if len(history) > 0:
                    history[-1][1] = f"{error_msg}\n\nPlease check the logs for more details or try a more specific request."
                else:
                    history.append([user_message, error_msg])
                status_update = f"❌ Error occurred: {str(e)[:100]}"
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                return
        
        adjustment_btn.click(
            handle_adjustment,
            inputs=[adjustment_chat, adjustment_input, pdf_file, adjustment_document, cover_letter_file, adjustment_status, pdf_preview, cover_letter_preview],
            outputs=[adjustment_chat, adjustment_input, pdf_file, pdf_preview, cover_letter_file, cover_letter_preview, adjustment_status]
        )
        
        adjustment_input.submit(
            handle_adjustment,
            inputs=[adjustment_chat, adjustment_input, pdf_file, adjustment_document, cover_letter_file, adjustment_status, pdf_preview, cover_letter_preview],
            outputs=[adjustment_chat, adjustment_input, pdf_file, pdf_preview, cover_letter_file, cover_letter_preview, adjustment_status]
        )
        
        generate_btn.click(
            handle_generate,
            inputs=[jd_text, files_upload, debug_mode, fast_mode, enable_ats, enable_privacy],
            outputs=[progress_status, download_section, adjustment_chat_section, task_timing_display, pdf_preview, cover_letter_preview, pdf_file, tex_file, cover_letter_file, status],
            show_progress=True  # Show progress bar during generation
        )
        
        # Custom CSS to improve layout
        demo.css = """
        .gradio-container { 
            max-width: 1400px !important; 
            margin: 0 auto;
        }
        /* Only hide duplicate progress bars that are truly duplicates */
        /* Don't hide the main progress bar - it should be visible during generation */
        /* The progress bar from gr.Progress() should always be visible */
        /* Make progress bar appear inline with status */
        .progress-bar-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        /* Increase status box height */
        textarea[data-testid="textbox"] {
            min-height: 150px !important;
        }
        /* Better spacing for sections */
        .gr-markdown {
            margin-bottom: 1rem;
        }
        /* Improve file upload area */
        .gr-file {
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
        }
        /* Better button styling */
        .gr-button {
            margin: 10px 5px;
        }
        /* Improve tabbed interface */
        .gr-tabs {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
        }
        /* Better spacing for columns */
        .gr-row {
            margin: 15px 0;
        }
        /* Improve chatbot appearance */
        .gr-chatbot {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
        }
        /* Better radio button layout */
        .gr-radio {
            padding: 10px;
            background: #f9f9f9;
            border-radius: 6px;
            margin: 10px 0;
        }
        /* Button info styling */
        .button-info {
            margin-left: 15px;
            padding: 8px 15px;
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            border-radius: 4px;
            color: #856404;
        }
        /* Improve chatbot appearance */
        .gr-chatbot {
            background: #fafafa !important;
        }
        /* Better column layout spacing */
        .gr-column {
            gap: 15px;
        }
        """
        
        # Removed JavaScript that was hiding progress bars
        # The progress bar from gr.Progress() should be visible during generation
        # If there are duplicate progress bars, Gradio will handle them appropriately
    
    return demo


def run_ui():
    """Launch the Gradio UI."""
    demo = build_ui()
    demo.queue()
    port = int(os.getenv("GRADIO_SERVER_PORT") or os.getenv("PORT") or "7860")
    demo.launch(server_name="127.0.0.1", server_port=port, inbrowser=True)

