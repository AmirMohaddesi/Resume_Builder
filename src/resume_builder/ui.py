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
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse

# Import paths and constants
from resume_builder.paths import (
    PROJECT_ROOT, OUTPUT_DIR, GENERATED_DIR, LOG_DIR, TEMPLATES, ensure_dirs
)
from resume_builder.logger import get_logger

# Import orchestration functions
from resume_builder.orchestration import run_pipeline

# UI Helper Constants
MAX_DYNAMIC_FIELDS = 5
PROGRESS_UPDATE_INTERVAL = 0.2  # seconds
FINAL_PROGRESS_ANIMATION_TICKS = 20
PROGRESS_ANIMATION_STEP = 0.02
MAX_PDF_SIZE_FOR_BASE64 = 10 * 1024 * 1024  # 10MB
AUTO_SAVE_DEBOUNCE_SECONDS = 2.0

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


# ============================================================================
# UI Helper Functions (extracted to reduce code duplication)
# ============================================================================

def create_dynamic_field_updates(
    dynamic_fields: Dict[str, Dict[str, str]], 
    max_fields: int = MAX_DYNAMIC_FIELDS
) -> Tuple[List, List]:
    """
    Create UI update dictionaries for dynamic fields.
    
    Args:
        dynamic_fields: Dictionary mapping field keys to {label, value} dicts
        max_fields: Maximum number of dynamic fields
        
    Returns:
        Tuple of (row_updates, field_updates) lists for Gradio components
    """
    import gradio as gr
    
    row_updates = []
    field_updates = []
    
    for i in range(1, max_fields + 1):
        field_key = f"field_{i}"
        if field_key in dynamic_fields:
            field_data = dynamic_fields[field_key]
            row_updates.append(gr.update(visible=True))
            field_updates.append(gr.update(
                label=field_data.get("label", ""),
                value=field_data.get("value", "")
            ))
        else:
            row_updates.append(gr.update(visible=False))
            field_updates.append(gr.update(value="", label=""))
    
    return row_updates, field_updates


def create_pdf_preview_html(
    pdf_path: Path, 
    pdf_name: str = "PDF",
    use_base64: bool = True
) -> str:
    """
    Create HTML preview for a PDF file.
    
    Uses base64 encoding for small files, file URL for large files.
    
    Args:
        pdf_path: Path to PDF file
        pdf_name: Display name for the PDF
        use_base64: Whether to use base64 encoding (False for large files)
        
    Returns:
        HTML string for PDF preview
    """
    try:
        pdf_abs = str(pdf_path.resolve())
        
        # Check file size and use appropriate method
        if use_base64 and pdf_path.exists():
            file_size = pdf_path.stat().st_size
            if file_size > MAX_PDF_SIZE_FOR_BASE64:
                logger.info(f"PDF too large ({file_size} bytes), using file URL instead of base64")
                return create_pdf_link_html(pdf_abs, pdf_name)
        
        if use_base64:
            with open(pdf_abs, 'rb') as f:
                pdf_bytes = f.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                return f"""
                <iframe src="data:application/pdf;base64,{pdf_base64}" 
                        width="100%" height="800px" 
                        style="border: 1px solid #ccc; border-radius: 4px;">
                    <p>Your browser does not support PDFs. 
                       <a href="{pdf_abs}" target="_blank">Download the {pdf_name}</a> instead.</p>
                </iframe>
                """
        else:
            return create_pdf_link_html(pdf_abs, pdf_name)
            
    except Exception as e:
        logger.warning(f"Could not create PDF preview for {pdf_name}: {e}")
        pdf_abs = str(pdf_path.resolve()) if pdf_path.exists() else str(pdf_path)
        return create_pdf_link_html(pdf_abs, pdf_name)


def create_pdf_link_html(pdf_path: str, pdf_name: str = "PDF") -> str:
    """Create HTML with download link for PDF."""
    return f"""
    <div style="padding: 20px; text-align: center;">
        <p>{pdf_name} Preview</p>
        <a href="{pdf_path}" target="_blank" 
           style="display: inline-block; padding: 10px 20px; background: #007bff; 
                  color: white; text-decoration: none; border-radius: 4px;">
            Open {pdf_name} in New Tab
        </a>
    </div>
    """


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email or not email.strip():
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url or not url.strip():
        return False
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False


def extract_file_info(files: List[str]) -> Dict[str, any]:
    """
    Extract and categorize uploaded files.
    
    Args:
        files: List of file paths
        
    Returns:
        Dictionary with 'resume_file', 'tex_file', 'reference_pdfs', and counts
    """
    resume_file = None
    tex_file = None
    reference_pdfs = []
    
    resume_count = 0
    tex_count = 0
    pdf_count = 0
    
    for file_path in files:
        if not file_path:
            continue
            
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
                reference_pdfs.append(file_path)
                pdf_count += 1
    
    return {
        'resume_file': resume_file,
        'tex_file': tex_file,
        'reference_pdfs': reference_pdfs,
        'resume_count': resume_count,
        'tex_count': tex_count,
        'pdf_count': pdf_count
    }


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
                location = gr.Textbox(label="Location", lines=1, max_lines=1, placeholder="e.g., City, State")
            
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
            enable_cover_letter = gr.Checkbox(
                label="📄 Cover Letter",
                value=True,
                info="Generate a tailored cover letter (can be disabled for faster execution)"
            )
            
            enforce_2_page_limit = gr.Checkbox(
                label="📏 Enforce 2-Page Limit",
                value=True,
                info="Automatically trim content and iteratively remove least important items to fit within 2 pages"
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
        
        # Manual progress bar slider (fully controlled by us, no conflicts)
        progress_bar = gr.Slider(
            minimum=0,
            maximum=100,
            value=0,
            label="Progress",
            interactive=False,
            show_label=True
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
                avatar_images=(None, "🤖"),
                type="messages"
            )
            
            with gr.Row():
                adjustment_input = gr.Textbox(
                    label="Your Request",
                    placeholder="Example: 'Add a newline after the summary section' or 'Fix the spacing in the experience section' or 'Make the cover letter opening more engaging'",
                    lines=3,
                    scale=4
                )
                adjustment_btn = gr.Button("📤 Send Request", variant="primary", scale=1, size="lg")
        
        # AI Edit section (hidden until PDF is generated)
        with gr.Column(visible=False) as ai_edit_section:
            gr.Markdown("---")
            gr.Markdown("## 🤖 AI-Powered Section Editing")
            gr.Markdown("Use AI to edit specific sections of your resume. Preview changes before applying.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    ai_section_dropdown = gr.Dropdown(
                        label="📝 Section to Edit",
                        choices=["summary", "header", "experiences", "projects", "skills", "education", "cover_letter"],
                        value="summary",
                        info="Select which section to edit"
                    )
                    ai_strict_checkbox = gr.Checkbox(
                        label="🔒 Strict Mode",
                        value=True,
                        info="Rewrite text only, no structural changes (recommended)"
                    )
                with gr.Column(scale=2):
                    ai_instruction_text = gr.Textbox(
                        label="✏️ AI Edit Instruction",
                        lines=4,
                        placeholder="e.g., Make the summary shorter and emphasize multi-robot SLAM and ROS2.",
                        info="Describe how you want the section edited"
                    )
            
            with gr.Row():
                ai_preview_btn = gr.Button("👁️ Preview AI Edit", variant="secondary", size="lg")
                ai_apply_btn = gr.Button("✅ Apply AI Edit", variant="primary", size="lg")
            
            with gr.Row():
                with gr.Column():
                    ai_status_output = gr.Markdown(
                        label="📊 AI Edit Status",
                        value="Ready to preview or apply AI edits..."
                    )
                with gr.Column():
                    ai_diff_output = gr.Textbox(
                        label="📋 Changes Preview",
                        lines=12,
                        interactive=False,
                        placeholder="Diff preview will appear here after previewing an edit..."
                    )
        
        status = gr.Textbox(label="Generation Status", lines=8, max_lines=20, visible=False)
        
        # Event handlers
        def handle_files_upload_combined(files):
            if not files:
                return {
                    first_name: "", last_name: "", title: "", email: "", phone: "", location: "",
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
            
            # Separate files by type (using helper function)
            file_info = extract_file_info(files)
            resume_file = file_info['resume_file']
            tex_file = file_info['tex_file']
            resume_count = file_info['resume_count']
            tex_count = file_info['tex_count']
            pdf_count = file_info['pdf_count']
            
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
                
                # Build dynamic field updates (using helper function)
                row_updates, field_updates = create_dynamic_field_updates(dynamic_fields)
                
                return {
                    first_name: identity.get("first", ""),
                    last_name: identity.get("last", ""),
                    title: identity.get("title", ""),
                    email: identity.get("email", ""),
                    phone: identity.get("phone", ""),
                    location: identity.get("location", ""),
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
                    first_name: "", last_name: "", title: "", email: "", phone: "", location: "",
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
                result.get(location, ""),
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
            outputs=[first_name, last_name, title, email, phone, location, website, linkedin, github,
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
            
            # Update UI with rows (using helper function)
            row_updates, field_updates = create_dynamic_field_updates(current_state)
            
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
            
            # Rebuild UI state (using helper function)
            row_updates, field_updates = create_dynamic_field_updates(current_state)
            
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
        
        def auto_save_profile(first, last, title_val, email_val, phone_val, location_val,
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
                    first, last, title_val, email_val, phone_val, location_val,
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
            first_name, last_name, title, email, phone, location, website, linkedin, github,
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
        
        async def handle_generate(jd, uploaded_files, debug, fast_mode, enable_ats, enable_privacy, enable_cover_letter, enforce_2_page_limit, progress=gr.Progress()):
            if not jd.strip():
                yield {
                    progress_status: gr.update(value="❌ Please paste a job description."),
                    progress_bar: gr.update(value=0),
                    download_section: gr.update(visible=False),
                    adjustment_chat_section: gr.update(visible=False),
                    ai_edit_section: gr.update(visible=False),
                    task_timing_display: gr.update(visible=False, value=""),
                    pdf_preview: "",
                    pdf_file: None,
                    tex_file: None,
                    status: gr.update(value="❌ Please paste a job description.", visible=True)
                }
                return
            
            # Initialize UI
            yield {
                progress_status: gr.update(value="Starting resume generation..."),
                progress_bar: gr.update(value=0),
                download_section: gr.update(visible=False),
                adjustment_chat_section: gr.update(visible=False),
                ai_edit_section: gr.update(visible=False),
                task_timing_display: gr.update(visible=debug, value="<div style='padding: 10px; text-align: center; color: #666;'>⏳ Collecting timing information...</div>"),
                pdf_preview: "",
                status: gr.update(visible=False)
            }
            
            # Process uploaded files
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
                            if custom_template_path is None:
                                custom_template_path = OUTPUT_DIR / "custom_template.tex"
                                shutil.copy2(uploaded_path, custom_template_path)
                                logger.info(f"Custom template uploaded: {custom_template_path}")
                        
                        elif file_ext == '.pdf':
                            pdf_num = len(reference_pdfs) + 1
                            dest_path = OUTPUT_DIR / f"reference_resume_{pdf_num}.pdf"
                            shutil.copy2(uploaded_path, dest_path)
                            reference_pdfs.append(str(dest_path))
                            logger.info(f"Reference PDF {pdf_num} uploaded: {dest_path}")
                    
                    except Exception as e:
                        logger.warning(f"Error processing file {file_path}: {e}")
            
            # Use saved profile from output/ if it exists, otherwise use default
            saved_profile = OUTPUT_DIR / "user_profile.json"
            if saved_profile.exists():
                profile_path = str(saved_profile)
                logger.info(f"Using saved profile from output: {profile_path}")
            else:
                profile_path = str(DEFAULT_PROFILE_PATH)
                logger.info(f"Using default profile: {profile_path}")
            
            # Background thread result holder
            result_holder = {"result": None, "error": None}
            done_flag = {"done": False}
            
            # Queue to capture log messages from orchestrator
            log_message_queue = queue.Queue()
            
            # Custom logging handler to capture messages
            class QueueLogHandler(logging.Handler):
                """Logging handler that puts messages into a queue."""
                def __init__(self, message_queue):
                    super().__init__()
                    self.message_queue = message_queue
                
                def emit(self, record):
                    """Emit a log record to the queue."""
                    try:
                        # Format the message (simplified, no timestamps)
                        msg = self.format(record)
                        # Only capture INFO and above (skip DEBUG)
                        if record.levelno >= logging.INFO:
                            # Clean up the message - remove logger name prefixes
                            clean_msg = msg
                            if " - " in clean_msg:
                                # Remove timestamp and logger name, keep just the message
                                parts = clean_msg.split(" - ", 1)
                                if len(parts) > 1:
                                    clean_msg = parts[-1]
                            # Filter out very verbose messages
                            if not any(skip in clean_msg.lower() for skip in [
                                "debug", "trace", "detailed", "verbose"
                            ]):
                                self.message_queue.put(clean_msg, block=False)
                    except Exception:
                        pass  # Ignore queue errors
            
            # Background thread wrapper function
            def run_orchestrator_in_thread():
                """Run orchestrator in background thread and store result."""
                # Add queue handler to logger to capture messages
                queue_handler = QueueLogHandler(log_message_queue)
                queue_handler.setLevel(logging.INFO)
                # Use simple format for cleaner messages
                formatter = logging.Formatter("%(message)s")
                queue_handler.setFormatter(formatter)
                
                # Get the resume_builder logger and add our handler
                orchestrator_logger = logging.getLogger("resume_builder")
                orchestrator_logger.addHandler(queue_handler)
                
                try:
                    result = run_pipeline(
                        jd,
                        str(profile_path),
                        str(custom_template_path) if custom_template_path else None,
                        reference_pdfs if reference_pdfs else None,
                        progress_callback=None,  # No progress callback - we use fake progress
                        debug=debug,
                        fast_mode=fast_mode,
                        enable_ats=enable_ats,
                        enable_privacy=enable_privacy,
                        enable_cover_letter=enable_cover_letter,
                        enforce_2_page_limit=enforce_2_page_limit
                    )
                    result_holder["result"] = result
                except Exception as e:
                    result_holder["error"] = str(e)
                    logger.error(f"Orchestrator error: {e}", exc_info=True)
                finally:
                    # Remove the handler when done
                    orchestrator_logger.removeHandler(queue_handler)
                    done_flag["done"] = True
            
            # Start orchestrator in background thread
            import threading
            orchestrator_thread = threading.Thread(target=run_orchestrator_in_thread, daemon=True)
            orchestrator_thread.start()
            
            # Fake progress bar animation - time-based to match actual runtime
            # Based on observed timings: ~500s (best), ~867s (typical), ~1000s (with cover letter)
            import time
            start_time = time.time()
            MAX_FAKE_PROGRESS = 0.90  # Don't exceed 90% until done
            UPDATE_INTERVAL = 0.5  # Update every 0.5 seconds
            
            # Target time to reach 90%: ~620 seconds (based on actual ~10.9 min runs)
            TARGET_TIME_TO_90_PERCENT = 620.0  # seconds (~10.3 minutes)
            
            # Default status message (will be updated with log messages)
            current_status = "Running pipeline... This typically takes 10-11 minutes depending on complexity."
            last_log_message_time = start_time
            
            # Animate fake progress while thread is running
            while not done_flag["done"]:
                # Check for new log messages from orchestrator
                try:
                    # Drain the queue and use the latest message
                    latest_message = None
                    while True:
                        try:
                            latest_message = log_message_queue.get_nowait()
                            last_log_message_time = time.time()
                        except queue.Empty:
                            break
                    
                    # Update status if we got a new message
                    if latest_message:
                        # Truncate very long messages
                        if len(latest_message) > 150:
                            latest_message = latest_message[:147] + "..."
                        current_status = latest_message
                except Exception:
                    pass  # Ignore queue errors
                
                # Calculate progress based on elapsed time
                elapsed_time = time.time() - start_time
                
                # Time-based progress: reach 90% after TARGET_TIME_TO_90_PERCENT seconds
                # Simple linear progression that slows down as it approaches 90%
                if elapsed_time < TARGET_TIME_TO_90_PERCENT:
                    # Linear progress: 90% over TARGET_TIME_TO_90_PERCENT seconds
                    fake_progress = (elapsed_time / TARGET_TIME_TO_90_PERCENT) * MAX_FAKE_PROGRESS
                else:
                    # After target time, stay at 90% (or very slowly approach it)
                    # This handles runs longer than expected
                    fake_progress = MAX_FAKE_PROGRESS
                
                progress_value = int(fake_progress * 100)
                
                yield {
                    progress_status: gr.update(value=current_status),
                    progress_bar: gr.update(value=progress_value)
                }
                
                await asyncio.sleep(UPDATE_INTERVAL)
            
            # Thread is done - wait a moment to ensure result is written
            await asyncio.sleep(0.1)
            
            # Check result and finalize
            if result_holder["error"]:
                # Error case: reset to 0% and show error
                yield {
                    progress_status: gr.update(value=f"❌ Error: {result_holder['error']}"),
                    progress_bar: gr.update(value=0),
                    download_section: gr.update(visible=False),
                    adjustment_chat_section: gr.update(visible=False),
                    ai_edit_section: gr.update(visible=False),
                    task_timing_display: gr.update(visible=False, value=""),
                    pdf_preview: "",
                    cover_letter_preview: "",
                    pdf_file: None,
                    tex_file: None,
                    cover_letter_file: gr.update(visible=False),
                    status: gr.update(value=result_holder["error"], visible=True)
                }
                return
            
            # Success case: get result and jump to 100%
            result = result_holder["result"]
            if isinstance(result, tuple) and len(result) == 3:
                pdf_path, msg, cover_letter_pdf_path = result
            else:
                pdf_path, msg = result if isinstance(result, tuple) else (None, str(result))
                cover_letter_pdf_path = None
            
            # Check if PDF was actually generated before showing success
            if pdf_path and Path(pdf_path).exists():
                # Jump to 100% with success message
                yield {
                    progress_status: gr.update(value="Done! JSON updated, LaTeX rebuilt, PDF compiled."),
                    progress_bar: gr.update(value=100)
                }
            else:
                # PDF not generated - treat as error
                error_status = msg if msg else "PDF generation failed"
                yield {
                    progress_status: gr.update(value=f"❌ Error: {error_status}"),
                    progress_bar: gr.update(value=0),
                    download_section: gr.update(visible=False),
                    adjustment_chat_section: gr.update(visible=False),
                    ai_edit_section: gr.update(visible=False),
                    task_timing_display: gr.update(visible=False, value=""),
                    pdf_preview: "",
                    cover_letter_preview: "",
                    pdf_file: None,
                    tex_file: None,
                    cover_letter_file: gr.update(visible=False),
                    status: gr.update(value=error_status, visible=True)
                }
                return
            
            await asyncio.sleep(0.1)
            
            # PDF exists (we already checked above) - proceed with final UI setup
            tex_path = RENDERED_TEX
            tex_file_path = str(tex_path) if tex_path.exists() else None
            
            # Check for LaTeX compilation errors
            latex_errors_path = OUTPUT_DIR / "latex_errors.json"
            error_message = None
            known_error_hint = None
            
            # Check for known recurring errors from error memory system
            try:
                from resume_builder.latex_error_memory import lookup_errors, compute_latex_fingerprint
                rendered_tex_path = GENERATED_DIR / "rendered_resume.tex"
                if rendered_tex_path.exists():
                    tex_content = rendered_tex_path.read_text(encoding='utf-8')
                    fingerprint = compute_latex_fingerprint(tex_content)
                    known_errors = lookup_errors(fingerprint)
                    if known_errors:
                        # Get the most frequent error
                        primary_error = known_errors[0]
                        count = primary_error.get("count", 1)
                        if count > 1:
                            error_type = primary_error.get("error_type", "Unknown")
                            suggested_fix = primary_error.get("suggested_fix", "")
                            known_error_hint = f"⚠️ Recurring LaTeX Error (seen {count} times): {error_type}"
                            if suggested_fix:
                                known_error_hint += f"\n💡 Suggested fix: {suggested_fix}"
            except Exception as e:
                logger.debug(f"Could not check error memory: {e}")
            
            if latex_errors_path.exists():
                try:
                    with open(latex_errors_path, 'r', encoding='utf-8') as f:
                        errors_data = json.load(f)
                        if errors_data.get("status") == "success" and errors_data.get("analysis"):
                            analysis = errors_data.get("analysis", {})
                            root_cause = analysis.get("root_cause", "Unknown error")
                            recommended_fix = analysis.get("recommended_fix", "")
                            error_message = f"⚠️ LaTeX Compilation Error:\n\nRoot Cause: {root_cause}\n\nRecommended Fix: {recommended_fix}"
                            
                            # Add known error hint if available
                            if known_error_hint:
                                error_message = f"{known_error_hint}\n\n--- Current Error Analysis ---\n\n{error_message}"
                except Exception as e:
                    logger.debug(f"Could not read latex_errors.json: {e}")
            elif known_error_hint:
                # Show known error hint even if no current error analysis
                error_message = known_error_hint
            
            # Build final UI (PDF exists, we already verified)
            # Ensure PDF file is properly closed and accessible
            pdf_absolute = str(Path(pdf_path).resolve())
            # Force file system sync to ensure file is written
            try:
                os.sync() if hasattr(os, 'sync') else None
            except Exception:
                pass
            
            # Create resume PDF preview (using helper function)
            pdf_preview_html = create_pdf_preview_html(Path(pdf_absolute), "Resume PDF")
            
            # Show download section and hide status
            cover_letter_absolute = None
            cover_letter_preview_html = "<div style='padding: 20px; text-align: center; color: #666;'>Cover letter not generated</div>"
            
            # Check for refined outputs and show info
            refined_info = []
            summary_refined_path = OUTPUT_DIR / "summary_refined.json"
            if summary_refined_path.exists():
                try:
                    with open(summary_refined_path, 'r', encoding='utf-8') as f:
                        refined_data = json.load(f)
                        if refined_data.get("status") == "success":
                            word_count = refined_data.get("word_count", 0)
                            refined_info.append(f"✨ Using refined summary ({word_count} words)")
                except Exception:
                    pass
            
            cover_letter_refined_path = OUTPUT_DIR / "cover_letter_refined.json"
            if cover_letter_refined_path.exists():
                try:
                    with open(cover_letter_refined_path, 'r', encoding='utf-8') as f:
                        refined_data = json.load(f)
                        if refined_data.get("status") == "success":
                            word_count = refined_data.get("word_count", 0)
                            refined_info.append(f"✨ Using refined cover letter ({word_count} words)")
                except Exception:
                    pass
            if cover_letter_pdf_path:
                try:
                    cover_letter_path_obj = Path(cover_letter_pdf_path)
                    if cover_letter_path_obj.exists():
                        cover_letter_absolute = str(cover_letter_path_obj.resolve())
                        cover_letter_preview_html = create_pdf_preview_html(cover_letter_path_obj, "Cover Letter PDF")
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
                                
                                logger.debug(f"Found {len(tasks)} tasks in progress.json")
                                
                                # Filter out cover letter tasks if cover letter was disabled in this run
                                cover_letter_task_names = ["write_cover_letter_task", "refine_cover_letter_task"]
                                
                                # Very lenient time filtering - show tasks from last 24 hours
                                # This ensures we catch all tasks from recent runs
                                from datetime import datetime, timedelta
                                current_time = datetime.now()
                                time_threshold = current_time - timedelta(hours=24)
                                
                                # Define valid task names from tasks.yaml (real pipeline tasks only)
                                # These are the actual tasks that exist in the pipeline
                                # NOTE: Fake/placeholder tasks like "Finalization", "Communication Preparation"
                                # are NOT real tasks and will be filtered out
                                valid_task_names = {
                                    # Core pipeline tasks from tasks.yaml
                                    "parse_job_description_task",
                                    "select_experiences_task",
                                    "select_projects_task",
                                    "select_skills_task",
                                    "write_header_task",
                                    "write_summary_task",
                                    "write_education_section_task",
                                    "ats_check_task",
                                    "privacy_validation_task",
                                    "write_cover_letter_task",
                                    "refine_cover_letter_task",
                                    "refine_summary_task",
                                    "analyze_latex_errors_task",
                                    # Orchestration-level timing (real wall-clock)
                                    "crew_execution",
                                    # Legacy/deterministic tasks (may appear in old data)
                                    "profile_validation_task",
                                    "collect_file_info_task",
                                    "template_validation_task",
                                }
                                
                                filtered_tasks = []
                                for t in tasks:
                                    task_name = t.get("task_name", "")
                                    duration = t.get("duration_seconds", 0)
                                    
                                    logger.debug(f"Processing task: {task_name}, duration: {duration}s")
                                    
                                    # CRITICAL: Filter out fake/placeholder tasks that don't exist in tasks.yaml
                                    # These are NOT real pipeline tasks and should be ignored
                                    if task_name not in valid_task_names:
                                        # Check if it's a known fake task pattern
                                        fake_patterns = [
                                            "finalization", "communication_preparation", "next_steps_planning",
                                            "alternative_methods_investigation", "data_acquisition_strategy",
                                            "retrieving_profile_data", "exploring_alternatives",
                                            "profile_data_retrieval", "data_retrieval", "experience_selection",
                                            "summary_creation", "Select and summarize projects"  # Wrong format
                                        ]
                                        if any(pattern in task_name.lower() for pattern in fake_patterns):
                                            logger.debug(f"Filtering out fake/placeholder task: {task_name}")
                                            continue
                                        # Also filter tasks with suspiciously round durations (5.0, 10.0, 15.0, etc.)
                                        # Real tasks have fractional seconds from actual execution
                                        if duration > 0 and duration == int(duration) and duration % 5 == 0 and duration <= 120:
                                            logger.debug(f"Filtering out suspicious round-duration task: {task_name} ({duration}s)")
                                            continue
                                    
                                    # Skip cover letter tasks if disabled
                                    if not enable_cover_letter and task_name in cover_letter_task_names:
                                        logger.debug(f"Skipping cover letter task: {task_name}")
                                        continue
                                    
                                    # Filter by timestamp if available, otherwise ALWAYS include the task
                                    # (be very lenient - include tasks without timestamps)
                                    completed_at_str = t.get("completed_at", "")
                                    if completed_at_str:
                                        try:
                                            # Handle various timestamp formats
                                            task_time_str = completed_at_str.replace('Z', '+00:00')
                                            if '+' in task_time_str or task_time_str.endswith('Z'):
                                                # Timezone-aware format
                                                task_time = datetime.fromisoformat(task_time_str)
                                                task_time_naive = task_time.replace(tzinfo=None) if task_time.tzinfo else task_time
                                            else:
                                                # Timezone-naive format
                                                task_time_naive = datetime.fromisoformat(task_time_str)
                                            
                                            # Only filter out if task is clearly too old (more than 24 hours)
                                            if task_time_naive < time_threshold:
                                                logger.debug(f"Skipping old task: {task_name} (completed at {completed_at_str})")
                                                continue
                                        except Exception as e:
                                            # Include task if timestamp parsing fails (be lenient)
                                            logger.debug(f"Could not parse task timestamp '{completed_at_str}': {e}, including task anyway")
                                            pass
                                    else:
                                        # No timestamp - always include (likely from current run)
                                        logger.debug(f"Including task without timestamp: {task_name}")
                                    
                                    # Include task if it passed all filters
                                    filtered_tasks.append(t)
                                
                                logger.debug(f"After filtering: {len(filtered_tasks)} tasks")
                                
                                # Use filtered tasks for display
                                # If filtering removed all tasks, use original tasks (fallback)
                                if not filtered_tasks and tasks:
                                    logger.warning(f"All {len(tasks)} tasks were filtered out, showing all tasks as fallback")
                                    filtered_tasks = tasks
                                
                                # Sort tasks by completion time (most recent first) or by duration (longest first) if no timestamp
                                def sort_key(task):
                                    completed_at = task.get("completed_at", "")
                                    if completed_at:
                                        try:
                                            task_time_str = completed_at.replace('Z', '+00:00')
                                            if '+' in task_time_str or task_time_str.endswith('Z'):
                                                task_time = datetime.fromisoformat(task_time_str)
                                                task_time_naive = task_time.replace(tzinfo=None) if task_time.tzinfo else task_time
                                            else:
                                                task_time_naive = datetime.fromisoformat(task_time_str)
                                            return task_time_naive
                                        except Exception:
                                            pass
                                    # Fallback: use duration for sorting (longest first)
                                    return datetime.min + timedelta(seconds=-task.get("duration_seconds", 0))
                                
                                filtered_tasks.sort(key=sort_key, reverse=True)
                                
                                tasks = filtered_tasks
                                
                                if not tasks:
                                    logger.debug("No tasks found in progress.json for timeline display")
                                    task_timing_html_final = f"<div style='padding: 10px; text-align: center; color: #666;'>No task timing data available. Found {len(progress_data.get('tasks_history', []))} tasks in file, but all were filtered out or empty.</div>"
                                else:
                                    total_time = sum(t.get("duration_seconds", 0) for t in tasks)
                                    
                                    # Find max duration for scaling progress bars
                                    max_duration = max((t.get("duration_seconds", 0) for t in tasks), default=1)
                                    
                                    html_parts = [
                                        "<div style='font-family: system-ui, -apple-system, sans-serif; font-size: 13px;'>",
                                        "<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border-radius: 8px 8px 0 0; margin-bottom: 0;'>",
                                        "<strong>⏱️ Task Execution Timeline</strong>",
                                        f"<span style='float: right; font-size: 11px; opacity: 0.9;'>Total: {total_time:.1f}s ({total_time/60:.1f} min)</span>",
                                        "</div>",
                                        "<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 8px 12px; margin: 0; font-size: 11px; color: #856404;'>",
                                        "<strong>ℹ️ Real Execution Data Only:</strong> Only tasks from tasks.yaml and actual wall-clock timing are shown. ",
                                        "Fake/placeholder tasks have been filtered out.",
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
                                        # Format display name (handle special cases)
                                        if task_name == "crew_execution":
                                            display_name = "Crew Execution (All Agents)"
                                        else:
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
                except Exception as e:
                    logger.error(f"Error loading task timing data for debug mode: {e}", exc_info=True)
                    task_timing_html_final = f"<div style='padding: 10px; text-align: center; color: #dc3545;'>Error loading timeline data: {str(e)}</div>"
            
            # Check for length trimming metadata and removal suggestions
            trimming_info = None
            removal_suggestions_text = None
            trimming_metadata_path = OUTPUT_DIR / "length_trimming_metadata.json"
            if trimming_metadata_path.exists():
                try:
                    with open(trimming_metadata_path, 'r', encoding='utf-8') as f:
                        trimming_data = json.load(f)
                        if trimming_data.get("status") == "success" and trimming_data.get("summary"):
                            trimming_info = trimming_data.get("summary", "")
                        
                        # Check for removal suggestions
                        removal_suggestions = trimming_data.get("removal_suggestions")
                        if removal_suggestions and removal_suggestions.get("removal_suggestions"):
                            suggestions = removal_suggestions.get("removal_suggestions", [])
                            estimated_pages = removal_suggestions.get("estimated_pages", 0)
                            target_pages = removal_suggestions.get("target_pages", 2.0)
                            
                            removal_suggestions_text = f"\n\n⚠️ Resume exceeds {target_pages}-page limit ({estimated_pages:.1f} pages). "
                            removal_suggestions_text += f"Removal suggestions ({len(suggestions)} items):\n"
                            for i, suggestion in enumerate(suggestions[:10], 1):  # Show top 10
                                item_type = suggestion.get("type", "item")
                                reason = suggestion.get("reason", "Low priority")
                                savings = suggestion.get("estimated_savings_lines", 0)
                                
                                if item_type == "experience":
                                    title = suggestion.get("title", "Unknown")
                                    removal_suggestions_text += f"  {i}. Remove experience: {title} ({reason}, saves ~{savings} lines)\n"
                                elif item_type == "project":
                                    name = suggestion.get("name", suggestion.get("title", "Unknown"))
                                    removal_suggestions_text += f"  {i}. Remove project: {name} ({reason}, saves ~{savings} lines)\n"
                                elif item_type == "bullet":
                                    parent = suggestion.get("parent", "Unknown")
                                    text_preview = suggestion.get("text", "")[:50]
                                    removal_suggestions_text += f"  {i}. Remove bullet from {parent}: \"{text_preview}...\" ({reason}, saves ~{savings} lines)\n"
                                elif item_type == "skill":
                                    skill = suggestion.get("skill", "Unknown")
                                    removal_suggestions_text += f"  {i}. Remove skill: {skill} ({reason})\n"
                            
                            if len(suggestions) > 10:
                                removal_suggestions_text += f"  ... and {len(suggestions) - 10} more suggestions\n"
                            
                            removal_suggestions_text += "\n💡 Tip: Use the chatbox to remove specific items based on these suggestions."
                except Exception as e:
                    logger.debug(f"Could not read length trimming metadata: {e}")
            
            # Build status message with refined info, trimming info, removal suggestions, and error messages
            status_message = "✅ Resume generated successfully!"
            if refined_info:
                status_message += "\n\n" + "\n".join(refined_info)
            if trimming_info:
                status_message += "\n\n" + trimming_info
            if removal_suggestions_text:
                status_message += removal_suggestions_text
            if error_message:
                status_message += "\n\n" + error_message
            
            yield {
                progress_status: gr.update(value=status_message),
                progress_bar: gr.update(value=100),
                download_section: gr.update(visible=True),
                adjustment_chat_section: gr.update(visible=True),
                ai_edit_section: gr.update(visible=True),
                task_timing_display: gr.update(
                    value=task_timing_html_final if task_timing_html_final else "<div style='padding: 10px; text-align: center; color: #666;'>Timing information not available</div>", 
                    visible=debug  # Only show timeline in debug mode
                ),
                pdf_preview: pdf_preview_html,
                cover_letter_preview: cover_letter_preview_html,
                pdf_file: pdf_absolute,
                tex_file: tex_file_path if tex_file_path else None,
                cover_letter_file: gr.update(value=cover_letter_absolute, visible=cover_letter_absolute is not None),
                status: gr.update(visible=bool(error_message), value=error_message if error_message else "")
            }
        
        def handle_adjustment(history, user_message, current_pdf, document_type="Resume", current_cover_letter_pdf=None, status_text="", current_pdf_preview="", current_cover_letter_preview=""):
            """Handle user adjustment requests by editing JSON files and regenerating LaTeX."""
            if not user_message.strip():
                return history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, "Please enter a request."
            
            try:
                import json
                
                # Initialize history if None (for messages format)
                if history is None:
                    history = []
                
                # Add user message to chat (messages format: {"role": "user", "content": "..."})
                history.append({"role": "user", "content": f"[{document_type}] {user_message}"})
                
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
                    required_json = OUTPUT_DIR / "summary.json"
                    doc_type_lower = "resume"
                
                # Check if JSON files exist (required for pipeline re-run)
                if not required_json.exists():
                    history.append({"role": "assistant", "content": f"❌ Error: Required JSON files not found. Please regenerate the {doc_type_lower} first."})
                    status_update = f"❌ Error: JSON files not found. Please generate the {doc_type_lower} first."
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                # Step 0: Detect and record design errors from user message
                try:
                    from resume_builder.design_error_memory import (
                        detect_design_error_in_message,
                        record_design_error
                    )
                    
                    detected_error = detect_design_error_in_message(user_message)
                    if detected_error:
                        record_design_error(
                            issue_description=detected_error["issue_description"],
                            context=detected_error["context"],
                            user_message=user_message,
                            section=detected_error["context"]
                        )
                        logger.info(f"Detected and recorded design error: {detected_error['issue_description']} in {detected_error['context']}")
                except Exception as e:
                    logger.debug(f"Design error detection failed: {e}")
                    # Continue anyway - don't break the edit flow
                
                # Step 1: Apply edit request to JSON files using edit_engine
                status_update = f"📝 Applying edit to JSON files..."
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                
                from resume_builder.edit_engine import apply_edit_request
                
                edit_result = apply_edit_request(user_message)
                
                if not edit_result.get("ok"):
                    reason = edit_result.get("reason", "Unknown error")
                    history.append({"role": "assistant", "content": f"❌ Could not apply edit: {reason}"})
                    status_update = f"❌ Edit not possible: {reason}"
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
                changed_fields = edit_result.get("changed_fields", [])
                if not changed_fields:
                    history.append({"role": "assistant", "content": f"ℹ️ No changes were made. The {doc_type_lower} may already match your request."})
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
                summary_json = OUTPUT_DIR / "summary.json"
                experience_json = OUTPUT_DIR / "selected_experiences.json"
                education_json = OUTPUT_DIR / "education.json"
                skills_json = OUTPUT_DIR / "selected_skills.json"
                projects_json = OUTPUT_DIR / "selected_projects.json"  # Optional
                header_json = OUTPUT_DIR / "header.json"  # Optional
                
                # Check required files exist
                required_files = {
                    "user_profile.json": identity_json,
                    "summary.json": summary_json,
                    "selected_experiences.json": experience_json,
                    "selected_skills.json": skills_json,
                }
                
                missing_files = []
                for name, file_path in required_files.items():
                    if not file_path.exists():
                        missing_files.append(name)
                
                if missing_files:
                    history.append({"role": "assistant", "content": f"❌ Error: Required JSON files missing: {', '.join(missing_files)}. Please regenerate the {doc_type_lower} first."})
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
                            
                            # Update preview (using helper function)
                            import time
                            time.sleep(0.1)
                            updated_cover_letter_preview = create_pdf_preview_html(
                                Path(updated_cover_letter_pdf), 
                                "Cover Letter PDF"
                            )
                            
                            history.append({"role": "assistant", "content": f"✅ Cover letter updated and regenerated successfully! Changed fields: {', '.join(changed_fields)}"})
                            yield history, "", current_pdf, current_pdf_preview, updated_cover_letter_pdf, updated_cover_letter_preview, status_update
                            return
                        else:
                            history.append({"role": "assistant", "content": f"❌ Error: Failed to regenerate cover letter PDF."})
                            status_update = f"❌ Error: PDF generation failed."
                            yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                    else:
                        # Resume: regenerate LaTeX and compile
                        rendered_tex = RENDERED_TEX
                        
                        # Use rebuild helper if available, otherwise use direct call
                        try:
                            from resume_builder.latex_builder import rebuild_resume_from_existing_json
                            rendered_tex = rebuild_resume_from_existing_json(
                                output_dir=OUTPUT_DIR,
                                template_path=None,
                                rendered_tex_path=rendered_tex
                            )
                        except ImportError:
                            # Fallback to direct call
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
                            
                            # Update preview (using helper function)
                            updated_preview = create_pdf_preview_html(
                                Path(updated_pdf_path), 
                                f"{document_type} PDF"
                            )
                            updated_pdf = updated_pdf_path
                            
                            history.append({"role": "assistant", "content": f"✅ {document_type} updated and regenerated successfully! Changed fields: {', '.join(changed_fields)}. The PDF preview has been refreshed."})
                            yield history, "", updated_pdf, updated_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                        else:
                            error_info = ""
                            if isinstance(compile_result, dict):
                                error_info = compile_result.get("error", "Unknown error")
                            history.append({"role": "assistant", "content": f"⚠️ {document_type} JSON was updated but PDF compilation failed:\n{error_info}\n\nCheck compile.log for details."})
                            status_update = f"⚠️ Compilation failed. Check compile.log for details."
                            yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                            return
                            
                except Exception as e:
                    logger.error(f"[ADJUSTMENT] Error regenerating {document_type}: {e}", exc_info=True)
                    history.append({"role": "assistant", "content": f"❌ Error regenerating {document_type}: {str(e)}\n\nPlease check the logs for more details."})
                    status_update = f"❌ Error: {str(e)[:100]}"
                    yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                    return
                
            except Exception as e:
                error_msg = f"❌ Error processing adjustment: {str(e)}"
                logger.error(error_msg, exc_info=True)
                if len(history) > 0:
                    history.append({"role": "assistant", "content": f"{error_msg}\n\nPlease check the logs for more details or try a more specific request."})
                else:
                    history.append({"role": "user", "content": user_message})
                    history.append({"role": "assistant", "content": error_msg})
                status_update = f"❌ Error occurred: {str(e)[:100]}"
                yield history, "", current_pdf, current_pdf_preview, current_cover_letter_pdf or None, current_cover_letter_preview, status_update
                return
        
        async def handle_ai_preview(section, instruction, strict, debug=False, progress=gr.Progress()):
            """Preview AI edit without saving changes."""
            if not instruction or not instruction.strip():
                return "⚠️ Please provide an instruction.", ""
            
            try:
                progress(0.0, desc="Analyzing edit request with AI...")
                
                from resume_builder.edit_engine_llm_json import apply_llm_json_edit
                
                # Auto-enable strict mode for simple character removal operations
                instruction_lower = instruction.lower()
                is_simple_removal = (
                    ("remove" in instruction_lower or "delete" in instruction_lower) and
                    ("pipe" in instruction_lower or "|" in instruction or "character" in instruction_lower) and
                    not any(word in instruction_lower for word in ["section", "field", "item", "experience", "project", "skill"])
                )
                effective_strict = bool(strict) or is_simple_removal
                
                result = apply_llm_json_edit(
                    section=section,
                    user_instruction=instruction,
                    strict=effective_strict,
                    dry_run=True,
                )
                
                if result.get("status") != "ok":
                    msg = f"❌ AI preview failed for section '{section}': {result.get('message', 'Unknown error')}"
                    progress(1.0, desc="Preview failed.")
                    return msg, ""
                
                # Build status message
                diff_meta = result.get("diff_meta") or {}
                warnings = result.get("warnings") or []
                diff_text = warnings[0] if warnings else "No changes detected."
                
                status_line = (
                    f"✅ **Preview successful** for section '{section}'. "
                    f"**No changes saved.**\n\n"
                    f"**Changes:** Modified: {diff_meta.get('modified_count', 0)}, "
                    f"Added: {diff_meta.get('added_count', 0)}, "
                    f"Removed: {diff_meta.get('removed_count', 0)}.\n\n"
                    f"*Click 'Apply AI Edit' to save these changes.*"
                )
                
                progress(1.0, desc="Preview ready.")
                return status_line, diff_text
                
            except Exception as e:
                error_msg = f"❌ Error during AI preview: {str(e)}"
                logger.error(f"AI preview error: {e}", exc_info=True)
                return error_msg, ""
        
        async def handle_ai_apply(section, instruction, strict, debug=False, progress=gr.Progress()):
            """Apply AI edit: save JSON, rebuild LaTeX, compile PDF."""
            if not instruction or not instruction.strip():
                return "⚠️ Please provide an instruction before applying.", "", None, ""
            
            try:
                progress(0.0, desc="Applying AI edit...")
                
                from resume_builder.edit_engine_llm_json import apply_llm_json_edit
                
                # Auto-enable strict mode for simple character removal operations
                instruction_lower = instruction.lower()
                is_simple_removal = (
                    ("remove" in instruction_lower or "delete" in instruction_lower) and
                    ("pipe" in instruction_lower or "|" in instruction or "character" in instruction_lower) and
                    not any(word in instruction_lower for word in ["section", "field", "item", "experience", "project", "skill"])
                )
                effective_strict = bool(strict) or is_simple_removal
                
                if is_simple_removal and not strict:
                    logger.info(f"Auto-enabling strict mode for simple character removal operation")
                
                result = apply_llm_json_edit(
                    section=section,
                    user_instruction=instruction,
                    strict=effective_strict,
                    dry_run=False,
                )
                
                if result.get("status") != "ok":
                    msg = f"❌ Failed to apply AI edit for section '{section}': {result.get('message', 'Unknown error')}"
                    progress(1.0, desc="Apply failed.")
                    return msg, "", None, ""
                
                progress(0.4, desc="Rebuilding resume from updated JSON...")
                
                from resume_builder.latex_builder import rebuild_resume_from_existing_json
                from resume_builder.paths import OUTPUT_DIR, GENERATED_DIR, TEMPLATES
                
                rendered_tex = rebuild_resume_from_existing_json(
                    output_dir=OUTPUT_DIR,
                    template_path=TEMPLATES / "main.tex",
                    rendered_tex_path=GENERATED_DIR / "rendered_resume.tex"
                )
                
                progress(0.7, desc="Compiling updated PDF...")
                
                from resume_builder.tools.latex_compile import LatexCompileTool
                compile_tool = LatexCompileTool()
                pdf_path = OUTPUT_DIR / "generated" / "final_resume.pdf"
                
                compile_result = compile_tool._run(
                    tex_path=str(rendered_tex),
                    out_name="final_resume.pdf"
                )
                
                compile_success = (
                    isinstance(compile_result, dict) and compile_result.get("success", False)
                ) or pdf_path.exists()
                
                if not compile_success:
                    error_info = compile_result.get("error", "Unknown error") if isinstance(compile_result, dict) else "Compilation failed"
                    msg = f"⚠️ JSON updated but PDF compilation failed: {error_info}"
                    progress(1.0, desc="Compilation failed.")
                    return msg, "", None, ""
                
                # Build status message
                diff_meta = result.get("diff_meta") or {}
                warnings = result.get("warnings") or []
                diff_text = warnings[0] if warnings else "Changes applied."
                
                status_line = (
                    f"✅ **AI edit applied** for section '{section}'. "
                    f"JSON updated, LaTeX rebuilt, PDF compiled.\n\n"
                    f"**Changes:** Modified: {diff_meta.get('modified_count', 0)}, "
                    f"Added: {diff_meta.get('added_count', 0)}, "
                    f"Removed: {diff_meta.get('removed_count', 0)}."
                )
                
                # Update PDF preview
                import time
                time.sleep(0.1)  # Small delay to ensure file is written
                updated_preview = create_pdf_preview_html(
                    pdf_path,
                    "Resume PDF"
                )
                
                progress(1.0, desc="AI edit applied and PDF rebuilt.")
                
                return status_line, diff_text, str(pdf_path.resolve()), updated_preview
                
            except Exception as e:
                error_msg = f"❌ Error during AI apply: {str(e)}"
                logger.error(f"AI apply error: {e}", exc_info=True)
                # Return empty preview HTML on error
                empty_preview = "<div style='padding: 20px; text-align: center; color: #666;'>Error occurred. Please try again.</div>"
                return error_msg, "", None, empty_preview
        
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
        
        # Wire AI edit handlers
        ai_preview_btn.click(
            handle_ai_preview,
            inputs=[ai_section_dropdown, ai_instruction_text, ai_strict_checkbox, debug_mode],
            outputs=[ai_status_output, ai_diff_output],
        )
        
        ai_apply_btn.click(
            handle_ai_apply,
            inputs=[ai_section_dropdown, ai_instruction_text, ai_strict_checkbox, debug_mode],
            outputs=[ai_status_output, ai_diff_output, pdf_file, pdf_preview],
        )
        
        generate_btn.click(
            handle_generate,
            inputs=[jd_text, files_upload, debug_mode, fast_mode, enable_ats, enable_privacy, enable_cover_letter],
            outputs=[progress_status, progress_bar, download_section, adjustment_chat_section, ai_edit_section, task_timing_display, pdf_preview, cover_letter_preview, pdf_file, tex_file, cover_letter_file, status],
            # Disable automatic progress completely - we use manual slider instead
            show_progress=False
        )
        
        # Custom CSS to improve layout
        demo.css = """
        .gradio-container { 
            max-width: 1400px !important; 
            margin: 0 auto;
        }
        /* Explicitly show Gradio's progress container + bar */
        .gradio-progress {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            margin: 12px 0 !important;
            padding: 8px !important;
            position: relative !important;
            z-index: 20 !important;
        }
        .gr-progress-bar {
            display: block !important;
            height: 18px !important;
            max-height: 18px !important;
            border-radius: 6px !important;
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

