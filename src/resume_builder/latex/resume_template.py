"""
LaTeX template generation for resume sections.

This module contains functions to generate LaTeX code for resume sections
from normalized JSON data.
"""

from __future__ import annotations

import re
from typing import Dict, List, Any, Optional

from resume_builder.latex.core import escape_latex, format_phone, format_url


def build_preamble(identity: Dict[str, Any]) -> str:
    """Build LaTeX preamble with identity commands for ModernCV/resumecv templates.
    
    Hard-requires: email, phone
    Optional: website, linkedin, github (skip cleanly if missing)
    """
    preamble_parts = []
    
    # Use \name{First}{Last} instead of \firstname/\familyname (ModernCV/resumecv standard)
    first = escape_latex(identity.get('first', '')).strip()
    last = escape_latex(identity.get('last', '')).strip()
    if first or last:
        preamble_parts.append(f"\\name{{{first}}}{{{last}}}")
    
    # HARD-REQUIRED: email and phone (must be present)
    email = identity.get('email', '').strip() if identity.get('email') else ''
    phone = identity.get('phone', '').strip() if identity.get('phone') else ''
    
    # Emit email and phone (required fields)
    if email:
        escaped_email = escape_latex(email)
        preamble_parts.append(f"\\email{{{escaped_email}}}")
    
    if phone:
        phone_formatted = format_phone(phone)
        preamble_parts.append(f"\\phone{{{phone_formatted}}}")
    
    # Optional: address
    # Check for location (new) or address (old) for backward compatibility
    location = identity.get('location', '').strip() if identity.get('location') else ''
    if not location:
        location = identity.get('address', '').strip() if identity.get('address') else ''
    if location:
        escaped_location = escape_latex(location)
        preamble_parts.append(f"\\address{{{escaped_location}}}")
    
    # Optional: website (skip cleanly if missing)
    site = identity.get('website', '').strip() if identity.get('website') else ''
    if site:
        url = format_url(site)
        preamble_parts.append(f"\\homepage{{{url}}}")
    
    # Optional: LinkedIn (skip cleanly if missing)
    linkedin = identity.get('linkedin', '').strip() if identity.get('linkedin') else ''
    if linkedin:
        # Extract username if full URL provided
        linkedin_lower = linkedin.lower()
        match = re.search(r'linkedin\.com/(?:in|pub)/([^/?]+)', linkedin_lower)
        if match:
            original_match = re.search(r'linkedin\.com/(?:in|pub)/([^/?]+)', linkedin, re.IGNORECASE)
            if original_match:
                linkedin = original_match.group(1).strip('/')
        preamble_parts.append(f"\\social[linkedin]{{{linkedin}}}")
    
    # Optional: GitHub (skip cleanly if missing)
    github = identity.get('github', '').strip() if identity.get('github') else ''
    if github:
        # Extract username if full URL provided
        github_lower = github.lower()
        match = re.search(r'github\.com/([^/?]+)', github_lower)
        if match:
            original_match = re.search(r'github\.com/([^/?]+)', github, re.IGNORECASE)
            if original_match:
                github = original_match.group(1).split('/')[0].strip('/')
        preamble_parts.append(f"\\social[github]{{{github}}}")
    
    return '\n'.join(preamble_parts)


def build_header(title_line: str, contact_info: Dict[str, Any]) -> str:
    """Build tailored header section with title line and contact information table.
    
    Args:
        title_line: Job-relevant keywords separated by pipes (e.g., "AI/ML Engineer | Robotics & Agentic AI")
        contact_info: Dictionary with phone, email, location, website, linkedin, github, google_scholar
        
    Returns:
        LaTeX code for header section matching user's format exactly
    """
    parts = []
    
    # Title line (centered, bold) - replace | with \textbar{} for LaTeX
    if title_line:
        title_escaped = title_line.replace('|', '\\textbar{}')
        title_escaped = escape_latex(title_escaped, keep_commands=True)
        parts.append(f"\\begin{{center}} \\textbf{{{title_escaped}}} \\end{{center}}")
    
    # Contact information table - 4 columns exactly as in user's example
    row1_parts = []
    row2_parts = []
    
    # Row 1: Phone (col 1), Email (cols 2-3 with multicolumn), Location (col 4)
    phone = contact_info.get('phone', '').strip()
    email = contact_info.get('email', '').strip()
    location = contact_info.get('location', '').strip()
    
    if phone:
        formatted_phone = format_phone(phone)
        row1_parts.append(f"\\enspace\\faMobile\\enspace {escape_latex(formatted_phone)}")
    
    if email:
        escaped_email = escape_latex(email)
        row1_parts.append(f"\\multicolumn{{2}}{{c}} {{$\\mathbb{{E}}$}}\\enspace {{{escaped_email}}}")
    
    if location:
        escaped_location = escape_latex(location)
        row1_parts.append(f"\\enspace\\faHome\\enspace {escaped_location}")
    
    # Row 2: Website, LinkedIn, GitHub, Google Scholar (1 col each)
    website = contact_info.get('website', '').strip()
    linkedin = contact_info.get('linkedin', '').strip()
    github = contact_info.get('github', '').strip()
    google_scholar = contact_info.get('google_scholar', '').strip()
    
    if website:
        website_url = format_url(website)
        row2_parts.append(f"\\color{{blue}} {{$\\mathbb{{W}}$}} \\href{{{website_url}}}{{Personal Website}}")
    
    if linkedin:
        linkedin_url = f"https://www.linkedin.com/in/{linkedin}"
        row2_parts.append(f"\\enspace\\faLinkedin\\enspace \\color{{blue}} \\href{{{linkedin_url}}}{{{escape_latex(linkedin)}}}")
    
    if github:
        github_url = f"https://github.com/{github}"
        row2_parts.append(f"\\enspace\\faGithub\\enspace \\color{{blue}} \\href{{{github_url}}}{{{escape_latex(github)}}}")
    
    if google_scholar:
        scholar_url = format_url(google_scholar)
        row2_parts.append(f"{{$\\mathbb{{G}}$}}\\enspace \\color{{blue}} \\href{{{scholar_url}}}{{Google Scholar}}")
    
    # Build table - always 4 columns to match user's format
    if row1_parts or row2_parts:
        table_content = []
        if row1_parts:
            while len(row1_parts) < 4:
                row1_parts.append('')
            row1_str = ' & '.join(row1_parts[:4]) + ' \\\\'
            table_content.append(row1_str)
            table_content.append("\\hline")
        
        if row2_parts:
            while len(row2_parts) < 4:
                row2_parts.append('')
            row2_str = ' & '.join(row2_parts[:4]) + ' \\\\'
            table_content.append(row2_str)
        
        table_latex = f"\\begin{{center}}\\begin{{tabular}}{{ c c c c }}\n" + "\n".join(table_content) + "\n\\end{{tabular}}\\end{{center}}"
        # Fix double braces issue: replace {{ with { and }} with } for tabular/center tags
        table_latex = table_latex.replace("\\end{{tabular}}", "\\end{tabular}").replace("\\end{{center}}", "\\end{center}")
        parts.append(table_latex)
    
    return "\n".join(parts) if parts else ""


def build_summary(summary: str) -> str:
    """Build summary section."""
    if not summary:
        return ""
    
    escaped = escape_latex(summary, keep_commands=True)
    return f"\\section*{{Summary}}\n{escaped}\n"


def build_experience_entry(exp: Dict[str, Any]) -> str:
    """Build a single experience entry using cventry."""
    title = escape_latex(exp.get('title', ''))
    organization = escape_latex(exp.get('organization', ''))
    location = escape_latex(exp.get('location', ''))
    dates = escape_latex(exp.get('dates', ''))
    
    # Build description with bullet points - allow LaTeX commands in descriptions
    description_lines = []
    if 'description' in exp and exp['description']:
        if isinstance(exp['description'], list):
            for item in exp['description']:
                escaped_item = escape_latex(item, keep_commands=True)
                description_lines.append(f"  \\item {escaped_item}")
        else:
            escaped_desc = escape_latex(exp['description'], keep_commands=True)
            description_lines.append(f"  \\item {escaped_desc}")
    
    if description_lines:
        description = "\\begin{itemize}[leftmargin=*,labelsep=0.5em,itemsep=0pt]\n" + \
                     '\n'.join(description_lines) + "\n\\end{itemize}"
    else:
        description = ""
    
    if description:
        return f"\\cventry{{{dates}}}{{{title}}}{{{organization}}}{{{location}}}{{}}{{{description}}}\n"
    else:
        return f"\\cventry{{{dates}}}{{{title}}}{{{organization}}}{{{location}}}{{}}{{}}\n"


def build_experience_section(experiences: List[Dict[str, Any]], max_entries_per_page: Optional[int] = None) -> str:
    """Build complete experience section with optional page breaks."""
    if not experiences:
        return ""
    
    entries = [build_experience_entry(exp) for exp in experiences]
    
    # Add page breaks if specified
    if max_entries_per_page and len(entries) > max_entries_per_page:
        result = ["\\section*{Experience}\n"]
        for i, entry in enumerate(entries):
            result.append(entry)
            if (i + 1) % max_entries_per_page == 0 and i < len(entries) - 1:
                result.append("\\pagebreak[2]\n")
        return ''.join(result)
    
    return "\\section*{Experience}\n" + '\n'.join(entries)


def build_education_entry(edu: Dict[str, Any]) -> str:
    """Build a single education entry."""
    degree = escape_latex(edu.get('degree', ''))
    institution = escape_latex(edu.get('institution', ''))
    location = escape_latex(edu.get('location', ''))
    dates = escape_latex(edu.get('dates', ''))
    
    # Optional: GPA, honors, etc.
    details = []
    if edu.get('gpa'):
        details.append(f"GPA: {edu['gpa']}")
    if edu.get('honors'):
        details.append(escape_latex(edu['honors']))
    
    description = ', '.join(details) if details else ''
    
    return f"\\cventry{{{dates}}}{{{degree}}}{{{institution}}}{{{location}}}{{}}{{{description}}}\n"


def build_education_section(education: List[Dict[str, Any]]) -> str:
    """Build complete education section."""
    if not education:
        return ""
    
    entries = [build_education_entry(edu) for edu in education]
    return "\\section*{Education}\n" + '\n'.join(entries)


def build_skills_section(skills: List[str]) -> str:
    """Build skills section."""
    if not skills:
        return ""
    
    escaped_skills = [escape_latex(skill) for skill in skills]
    skills_text = ', '.join(escaped_skills)
    
    return f"\\section*{{Skills}}\n\\begin{{sloppypar}}{skills_text}\\end{{sloppypar}}\n"


def build_projects_section(projects: List[Dict[str, Any]], max_entries_per_page: Optional[int] = None) -> str:
    """Build projects section with optional page breaks."""
    if not projects:
        return ""
    
    entries = []
    for proj in projects:
        name = escape_latex(proj.get('name', ''), keep_commands=True)
        description = escape_latex(proj.get('description', ''), keep_commands=True)
        url = proj.get('url', '')
        
        if url:
            url_formatted = format_url(url)
            name_with_link = f"\\href{{{url_formatted}}}{{{name}}}"
        else:
            name_with_link = name
        
        name_display = name_with_link if re.search(r'\\[a-zA-Z]+', name_with_link) else f"\\textbf{{{name_with_link}}}"
        entries.append(f"\\cvitem{{~}}{{{name_display}: {description}}}\n")
    
    # Add page breaks if specified
    if max_entries_per_page and len(entries) > max_entries_per_page:
        result = ["\\section*{Projects}\n"]
        for i, entry in enumerate(entries):
            result.append(entry)
            if (i + 1) % max_entries_per_page == 0 and i < len(entries) - 1:
                result.append("\\pagebreak[2]\n")
        return ''.join(result)
    
    return "\\section*{Projects}\n" + ''.join(entries)

