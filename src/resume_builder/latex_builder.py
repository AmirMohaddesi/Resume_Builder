"""
Python-based LaTeX generator for resumes.
Agents output JSON, Python handles all LaTeX syntax.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from jinja2 import Template


class LaTeXBuilder:
    """Builds LaTeX resume from JSON data with proper escaping and validation."""
    
    @staticmethod
    def escape_latex(text: str) -> str:
        """Escape special LaTeX characters."""
        if not text:
            return ""
        
        # LaTeX special characters that need escaping
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
            '\\': r'\textbackslash{}',
        }
        
        # Apply replacements
        result = text
        for char, replacement in replacements.items():
            result = result.replace(char, replacement)
        
        return result
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number for display."""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone  # Return as-is if format is unclear
    
    @staticmethod
    def format_url(url: str) -> str:
        """Clean and format URL for LaTeX hyperref."""
        if not url:
            return ""
        
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
    def build_preamble(self, identity: Dict[str, Any]) -> str:
        """Build LaTeX preamble with identity commands."""
        preamble_parts = []
        
        # Required fields
        if identity.get('first'):
            preamble_parts.append(f"\\firstname{{{identity['first']}}}")
        if identity.get('last'):
            preamble_parts.append(f"\\familyname{{{identity['last']}}}")
        
        # Optional contact info
        if identity.get('email'):
            preamble_parts.append(f"\\email{{{identity['email']}}}")
        
        if identity.get('phone'):
            phone = self.format_phone(identity['phone'])
            preamble_parts.append(f"\\phone{{{phone}}}")
        
        if identity.get('address'):
            addr = self.escape_latex(identity['address'])
            preamble_parts.append(f"\\address{{{addr}}}")
        
        # Social links
        social_parts = []
        if identity.get('website'):
            url = self.format_url(identity['website'])
            social_parts.append(f"\\homepage{{{url}}}")
        
        if identity.get('linkedin'):
            linkedin = identity['linkedin']
            # Extract username if full URL provided
            if 'linkedin.com/in/' in linkedin:
                linkedin = linkedin.split('linkedin.com/in/')[-1].strip('/')
            social_parts.append(f"\\social[linkedin]{{{linkedin}}}")
        
        if identity.get('github'):
            github = identity['github']
            # Extract username if full URL provided
            if 'github.com/' in github:
                github = github.split('github.com/')[-1].strip('/')
            social_parts.append(f"\\social[github]{{{github}}}")
        
        preamble_parts.extend(social_parts)
        
        return '\n'.join(preamble_parts)
    
    def build_summary(self, summary: str) -> str:
        """Build summary section."""
        if not summary:
            return ""
        
        escaped = self.escape_latex(summary)
        return f"\\section{{Summary}}\n{escaped}\n"
    
    def build_experience_entry(self, exp: Dict[str, Any]) -> str:
        """Build a single experience entry using cventry."""
        title = self.escape_latex(exp.get('title', ''))
        organization = self.escape_latex(exp.get('organization', ''))
        location = self.escape_latex(exp.get('location', ''))
        dates = self.escape_latex(exp.get('dates', ''))
        
        # Build description with bullet points
        description_lines = []
        if 'description' in exp and exp['description']:
            if isinstance(exp['description'], list):
                for item in exp['description']:
                    escaped_item = self.escape_latex(item)
                    description_lines.append(f"  \\item {escaped_item}")
            else:
                # Single string description
                escaped_desc = self.escape_latex(exp['description'])
                description_lines.append(f"  \\item {escaped_desc}")
        
        if description_lines:
            description = "\\begin{itemize}[leftmargin=*,labelsep=0.5em,itemsep=0pt]\n" + \
                         '\n'.join(description_lines) + "\n\\end{itemize}"
        else:
            description = ""
        
        # cventry format: {dates}{title}{organization}{location}{description}
        return f"\\cventry{{{dates}}}{{{title}}}{{{organization}}}{{{location}}}{{}}{{\n{description}\n}}\n"
    
    def build_experience_section(self, experiences: List[Dict[str, Any]]) -> str:
        """Build complete experience section."""
        if not experiences:
            return ""
        
        entries = [self.build_experience_entry(exp) for exp in experiences]
        return "\\section{Experience}\n" + '\n'.join(entries)
    
    def build_education_entry(self, edu: Dict[str, Any]) -> str:
        """Build a single education entry."""
        degree = self.escape_latex(edu.get('degree', ''))
        institution = self.escape_latex(edu.get('institution', ''))
        location = self.escape_latex(edu.get('location', ''))
        dates = self.escape_latex(edu.get('dates', ''))
        
        # Optional: GPA, honors, etc.
        details = []
        if edu.get('gpa'):
            details.append(f"GPA: {edu['gpa']}")
        if edu.get('honors'):
            details.append(self.escape_latex(edu['honors']))
        
        description = ', '.join(details) if details else ''
        
        return f"\\cventry{{{dates}}}{{{degree}}}{{{institution}}}{{{location}}}{{}}{{{description}}}\n"
    
    def build_education_section(self, education: List[Dict[str, Any]]) -> str:
        """Build complete education section."""
        if not education:
            return ""
        
        entries = [self.build_education_entry(edu) for edu in education]
        return "\\section{Education}\n" + '\n'.join(entries)
    
    def build_skills_section(self, skills: List[str]) -> str:
        """Build skills section."""
        if not skills:
            return ""
        
        # Group skills into a compact format
        escaped_skills = [self.escape_latex(skill) for skill in skills]
        skills_text = ', '.join(escaped_skills)
        
        return f"\\section{{Skills}}\n{skills_text}\n"
    
    def build_projects_section(self, projects: List[Dict[str, Any]]) -> str:
        """Build projects section."""
        if not projects:
            return ""
        
        entries = []
        for proj in projects:
            name = self.escape_latex(proj.get('name', ''))
            description = self.escape_latex(proj.get('description', ''))
            url = proj.get('url', '')
            
            if url:
                url_formatted = self.format_url(url)
                name_with_link = f"\\href{{{url_formatted}}}{{{name}}}"
            else:
                name_with_link = name
            
            entries.append(f"\\cvitem{{{name_with_link}}}{{{description}}}\n")
        
        return "\\section{Projects}\n" + ''.join(entries)
    
    def _ensure_required_packages(self, latex_content: str) -> str:
        """
        Automatically add required packages if they're used but not included.
        Detects \mathbb commands and FontAwesome icons.
        """
        # Check if \mathbb is used
        needs_amssymb = bool(re.search(r'\\mathbb\{', latex_content))
        has_amssymb = bool(re.search(r'\\usepackage.*\{amssymb\}', latex_content))
        
        # Check if FontAwesome is used
        needs_fontawesome = bool(re.search(r'\\fa[A-Z][a-zA-Z]*', latex_content))
        has_fontawesome = bool(re.search(r'\\usepackage.*\{fontawesome', latex_content))
        
        # Also check for commented-out fontawesome5 (handle various comment patterns)
        if not has_fontawesome:
            # Pattern 1: % \usepackage{fontawesome5} (comment on same line)
            if re.search(r'%\s*\\usepackage.*\{fontawesome5\}', latex_content):
                latex_content = re.sub(
                    r'%\s*(\\usepackage.*\{fontawesome5\})',
                    r'\1',
                    latex_content
                )
                has_fontawesome = True
            # Pattern 2: % on separate line before \usepackage{fontawesome5}
            elif re.search(r'%\s*.*\n\s*%\s*\\usepackage.*\{fontawesome5\}', latex_content, re.MULTILINE):
                # Uncomment the usepackage line (remove the % before \usepackage)
                latex_content = re.sub(
                    r'%\s*(\\usepackage.*\{fontawesome5\})',
                    r'\1',
                    latex_content,
                    flags=re.MULTILINE
                )
                has_fontawesome = True
        
        # Find the position to insert packages (after \usepackage{hyperref} or similar)
        insert_pos = -1
        hyperref_match = re.search(r'\\usepackage.*\{hyperref\}', latex_content)
        if hyperref_match:
            insert_pos = hyperref_match.end()
        else:
            # Find last \usepackage
            last_usepackage = list(re.finditer(r'\\usepackage', latex_content))
            if last_usepackage:
                insert_pos = last_usepackage[-1].end()
                # Find the end of that package line
                next_newline = latex_content.find('\n', insert_pos)
                if next_newline != -1:
                    insert_pos = next_newline
        
        # Insert missing packages
        packages_to_add = []
        if needs_amssymb and not has_amssymb:
            packages_to_add.append('\\usepackage{amssymb}')
        if needs_fontawesome and not has_fontawesome:
            # Use fontawesome5 with microtype disabled to avoid font expansion issues
            packages_to_add.append('\\usepackage{fontawesome5}')
            # Disable microtype font expansion if it's causing issues
            if re.search(r'\\usepackage.*\{microtype\}', latex_content):
                # Add microtype config to disable expansion
                microtype_match = re.search(r'\\usepackage.*\{microtype\}', latex_content)
                if microtype_match:
                    microtype_line = latex_content[microtype_match.start():microtype_match.end()]
                    if 'expansion' not in microtype_line:
                        # Replace microtype with version that disables expansion
                        latex_content = latex_content.replace(
                            microtype_line,
                            microtype_line.replace('}', '[expansion=false]}')
                        )
        
        if packages_to_add and insert_pos != -1:
            packages_str = '\n' + '\n'.join(packages_to_add)
            latex_content = latex_content[:insert_pos] + packages_str + latex_content[insert_pos:]
        elif packages_to_add:
            # Fallback: add after documentclass
            docclass_match = re.search(r'\\documentclass.*\n', latex_content)
            if docclass_match:
                insert_pos = docclass_match.end()
                packages_str = '\n' + '\n'.join(packages_to_add) + '\n'
                latex_content = latex_content[:insert_pos] + packages_str + latex_content[insert_pos:]
        
        # Fix font expansion issue with FontAwesome
        # If fontawesome5 is used, disable font expansion to avoid pdfTeX errors
        if needs_fontawesome:
            # Check if microtype is loaded
            if re.search(r'\\usepackage.*\{microtype\}', latex_content):
                # Disable expansion in microtype
                latex_content = re.sub(
                    r'\\usepackage(\[.*?\])?\{microtype\}',
                    r'\\usepackage[expansion=false]{microtype}',
                    latex_content
                )
            else:
                # Add microtype with expansion disabled to prevent conflicts
                # Find where to insert (after fontawesome5)
                fa_match = re.search(r'\\usepackage.*\{fontawesome5\}', latex_content)
                if fa_match:
                    insert_after_fa = fa_match.end()
                    latex_content = latex_content[:insert_after_fa] + '\n\\DisableLigatures{encoding = *, family = * }' + latex_content[insert_after_fa:]
            
            # Add command to disable font expansion globally to fix MiKTeX font expansion error
            # This prevents pdfTeX from trying to expand FontAwesome fonts (which aren't scalable)
            if '\\pdfprotrudechars' not in latex_content:
                # Add before \begin{document}
                doc_start = latex_content.find('\\begin{document}')
                if doc_start != -1:
                    # Disable font expansion globally
                    disable_expansion = '\n% Disable font expansion to fix FontAwesome compatibility with MiKTeX\n\\pdfprotrudechars=0\n\\pdfadjustspacing=0\n'
                    latex_content = latex_content[:doc_start] + disable_expansion + latex_content[doc_start:]
        
        return latex_content
    
    def build_complete_resume(
        self,
        identity: Dict[str, Any],
        summary: str,
        experiences: List[Dict[str, Any]],
        education: List[Dict[str, Any]],
        skills: List[str],
        projects: Optional[List[Dict[str, Any]]] = None,
        template_path: Optional[Path] = None
    ) -> str:
        """Build complete LaTeX resume from JSON components."""
        
        # Build all sections
        preamble = self.build_preamble(identity)
        summary_section = self.build_summary(summary)
        experience_section = self.build_experience_section(experiences)
        education_section = self.build_education_section(education)
        skills_section = self.build_skills_section(skills)
        projects_section = self.build_projects_section(projects) if projects else ""
        
        # Use template if provided, otherwise use default
        if template_path and template_path.exists():
            template_content = template_path.read_text(encoding='utf-8')
        else:
            template_content = self._get_default_template()
        
        # Replace markers
        latex = template_content
        latex = latex.replace('% === AUTO:PREAMBLE ===', preamble)
        latex = latex.replace('% === AUTO:SUMMARY ===', summary_section)
        latex = latex.replace('% === AUTO:EXPERIENCE ===', experience_section)
        latex = latex.replace('% === AUTO:EDUCATION ===', education_section)
        latex = latex.replace('% === AUTO:SKILLS ===', skills_section)
        
        # Handle projects (might be under ACHIEVEMENTS or ADDITIONAL)
        if projects_section:
            if '% === AUTO:ACHIEVEMENTS ===' in latex:
                latex = latex.replace('% === AUTO:ACHIEVEMENTS ===', projects_section)
            elif '% === AUTO:ADDITIONAL ===' in latex:
                latex = latex.replace('% === AUTO:ADDITIONAL ===', projects_section)
        
        # Remove any remaining markers
        latex = re.sub(r'% === AUTO:\w+ ===', '', latex)
        
        # Automatically add required packages if needed
        latex = self._ensure_required_packages(latex)
        
        return latex
    
    def _get_default_template(self) -> str:
        """Return default moderncv template."""
        return r"""\documentclass[11pt,a4paper,sans]{moderncv}
\moderncvstyle{banking}
\moderncvcolor{black}
\nopagenumbers{}
\usepackage[utf8]{inputenc}
\usepackage[scale=0.915]{geometry}
\usepackage{ragged2e}
\usepackage{multicol}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{fontawesome5}
\usepackage{amssymb}

% === AUTO:PREAMBLE ===

\begin{document}
\makecvtitle

% === AUTO:SUMMARY ===

% === AUTO:EXPERIENCE ===

% === AUTO:EDUCATION ===

% === AUTO:SKILLS ===

% === AUTO:ACHIEVEMENTS ===

\end{document}
"""


def _clean_json_content(content: str) -> str:
    """
    Clean JSON content by removing markdown code fences and extra whitespace.
    Agents sometimes wrap JSON in ```json ... ``` which breaks parsing.
    """
    content = content.strip()
    
    # Remove markdown code fences
    if content.startswith('```'):
        lines = content.split('\n')
        # Remove first line if it's a fence (```json or ```)
        if lines[0].startswith('```'):
            lines = lines[1:]
        # Remove last line if it's a fence (```)
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        content = '\n'.join(lines)
    
    return content.strip()


def _load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON file with error handling for markdown-wrapped content.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            cleaned_content = _clean_json_content(content)
            if not cleaned_content:
                return {}
            return json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        # Log the error and return empty dict
        print(f"Warning: Failed to parse JSON from {file_path}: {e}")
        return {}


def build_resume_from_json_files(
    identity_path: Path,
    summary_path: Path,
    experience_path: Path,
    education_path: Path,
    skills_path: Path,
    projects_path: Optional[Path] = None,
    template_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> str:
    """
    Convenience function to build resume from JSON files.
    
    Args:
        identity_path: Path to identity JSON
        summary_path: Path to summary JSON
        experience_path: Path to experiences JSON
        education_path: Path to education JSON
        skills_path: Path to skills JSON
        projects_path: Optional path to projects JSON
        template_path: Optional path to custom LaTeX template
        output_path: Optional path to write output .tex file
    
    Returns:
        Complete LaTeX document as string
    """
    builder = LaTeXBuilder()
    
    # Load JSON data with markdown fence handling
    identity_data = _load_json_file(identity_path)
    identity = identity_data.get('identity', identity_data)
    
    summary_data = _load_json_file(summary_path)
    summary = summary_data.get('summary', summary_data.get('SUMMARY', ''))
    
    exp_data = _load_json_file(experience_path)
    experiences = exp_data.get('experiences', exp_data.get('selected_experiences', []))
    
    edu_data = _load_json_file(education_path)
    education = edu_data.get('education', edu_data.get('selected_education', []))
    
    skills_data = _load_json_file(skills_path)
    skills = skills_data.get('skills', skills_data.get('selected_skills', []))
    
    projects = None
    if projects_path and projects_path.exists():
        proj_data = _load_json_file(projects_path)
        projects = proj_data.get('projects', proj_data.get('selected_projects', []))
    
    # Build resume
    latex = builder.build_complete_resume(
        identity=identity,
        summary=summary,
        experiences=experiences,
        education=education,
        skills=skills,
        projects=projects,
        template_path=template_path
    )
    
    # Write to file if output path provided
    if output_path:
        output_path.write_text(latex, encoding='utf-8')
    
    return latex



