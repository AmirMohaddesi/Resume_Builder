"""
Python-based LaTeX generator for resumes.
Agents output JSON, Python handles all LaTeX syntax.
"""
import json
import re
import unicodedata
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from resume_builder.utils import clean_json_content, extract_braces

logger = logging.getLogger(__name__)


class LaTeXBuilder:
    """Builds LaTeX resume from JSON data with proper escaping and validation."""
    
    @staticmethod
    def _strip_latex_comments(s: str) -> str:
        """Remove LaTeX comments but preserve newlines."""
        return "\n".join(line.split("%", 1)[0] for line in s.splitlines())
    
    @staticmethod
    def _has_pkg(s: str, pkg: str) -> bool:
        """Check if package exists in uncommented text only."""
        s_nc = LaTeXBuilder._strip_latex_comments(s)
        return bool(re.search(r'\\usepackage(?:\[[^\]]*\])?\{'+re.escape(pkg)+r'\}', s_nc))
    
    @staticmethod
    def escape_latex(text: str, *, keep_commands: bool = False) -> str:
        """Escape special LaTeX characters safely without re-escaping what we just emitted.
        
        Order matters to prevent double-escaping:
        1. Backslash first (to avoid turning \& into \textbackslash{}&)
        2. Other special characters (ASCII seven: & % $ # _ ~ ^)
        3. Braces last (to avoid interfering with previous escapes)
        
        If keep_commands=True, we do NOT escape \ { } so embedded LaTeX stays intact.
        
        Args:
            text: Text to escape
            keep_commands: If True, don't escape backslashes, braces (allows LaTeX commands)
        """
        if not text:
            return ""
        
        if keep_commands:
            # Only escape the "ASCII seven" special characters, not backslashes or braces
            pattern = r'[&%$#_\~^]'
            repl_map = {
                '&': r'\&',
                '%': r'\%',
                '$': r'\$',
                '#': r'\#',
                '_': r'\_',
                '~': r'\textasciitilde{}',
                '^': r'\textasciicircum{}',
            }
            def repl(m): return repl_map[m.group(0)]
            return re.sub(pattern, repl, text)
        else:
            # Three passes to avoid cascading escapes:
            # (1) backslash first, (2) other special chars, (3) braces last
            # Note: Always apply strict, ordered escaping (no heuristic shortcuts)
            s = re.sub(r'\\', r'\\textbackslash{}', text)
            
            def repl2(m):
                ch = m.group(0)
                return {
                    '&': r'\&',
                    '%': r'\%',
                    '$': r'\$',
                    '#': r'\#',
                    '_': r'\_',
                    '~': r'\textasciitilde{}',
                    '^': r'\textasciicircum{}'
                }[ch]
            
            s = re.sub(r'[&%$#_\~^]', repl2, s)
            s = s.replace('{', r'\{').replace('}', r'\}')
            return s
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number for display. Supports US/CA NANP format, preserves international numbers."""
        if not phone:
            return ""
        
        # Preserve leading "+" if present and not NANP
        phone_stripped = phone.strip()
        digits = re.sub(r'\D', '', phone_stripped)
        if not digits:
            return phone_stripped
        
        # If starts with + and not 10/11 digits, preserve original
        if phone_stripped.startswith('+') and len(digits) not in (10, 11):
            return phone_stripped
        
        # E.g., +1xxxxxxxxxx
        if len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        # Plain US 10-digit
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        # Otherwise, don't guess; return original
        return phone_stripped
    
    @staticmethod
    def format_url(url: str) -> str:
        """Clean and format URL for LaTeX hyperref."""
        if not url:
            return ""
        
        # Normalize backslashes someone might paste
        url = url.replace('\\', '/').strip()
        
        # Strip trailing punctuation that often sneaks in from prose
        url = url.rstrip(').,;')
        
        # Guard: Don't prepend https:// if URL already has a scheme (mailto:, ftp:, etc.)
        if re.match(r'^[a-z]+:', url, re.IGNORECASE):
            # Already has a scheme like mailto:, ftp:, etc.
            return url
        
        # Ensure URL has protocol (default to https://)
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
    def build_preamble(self, identity: Dict[str, Any]) -> str:
        """Build LaTeX preamble with identity commands for ModernCV/resumecv templates.
        
        Hard-requires: email, phone
        Optional: website, linkedin, github (skip cleanly if missing)
        """
        preamble_parts = []
        
        # Use \name{First}{Last} instead of \firstname/\familyname (ModernCV/resumecv standard)
        first = self.escape_latex(identity.get('first', '')).strip()
        last = self.escape_latex(identity.get('last', '')).strip()
        if first or last:
            preamble_parts.append(f"\\name{{{first}}}{{{last}}}")
        
        # HARD-REQUIRED: email and phone (must be present)
        # These should have been validated by file_collection_report, but be defensive
        # Normalize and validate fields: strip whitespace and check for non-empty strings
        email = identity.get('email', '').strip() if identity.get('email') else ''
        phone = identity.get('phone', '').strip() if identity.get('phone') else ''
        
        # Hard-require email and phone - validation should have caught missing fields earlier
        # Log warnings if missing (should not happen if validation passed)
        if not email:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Email missing in identity - LaTeX header will be incomplete. This should have been caught by validation.")
        if not phone:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Phone missing in identity - LaTeX header will be incomplete. This should have been caught by validation.")
        
        # Emit email and phone (required fields)
        if email:
            escaped_email = self.escape_latex(email)
            preamble_parts.append(f"\\email{{{escaped_email}}}")
        
        if phone:
            phone_formatted = self.format_phone(phone)
            preamble_parts.append(f"\\phone{{{phone_formatted}}}")
        
        # Optional: address
        addr = identity.get('address', '').strip() if identity.get('address') else ''
        if addr:
            escaped_addr = self.escape_latex(addr)
            preamble_parts.append(f"\\address{{{escaped_addr}}}")
        
        # Optional: website (skip cleanly if missing)
        site = identity.get('website', '').strip() if identity.get('website') else ''
        if site:
            # Ensure full URL for links (format_url adds https:// if missing)
            url = self.format_url(site)
            preamble_parts.append(f"\\homepage{{{url}}}")
        
        # Optional: LinkedIn (skip cleanly if missing)
        # LinkedIn should already be normalized to username only by file_collector
        # Render as https://www.linkedin.com/in/<username>
        linkedin = identity.get('linkedin', '').strip() if identity.get('linkedin') else ''
        if linkedin:
            # Extract username if full URL provided (handle common variants)
            linkedin_lower = linkedin.lower()
            # Match linkedin.com/in/USERNAME or linkedin.com/pub/USERNAME (case-insensitive)
            match = re.search(r'linkedin\.com/(?:in|pub)/([^/?]+)', linkedin_lower)
            if match:
                # Extract username from original string (preserve case)
                original_match = re.search(r'linkedin\.com/(?:in|pub)/([^/?]+)', linkedin, re.IGNORECASE)
                if original_match:
                    linkedin = original_match.group(1).strip('/')
            # linkedin is now username only - LaTeX class will render as https://www.linkedin.com/in/<username>
            preamble_parts.append(f"\\social[linkedin]{{{linkedin}}}")
        
        # Optional: GitHub (skip cleanly if missing)
        # GitHub should already be normalized to username only by file_collector
        # Render as https://github.com/<username>
        github = identity.get('github', '').strip() if identity.get('github') else ''
        if github:
            # Extract username if full URL provided (case-insensitive check)
            github_lower = github.lower()
            # Match github.com/USERNAME pattern (case-insensitive)
            match = re.search(r'github\.com/([^/?]+)', github_lower)
            if match:
                # Extract username from original string (preserve case)
                original_match = re.search(r'github\.com/([^/?]+)', github, re.IGNORECASE)
                if original_match:
                    github = original_match.group(1).split('/')[0].strip('/')  # Take first path component only
            # github is now username only - LaTeX class will render as https://github.com/<username>
            preamble_parts.append(f"\\social[github]{{{github}}}")
        
        return '\n'.join(preamble_parts)
    
    def build_header(self, title_line: str = None, contact_info: Dict[str, Any] = None, 
                     header_data: Dict[str, Any] = None) -> str:
        """Build tailored header section with title line and contact information table.
        
        Args:
            title_line: (Deprecated) Job-relevant keywords separated by pipes. Use header_data instead.
            contact_info: (Deprecated) Dictionary with phone, email, location, website, linkedin, github, google_scholar. Use header_data instead.
            header_data: New format dictionary with name, location, email, phone, links, target_title
        
        Returns:
            LaTeX code for header section matching user's format exactly
        """
        parts = []
        
        # Support new format (header_data) or old format (title_line + contact_info)
        if header_data:
            target_title = header_data.get('target_title', '')
            name = header_data.get('name', '')
            location = header_data.get('location', '')
            email = header_data.get('email', '')
            phone = header_data.get('phone', '')
            links = header_data.get('links', [])
            
            # target_title is metadata only - do NOT display it in the header
            # The old format used title_line for display, but new format doesn't show target_title
            title_line = ''  # Don't display target_title - it's just metadata
            contact_info = {
                'phone': phone,
                'email': email,
                'location': location,
            }
            # Parse links array into individual fields
            for link in links:
                link_str = str(link).lower()
                if 'linkedin.com' in link_str or link_str.startswith('linkedin'):
                    contact_info['linkedin'] = link.split('/')[-1] if '/' in link else link
                elif 'github.com' in link_str or link_str.startswith('github'):
                    contact_info['github'] = link.split('/')[-1] if '/' in link else link
                elif 'scholar.google' in link_str or 'google.com/scholar' in link_str:
                    contact_info['google_scholar'] = link
                elif link_str.startswith('http'):
                    contact_info['website'] = link
        else:
            # Old format - use provided parameters or defaults
            title_line = title_line or ''
            contact_info = contact_info or {}
            phone = contact_info.get('phone', '').strip()
            email = contact_info.get('email', '').strip()
            location = contact_info.get('location', '').strip()
        
        # Title line (centered, bold) - replace | with \textbar{} for LaTeX
        if title_line:
            # Replace pipe separators with LaTeX \textbar{}
            title_escaped = title_line.replace('|', '\\textbar{}')
            # Escape other special characters but keep LaTeX commands
            title_escaped = self.escape_latex(title_escaped, keep_commands=True)
            parts.append(f"\\begin{{center}} \\textbf{{{title_escaped}}} \\end{{center}}")
        
        # Contact information table - 4 columns exactly as in user's example
        row1_parts = []
        row2_parts = []
        
        # Row 1: Phone (col 1), Email (cols 2-3 with multicolumn), Location (col 4)
        if not header_data:
            phone = contact_info.get('phone', '').strip()
            email = contact_info.get('email', '').strip()
            location = contact_info.get('location', '').strip()
        
        if phone:
            formatted_phone = self.format_phone(phone)
            row1_parts.append(f"\\enspace\\faMobile\\enspace {self.escape_latex(formatted_phone)}")
        
        if email:
            escaped_email = self.escape_latex(email)
            row1_parts.append(f"\\multicolumn{{2}}{{c}} {{$\\mathbb{{E}}$}}\\enspace {{{escaped_email}}}")
        
        if location:
            escaped_location = self.escape_latex(location)
            row1_parts.append(f"\\enspace\\faHome\\enspace {escaped_location}")
        
        # Row 2: Website, LinkedIn, GitHub, Google Scholar (1 col each)
        if not header_data:
            website = contact_info.get('website', '').strip()
            linkedin = contact_info.get('linkedin', '').strip()
            github = contact_info.get('github', '').strip()
            google_scholar = contact_info.get('google_scholar', '').strip()
        else:
            # Extract from links array
            website = ''
            linkedin = ''
            github = ''
            google_scholar = ''
            for link in links:
                link_str = str(link).lower()
                if 'linkedin.com' in link_str or link_str.startswith('linkedin'):
                    linkedin = link.split('/')[-1] if '/' in link else link
                elif 'github.com' in link_str or link_str.startswith('github'):
                    github = link.split('/')[-1] if '/' in link else link
                elif 'scholar.google' in link_str or 'google.com/scholar' in link_str:
                    google_scholar = link
                elif link_str.startswith('http'):
                    website = link
        
        if website:
            website_url = self.format_url(website)
            # Use "Personal Website" as display text
            row2_parts.append(f"\\color{{blue}} {{$\\mathbb{{W}}$}} \\href{{{website_url}}}{{Personal Website}}")
        
        if linkedin:
            linkedin_url = f"https://www.linkedin.com/in/{linkedin}" if not linkedin.startswith('http') else linkedin
            row2_parts.append(f"\\enspace\\faLinkedin\\enspace \\color{{blue}} \\href{{{linkedin_url}}}{{{self.escape_latex(linkedin)}}}")
        
        if github:
            github_url = f"https://github.com/{github}" if not github.startswith('http') else github
            row2_parts.append(f"\\enspace\\faGithub\\enspace \\color{{blue}} \\href{{{github_url}}}{{{self.escape_latex(github)}}}")
        
        if google_scholar:
            scholar_url = self.format_url(google_scholar)
            row2_parts.append(f"{{$\\mathbb{{G}}$}}\\enspace \\color{{blue}} \\href{{{scholar_url}}}{{Google Scholar}}")
        
        # Build table - always 4 columns to match user's format
        if row1_parts or row2_parts:
            table_content = []
            if row1_parts:
                # Row 1 structure: Phone (1 col) + Email with multicolumn (2 cols) + Location (1 col) = 4 cols total
                # Email uses \multicolumn{2}{c}, so row1_parts should have exactly 3 items when email is present
                # Don't pad if we already have the correct structure (phone, email, location)
                # Only pad if we're missing items (e.g., no email means we need to adjust)
                has_email_multicolumn = any('\\multicolumn{2}{c}' in part for part in row1_parts)
                if has_email_multicolumn:
                    # With multicolumn email, we should have 3 items max (phone, email, location)
                    # This represents 4 columns: 1 + 2 + 1
                    row1_str = ' & '.join(row1_parts) + ' \\\\'
                else:
                    # No multicolumn email, pad to 4 columns normally
                    while len(row1_parts) < 4:
                        row1_parts.append('\\phantom{}')
                    row1_str = ' & '.join(row1_parts[:4]) + ' \\\\'
                table_content.append(row1_str)
                table_content.append("\\hline")
            
            if row2_parts:
                # Pad row2 to 4 columns if needed
                while len(row2_parts) < 4:
                    row2_parts.append('\\phantom{}')  # Use phantom to prevent empty cell rendering issues
                row2_str = ' & '.join(row2_parts[:4]) + ' \\\\'
                table_content.append(row2_str)
            
            # Always use 4 columns (c c c c) to match user's format
            # Note: Use single braces in LaTeX output (double braces in f-string are for escaping)
            table_latex = f"\\begin{{center}}\\begin{{tabular}}{{ c c c c }}\n" + "\n".join(table_content) + "\n\\end{{tabular}}\\end{{center}}"
            # Fix double braces issue: replace {{ with { and }} with } for tabular/center tags
            table_latex = table_latex.replace("\\end{{tabular}}", "\\end{tabular}").replace("\\end{{center}}", "\\end{center}")
            parts.append(table_latex)
        
        result = "\n".join(parts) if parts else ""
        
        # Log if header is empty for debugging
        if not result or not result.strip():
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"build_header returned empty string - "
                f"title_line: '{title_line}', "
                f"contact_info: phone={bool(phone)}, email={bool(email)}, location={bool(location)}, "
                f"website={bool(website)}, linkedin={bool(linkedin)}, github={bool(github)}, "
                f"google_scholar={bool(google_scholar)}"
            )
        
        return result
    
    def build_summary(self, summary: str) -> str:
        """Build summary section."""
        if not summary:
            return ""
        
        # Allow LaTeX commands in summary (users may paste \textit{} or inline math)
        escaped = self.escape_latex(summary, keep_commands=True)
        return f"\\section*{{Summary}}\n{escaped}\n"
    
    def build_experience_entry(self, exp: Dict[str, Any]) -> str:
        """Build a single experience entry using cventry."""
        title = self.escape_latex(exp.get('title', ''))
        # Support both old (organization) and new (company) field names
        company = self.escape_latex(exp.get('company', exp.get('organization', '')))
        location = self.escape_latex(exp.get('location', ''))
        dates = self.escape_latex(exp.get('dates', ''))
        
        # Build description with bullet points - support both old (description) and new (bullets) field names
        description_lines = []
        bullets = exp.get('bullets', [])
        if bullets:
            for item in bullets:
                escaped_item = self.escape_latex(str(item), keep_commands=True)
                description_lines.append(f"  \\item {escaped_item}")
        elif 'description' in exp and exp['description']:
            # Backward compatibility: handle old description field
            if isinstance(exp['description'], list):
                for item in exp['description']:
                    escaped_item = self.escape_latex(item, keep_commands=True)
                    description_lines.append(f"  \\item {escaped_item}")
            else:
                # Single string description
                escaped_desc = self.escape_latex(exp['description'], keep_commands=True)
                description_lines.append(f"  \\item {escaped_desc}")
        
        if description_lines:
            description = "\\begin{itemize}[leftmargin=*,labelsep=0.5em,itemsep=0pt]\n" + \
                         '\n'.join(description_lines) + "\n\\end{itemize}"
        else:
            description = ""
        
        # cventry format: {dates}{title}{company}{location}{description}
        # For empty descriptions, use {}{} with no inner newline to avoid spurious vertical gaps
        if description:
            return f"\\cventry{{{dates}}}{{{title}}}{{{company}}}{{{location}}}{{}}{{{description}}}\n"
        else:
            return f"\\cventry{{{dates}}}{{{title}}}{{{company}}}{{{location}}}{{}}{{}}\n"
    
    def build_experience_section(self, experiences: List[Dict[str, Any]], max_entries_per_page: Optional[int] = None) -> str:
        """Build complete experience section with optional page breaks."""
        if not experiences:
            return ""
        
        entries = [self.build_experience_entry(exp) for exp in experiences]
        
        # Add page breaks if specified
        if max_entries_per_page and len(entries) > max_entries_per_page:
            result = ["\\section*{Experience}\n"]
            for i, entry in enumerate(entries):
                result.append(entry)
                # Insert soft page break after every max_entries_per_page entries (except the last)
                if (i + 1) % max_entries_per_page == 0 and i < len(entries) - 1:
                    result.append("\\pagebreak[2]\n")  # [2] = preferred but not forced
            return ''.join(result)
        
        return "\\section*{Experience}\n" + '\n'.join(entries)
    
    def build_education_entry(self, edu: Dict[str, Any]) -> str:
        """Build a single education entry."""
        degree = self.escape_latex(edu.get('degree', ''))
        institution = self.escape_latex(edu.get('institution', ''))
        location = self.escape_latex(edu.get('location', ''))
        dates = self.escape_latex(edu.get('dates', ''))
        
        # Optional: honors (gpa removed in new schema, but keep backward compatibility)
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
        return "\\section*{Education}\n" + '\n'.join(entries)
    
    def build_skills_section(self, skills: List[str], groups: Optional[Dict[str, List[str]]] = None) -> str:
        """Build skills section.
        
        Args:
            skills: List of skill strings
            groups: Optional dictionary mapping group names to lists of skills
        """
        if not skills and not groups:
            return ""
        
        # If groups are provided, use them; otherwise use flat skills list
        if groups:
            sections = []
            for group_name, group_skills in groups.items():
                if group_skills:
                    escaped_skills = [self.escape_latex(skill) for skill in group_skills]
                    skills_text = ', '.join(escaped_skills)
                    escaped_group_name = self.escape_latex(group_name)
                    sections.append(f"\\textbf{{{escaped_group_name}}}: {skills_text}")
            skills_text = ' | '.join(sections)
        else:
            # Flat list
            escaped_skills = [self.escape_latex(skill) for skill in skills]
            skills_text = ', '.join(escaped_skills)
        
        # Wrap in sloppypar to avoid overfull boxes with long skill lists
        return f"\\section*{{Skills}}\n\\begin{{sloppypar}}{skills_text}\\end{{sloppypar}}\n"
    
    def build_projects_section(self, projects: List[Dict[str, Any]], max_entries_per_page: Optional[int] = None) -> str:
        """Build compact projects section with space-efficient formatting."""
        if not projects:
            return ""
        
        entries = []
        for proj in projects:
            # Allow LaTeX commands in project names and descriptions (users often paste \textit{} or inline math)
            name = self.escape_latex(proj.get('name', ''), keep_commands=True)
            url = proj.get('url', '')
            
            # Support both old (description) and new (bullets) field names
            bullets = proj.get('bullets', [])
            if bullets:
                # Use compact inline format: "• bullet1 • bullet2" instead of itemize list
                # This saves significant vertical space
                bullet_texts = []
                for bullet in bullets:
                    escaped_bullet = self.escape_latex(str(bullet), keep_commands=True)
                    bullet_texts.append(f"\\textbullet\\enspace {escaped_bullet}")
                description = " ".join(bullet_texts)
            elif 'description' in proj:
                # Backward compatibility: handle old description field
                description = self.escape_latex(proj.get('description', ''), keep_commands=True)
            else:
                description = ""
            
            if url:
                url_formatted = self.format_url(url)
                # Format: \href{url}{text} (bolding happens once in \cvitem)
                name_with_link = f"\\href{{{url_formatted}}}{{{name}}}"
            else:
                name_with_link = name
            
            # Avoid double bold if name already contains a command (e.g., user pasted \textbf{...})
            name_display = name_with_link if re.search(r'\\[a-zA-Z]+', name_with_link) else f"\\textbf{{{name_with_link}}}"
            
            # Use compact format: name and description on same line with minimal spacing
            # Use thin space in label (some ModernCV forks don't accept truly empty {})
            if description:
                # Compact format: name: description (all on one line, saves vertical space)
                entries.append(f"\\cvitem{{~}}{{{name_display}: {description}}}\n")
            else:
                entries.append(f"\\cvitem{{~}}{{{name_display}}}\n")
        
        # Use compact section header (reduced spacing)
        section_header = "\\section*{Projects}\n"
        
        # Add page breaks if specified
        if max_entries_per_page and len(entries) > max_entries_per_page:
            result = [section_header]
            for i, entry in enumerate(entries):
                result.append(entry)
                # Insert soft page break after every max_entries_per_page entries (except the last)
                if (i + 1) % max_entries_per_page == 0 and i < len(entries) - 1:
                    result.append("\\pagebreak[2]\n")  # [2] = preferred but not forced
            return ''.join(result)
        
        return section_header + ''.join(entries)
    
    def _ensure_required_packages(self, latex_content: str) -> str:
        """
        Automatically add required packages if they're used but not included.
        Detects \mathbb commands and FontAwesome icons.
        """
        # Check if \mathbb is used
        needs_amssymb = bool(re.search(r'\\mathbb\{', latex_content))
        has_amssymb = self._has_pkg(latex_content, 'amssymb')
        
        # Check if FontAwesome is used
        needs_fontawesome = bool(re.search(r'\\fa[A-Z][a-zA-Z]*', latex_content))
        has_fontawesome = (self._has_pkg(latex_content, 'fontawesome') or
                          self._has_pkg(latex_content, 'fontawesome5'))
        
        # Also check for commented-out fontawesome5 (handle various comment patterns)
        # This must happen BEFORE we check if we need to add it, because we want to uncomment if it exists
        if needs_fontawesome and not has_fontawesome:
            # Try to uncomment commented fontawesome5 lines - be very aggressive about matching
            lines = latex_content.split('\n')
            for i, line in enumerate(lines):
                line_lower = line.lower()
                # Match any line that has fontawesome5 and is commented
                # Check both the current line and if usepackage might be on the same or next line
                if 'fontawesome5' in line_lower:
                    # Check if this line or the previous line has usepackage
                    has_usepackage = 'usepackage' in line_lower
                    if not has_usepackage and i > 0:
                        has_usepackage = 'usepackage' in lines[i-1].lower()
                    
                    # If the line starts with % (possibly with leading whitespace), uncomment it
                    # Add narrow guard to ensure we only uncomment fontawesome5 lines
                    stripped = line.lstrip()
                    if stripped.startswith('%') and has_usepackage:
                        # Only uncomment if it's actually a fontawesome5 usepackage line
                        if re.search(r'\\usepackage(?:\[[^\]]*\])?\{fontawesome5\}', stripped):
                            # Remove the % and any whitespace immediately after it, preserve leading whitespace
                            uncommented = re.sub(r'^(\s*)%\s*', r'\1', line)
                            if uncommented != line:  # Only replace if we actually uncommented something
                                lines[i] = uncommented
                                has_fontawesome = True
                                break  # Only uncomment the first match
            
            if has_fontawesome:
                latex_content = '\n'.join(lines)
                # Re-check to confirm it's now uncommented
                has_fontawesome = bool(re.search(r'\\usepackage[^\n]*\{fontawesome', latex_content, re.IGNORECASE))
        
        # Find the position to insert packages
        # Prefer: after \documentclass if we can't confidently find hyperref
        insert_pos = -1
        content_nc = self._strip_latex_comments(latex_content)
        hyperref_match_nc = re.search(r'\\usepackage.*\{hyperref\}', content_nc)
        if hyperref_match_nc:
            # Try to find in original (simpler approach: find after documentclass if mapping fails)
            docclass_match = re.search(r'\\documentclass[^\n]*\n', latex_content)
            if docclass_match:
                # Look for hyperref after documentclass
                search_start = docclass_match.end()
                hyperref_match = re.search(r'\\usepackage.*\{hyperref\}', latex_content[search_start:])
                if hyperref_match:
                    insert_pos = search_start + hyperref_match.end()
        
        # Fallback: insert after \documentclass
        if insert_pos == -1:
            docclass_match = re.search(r'\\documentclass[^\n]*\n', latex_content)
            if docclass_match:
                insert_pos = docclass_match.end()
        
        # Insert missing packages
        packages_to_add = []
        if needs_amssymb and not has_amssymb:
            packages_to_add.append('\\usepackage{amssymb}')
        if needs_fontawesome and not has_fontawesome:
            # Use fontawesome5 with microtype disabled to avoid font expansion issues
            packages_to_add.append('\\usepackage{fontawesome5}')
            # Disable microtype font expansion if it's causing issues (idempotent)
            def _ensure_microtype_expansion_false(s: str) -> str:
                def _patch(m):
                    opts = m.group(1)  # may be None
                    if not opts:
                        return r'\usepackage[expansion=false]{microtype}'
                    # split options, ensure 'expansion=' present and set to false
                    parts = [p.strip() for p in opts.split(',') if p.strip()]
                    if not any(p.startswith('expansion=') for p in parts):
                        parts.insert(0, 'expansion=false')
                    else:
                        parts = [('expansion=false' if p.startswith('expansion=') else p) for p in parts]
                    return r'\usepackage[' + ','.join(parts) + r']{microtype}'
                return re.sub(r'\\usepackage(?:\[([^\]]*)\])?\{microtype\}', _patch, s)
            
            latex_content = _ensure_microtype_expansion_false(latex_content)
        
        if packages_to_add and insert_pos != -1:
            # Always add a trailing newline on injected packages
            packages_str = '\n' + '\n'.join(packages_to_add) + '\n'
            latex_content = latex_content[:insert_pos] + packages_str + latex_content[insert_pos:]
        elif packages_to_add:
            # Fallback: add after documentclass
            docclass_match = re.search(r'\\documentclass.*\n', latex_content)
            if docclass_match:
                insert_pos = docclass_match.end()
                packages_str = '\n' + '\n'.join(packages_to_add) + '\n'
                latex_content = latex_content[:insert_pos] + packages_str + latex_content[insert_pos:]
        
        return latex_content
    
    # NOTE: _disable_font_expansion_unconditionally() was removed as it's unused and can cause
    # issues with pdfTeX/LuaTeX/XeTeX. The resumecv.cls class already handles font expansion
    # internally, so this function is not needed.
    
    def build_complete_resume(
        self,
        identity: Dict[str, Any],
        summary: str,
        experiences: List[Dict[str, Any]],
        education: List[Dict[str, Any]],
        skills: List[str],
        projects: Optional[List[Dict[str, Any]]] = None,
        header_data: Optional[Dict[str, Any]] = None,
        template_path: Optional[Path] = None
    ) -> str:
        """Build complete LaTeX resume from JSON components.
        
        Args:
            identity: Identity/contact information dictionary
            summary: Professional summary text
            experiences: List of experience dictionaries
            education: List of education dictionaries
            skills: List of skill strings
            projects: Optional list of project dictionaries
            header_data: Optional header data with 'title_line' and 'contact_info'
            template_path: Optional path to custom LaTeX template
        """
        
        # Build all sections
        preamble = self.build_preamble(identity)
        summary_section = self.build_summary(summary)
        experience_section = self.build_experience_section(experiences)
        education_section = self.build_education_section(education)
        # Handle skills - support both old (skills list) and new (skills_data dict) formats
        # If skills is a dict with 'skills' key, treat it as skills_data
        if isinstance(skills, dict) and 'skills' in skills:
            skills_list = skills.get('skills', [])
            groups = skills.get('groups')
            skills_section = self.build_skills_section(skills_list, groups)
        else:
            skills_section = self.build_skills_section(skills if skills else [])
        projects_section = self.build_projects_section(projects) if projects else ""
        
        # Build header section if header_data is provided
        header_section = ""
        if header_data:
            # Check if it's new format (has target_title) or old format (has title_line)
            if 'target_title' in header_data or 'name' in header_data:
                # New format
                header_section = self.build_header(header_data=header_data)
            else:
                # Old format - backward compatibility
                title_line = header_data.get('title_line', '')
                contact_info = header_data.get('contact_info', {})
                # Fallback to identity if contact_info is empty
                if not contact_info and identity:
                    identity_data = identity.get('identity', identity)
                    contact_info = {
                        'phone': identity_data.get('phone', ''),
                        'email': identity_data.get('email', ''),
                        'location': identity_data.get('address', ''),
                        'website': identity_data.get('website', ''),
                        'linkedin': identity_data.get('linkedin', ''),
                        'github': identity_data.get('github', ''),
                        'google_scholar': identity_data.get('google_scholar', '') or identity_data.get('scholar', '')
                    }
                if title_line or contact_info:
                    header_section = self.build_header(title_line, contact_info)
        elif identity:
            # Fallback: build header from identity if header_data not provided
            identity_data = identity.get('identity', identity)
            contact_info = {
                'phone': identity_data.get('phone', ''),
                'email': identity_data.get('email', ''),
                'location': identity_data.get('address', ''),
                'website': identity_data.get('website', ''),
                'linkedin': identity_data.get('linkedin', ''),
                'github': identity_data.get('github', ''),
                'google_scholar': identity_data.get('google_scholar', '') or identity_data.get('scholar', '')
            }
            if any(contact_info.values()):
                header_section = self.build_header('', contact_info)
        
        # Use template if provided, otherwise use default
        if template_path and template_path.exists():
            # Read as bytes first to preserve backslashes, then decode
            # This prevents Python from interpreting \n, \t, etc. as escape sequences
            template_bytes = template_path.read_bytes()
            template_content = template_bytes.decode('utf-8')
        else:
            template_content = self._get_default_template()
        
        # Replace markers
        latex = template_content
        # Check if template had compact layout definition (for debugging)
        template_had_compact = (
            r'\newcommand{\compactresumelayout}' in template_content or
            r'\newcommand*{\compactresumelayout}' in template_content or
            r'\def\compactresumelayout' in template_content
        )
        if template_had_compact:
            logger.debug("Template contains \\compactresumelayout definition")
        latex = latex.replace('% === AUTO:PREAMBLE ===', preamble)
        # Verify compact layout definition is still present after marker replacement
        if template_had_compact:
            still_has_compact = (
                r'\newcommand{\compactresumelayout}' in latex or
                r'\newcommand*{\compactresumelayout}' in latex or
                r'\def\compactresumelayout' in latex
            )
            if not still_has_compact:
                logger.warning("Template had \\compactresumelayout definition but it was lost during marker replacement!")
        
        # Always insert header - either replace marker or insert before summary
        if header_section and header_section.strip():
            if '% === AUTO:HEADER ===' in latex:
                # Template has header marker - replace it
                latex = latex.replace('% === AUTO:HEADER ===', header_section)
            else:
                # Template doesn't have header marker - insert before summary section
                # Try to find a good insertion point (before summary, after \makecvtitle, or after \begin{document})
                if '% === AUTO:SUMMARY ===' in latex:
                    # Insert before summary
                    latex = latex.replace('% === AUTO:SUMMARY ===', header_section + '\n\n% === AUTO:SUMMARY ===')
                elif '\\section*{Summary}' in latex or '\\section{Summary}' in latex:
                    # Insert before Summary section
                    latex = latex.replace('\\section*{Summary}', header_section + '\n\n\\section*{Summary}')
                    latex = latex.replace('\\section{Summary}', header_section + '\n\n\\section{Summary}')
                elif '\\begin{document}' in latex:
                    # Insert after \begin{document} and \makecvtitle if present
                    if '\\makecvtitle' in latex:
                        # Insert after \makecvtitle
                        latex = latex.replace('\\makecvtitle', '\\makecvtitle\n\n' + header_section)
                    else:
                        # Insert after \begin{document}
                        latex = latex.replace('\\begin{document}', '\\begin{document}\n\n' + header_section)
                else:
                    # Fallback: insert after preamble marker
                    latex = latex.replace('% === AUTO:PREAMBLE ===', '% === AUTO:PREAMBLE ===\n\n' + header_section)
        else:
            # Header is empty - still handle marker if present
            if '% === AUTO:HEADER ===' in latex:
                # If header is empty, remove the marker but keep the comment line for debugging
                latex = latex.replace('% === AUTO:HEADER ===', '% Header section empty - no contact info available')
        
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
        else:
            # No projects - remove empty section markers (but don't remove section headers yet)
            # Section headers will be removed by apply_section_removals if marked for removal
            if '% === AUTO:ACHIEVEMENTS ===' in latex:
                latex = latex.replace('% === AUTO:ACHIEVEMENTS ===', '')
            if '% === AUTO:ADDITIONAL ===' in latex:
                latex = latex.replace('% === AUTO:ADDITIONAL ===', '')
        
        # Remove any remaining markers
        latex = re.sub(r'% === AUTO:\w+ ===', '', latex)
        
        # Apply section removals (from metadata)
        from resume_builder.section_removal import apply_section_removals
        latex = apply_section_removals(latex)
        
        # CRITICAL: Replace moderncv with resumecv if present
        # This handles cases where AI generates LaTeX directly or uses old templates
        # Handle both with and without options, including 'sans' option
        if 'moderncv' in latex:
            # First, replace moderncv with resumecv (keep options for now)
            latex = re.sub(
                r'\\documentclass(\[[^\]]*\])?\{moderncv\}',
                r'\\documentclass\1{resumecv}',
                latex
            )
            # Then clean up 'sans' option from resumecv (not needed, handled by class)
            # Match documentclass with options containing 'sans'
            def remove_sans_option(match):
                options = match.group(1) if match.group(1) else ''
                # Remove 'sans' and clean up commas (remove leading/trailing commas)
                cleaned = re.sub(r',?\s*sans\s*,?', ',', options)
                # Remove leading/trailing commas and whitespace
                cleaned = cleaned.strip(',').strip().strip('[]')
                # Split by comma, filter empty, rejoin
                parts = [p.strip() for p in cleaned.split(',') if p.strip()]
                if parts:
                    return f'\\documentclass[{",".join(parts)}]{{resumecv}}'
                else:
                    return '\\documentclass{resumecv}'
            
            latex = re.sub(
                r'\\documentclass(\[[^\]]*\])?\{resumecv\}',
                remove_sans_option,
                latex
            )
        
        # Automatically add required packages if needed
        # Note: Font expansion is disabled in resumecv.cls, so no need for manual fixes
        latex = self._ensure_required_packages(latex)
        
        # Post-process to fix common LaTeX issues (BEFORE compact layout injection)
        # Only assume class loads core packages if we're using resumecv (which we know loads them)
        is_resumecv = bool(re.search(r'\\documentclass[^\n]*\{resumecv\}', latex))
        latex = self._post_process_latex(latex, assume_class_loads_core_pkgs=is_resumecv)
        
        # Add intelligent page breaks to prevent large gaps
        latex = self._add_intelligent_page_breaks(latex)
        
        return latex
    
    def _post_process_latex(self, latex_content: str, *, assume_class_loads_core_pkgs: bool = False) -> str:
        """
        Post-process LaTeX to fix common issues:
        1. Fix lost backslashes (opagenumbers, ewcommand, oindent)
        2. Fix trailing commas in documentclass options
        3. Fix broken \textcolor name blocks
        4. Remove redundant manual header blocks when using resumecv
        5. Fix \nopagenumbers{} to \nopagenumbers (no braces)
        6. Remove redundant packages (geometry, hyperref, xcolor, inputenc, enumitem, multicol, ragged2e - already in resumecv.cls)
        7. Remove manual vspace tweaks that break layout
        8. Ensure fontawesome5 is loaded
        9. Remove stray pipe characters at the start of document (common table rendering issue)
        """
        # Fix 0: Restore lost backslashes (CRITICAL - must be first)
        # Fix opagenumbers -> \nopagenumbers (missing backslash at start of line or after newline)
        latex_content = re.sub(r'(?<!\\)(?<![a-zA-Z])opagenumbers\b', r'\\nopagenumbers', latex_content)
        # Fix ewcommand -> \newcommand (missing backslash)
        latex_content = re.sub(r'(?<!\\)(?<![a-zA-Z])ewcommand\b', r'\\newcommand', latex_content)
        # Fix ewif -> \newif (missing backslash) - CRITICAL for compact layout
        latex_content = re.sub(r'(?<!\\)(?<![a-zA-Z])ewif\b', r'\\newif', latex_content)
        # Fix oindent -> \noindent (missing backslash)
        latex_content = re.sub(r'(?<!\\)(?<![a-zA-Z])oindent\b', r'\\noindent', latex_content)
        # Fix ame{ -> \name{ (missing backslash)
        latex_content = re.sub(r'(?<!\\)(?<![a-zA-Z])ame\s*\{', r'\\name{', latex_content)
        
        # Fix 0.5: Fix trailing commas in documentclass options
        # Pattern: \documentclass[11pt,a4paper,]{resumecv} -> \documentclass[11pt,a4paper]{resumecv}
        # CRITICAL: Must capture class name to avoid dropping it
        latex_content = re.sub(
            r'\\documentclass\[([^\]]+),\]\{([^\}]+)\}',
            lambda m: f'\\documentclass[{m.group(1).rstrip(",")}]{{{m.group(2)}}}',
            latex_content
        )
        
        # Fix 0.5.5: Remove \moderncvstyle and \moderncvcolor when using resumecv (they're incompatible)
        # These commands are for ModernCV, not resumecv, and cause layout issues
        is_resumecv = bool(re.search(r'\\documentclass[^\n]*\{resumecv\}', latex_content))
        if is_resumecv:
            # Remove these lines completely (they break resumecv layout)
            latex_content = re.sub(r'\\moderncvstyle\{[^\}]*\}\s*\n?', '', latex_content)
            latex_content = re.sub(r'\\moderncvcolor\{[^\}]*\}\s*\n?', '', latex_content)
        
        # Fix 0.6: Remove redundant manual header blocks when using resumecv
        # If we have \makecvtitle and \name, remove manual center blocks that match name patterns
        # Only remove blocks that look like name headers (Huge/bfseries/textcolor with name-like content)
        has_makecvtitle = bool(re.search(r'\\makecvtitle', latex_content))
        has_name_commands = bool(re.search(r'\\name\{', latex_content))
        
        if has_makecvtitle and has_name_commands and is_resumecv:
            doc_start = latex_content.find('\\begin{document}')
            if doc_start > 0:
                preamble = latex_content[:doc_start]
                body = latex_content[doc_start:]
                
                # Extract name from \name{First}{Last} to match against header blocks
                name_match = re.search(r'\\name\{([^}]+)\}\{([^}]+)\}', latex_content)
                if name_match:
                    first_name = name_match.group(1).strip()
                    last_name = name_match.group(2).strip()
                    # Remove manual header center blocks that contain the name
                    # Only remove blocks that match name-specific patterns (not all center blocks)
                    name_pattern = re.escape(first_name) + r'.*?' + re.escape(last_name)
                    preamble = re.sub(
                        r'\\begin\{center\}.*?\{\\Huge.*?\\bfseries.*?' + name_pattern + r'.*?\}.*?\\end\{center\}.*?\n',
                        '',
                        preamble,
                        flags=re.DOTALL | re.IGNORECASE
                    )
                    # Also match textcolor patterns with the name
                    preamble = re.sub(
                        r'\\begin\{center\}.*?\\textcolor\{[^}]+\}.*?' + name_pattern + r'.*?\\end\{center\}.*?\n',
                        '',
                        preamble,
                        flags=re.DOTALL | re.IGNORECASE
                    )
                    # Remove orphaned \vspace{1em} that might follow removed headers
                    preamble = re.sub(r'\\vspace\{1em\}\s*\n\s*\\vspace\{1em\}', r'\\vspace{1em}', preamble)
                
                # Remove duplicate contact info blocks (tabular with \hline) that appear right after \makecvtitle
                # These are redundant since \makecvtitle already handles contact info
                makecvtitle_pos = body.find('\\makecvtitle')
                if makecvtitle_pos >= 0:
                    # Look for center blocks with tabular right after \makecvtitle
                    after_makecvtitle = body[makecvtitle_pos:]
                    # Remove center blocks with tabular that contain contact info patterns
                    # (phone numbers, emails, \faMobile, \faEnvelope, etc.)
                    after_makecvtitle = re.sub(
                        r'\\begin\{center\}.*?\\begin\{tabular\}.*?\\hline.*?\\end\{tabular\}.*?\\end\{center\}',
                        '',
                        after_makecvtitle,
                        flags=re.DOTALL,
                        count=2  # Remove up to 2 such blocks (role line + contact line)
                    )
                    # Also remove simple center blocks with role/tagline text right after \makecvtitle
                    after_makecvtitle = re.sub(
                        r'\\begin\{center\}.*?\\textbf\{[^}]*Engineer[^}]*\}.*?\\end\{center\}',
                        '',
                        after_makecvtitle,
                        flags=re.DOTALL,
                        count=1
                    )
                    body = body[:makecvtitle_pos] + after_makecvtitle
                
                latex_content = preamble + body
        
        # Fix 0.7: Fix broken \textcolor name blocks
        # Pattern: \textcolor{black}{John \textcolor}{black} -> \textcolor{black}{John}
        latex_content = re.sub(
            r'\\textcolor\{([^}]+)\}\{([^}]+)\\textcolor\}\{([^}]+)\}',
            r'\\textcolor{\1}{\2 \3}',
            latex_content
        )
        # Pattern: \textcolor{black}{Name \textcolor{black} -> \textcolor{black}{Name}
        latex_content = re.sub(
            r'\\textcolor\{([^}]+)\}\{([^}]+)\\textcolor\{([^}]+)\}',
            r'\\textcolor{\1}{\2}',
            latex_content
        )
        # Extra guard: Normalize cases like: \textcolor{black}{First \textcolor}{black}{Last}
        latex_content = re.sub(
            r'\\textcolor\{([^}]+)\}\{([^}]*)\\textcolor\}\{([^}]+)\}',
            r'\\textcolor{\1}{\2 \3}',
            latex_content
        )
        
        # Fix 1: \nopagenumbers{} -> \nopagenumbers (no braces)
        latex_content = re.sub(r'\\nopagenumbers\{\}', r'\\nopagenumbers', latex_content)
        
        # Fix 2: Remove redundant packages (only if class is known to load them)
        # These packages are loaded by resumecv.cls: geometry, hyperref, xcolor, inputenc, enumitem, multicol, ragged2e
        # Only remove if explicitly requested (assume_class_loads_core_pkgs=True)
        if assume_class_loads_core_pkgs:
            redundant_packages = [
                r'\\usepackage\[[^\]]*\]\{geometry\}',
                r'\\usepackage\{geometry\}',
                r'\\usepackage\[[^\]]*\]\{hyperref\}',
                r'\\usepackage\{hyperref\}',
                r'\\usepackage\[[^\]]*\]\{xcolor\}',
                r'\\usepackage\{xcolor\}',
                r'\\usepackage\[[^\]]*\]\{inputenc\}',
                r'\\usepackage\{inputenc\}',
                r'\\usepackage\[[^\]]*\]\{enumitem\}',
                r'\\usepackage\{enumitem\}',
                r'\\usepackage\[[^\]]*\]\{multicol\}',
                r'\\usepackage\{multicol\}',
                r'\\usepackage\[[^\]]*\]\{ragged2e\}',
                r'\\usepackage\{ragged2e\}',
            ]
            
            for pattern in redundant_packages:
                # Remove the line but keep newlines
                latex_content = re.sub(pattern + r'\s*\n', '', latex_content)
        
        # Fix 3: Remove problematic manual vspace tweaks
        # Remove negative vspace (e.g., \vspace{-11mm}) that break layout
        # Keep small positive vspace as they're usually fine
        def check_vspace(match):
            full_match = match.group(0)
            value_str = match.group(1)
            unit = match.group(2) if match.group(2) else 'em'
            
            try:
                num = float(value_str)
                # Remove negative vspace (always problematic)
                if num < 0:
                    return ''
                # Remove very large vspace (>10mm or >5em) that break layout
                if unit == 'mm' and num > 10:
                    return ''
                elif unit == 'cm' and num > 1:
                    return ''
                elif unit == 'pt' and num > 72:  # >1 inch
                    return ''
                elif (unit == 'em' or unit == '') and num > 5:
                    return ''
            except:
                pass
            return full_match
        
        # Match vspace with optional * and value with optional unit
        latex_content = re.sub(r'\\vspace\*?\{(-?\d+\.?\d*)(mm|cm|pt|em)?\}', check_vspace, latex_content)
        
        # Fix 4: Ensure fontawesome5 is loaded (if FontAwesome commands are used)
        has_fa_commands = bool(re.search(r'\\fa[A-Z][a-zA-Z]*', latex_content))
        has_fontawesome = bool(re.search(r'\\usepackage[^\n]*\{fontawesome', latex_content, re.IGNORECASE))
        
        if has_fa_commands and not has_fontawesome:
            # Find position after documentclass to insert
            docclass_match = re.search(r'\\documentclass[^\n]*\n', latex_content)
            if docclass_match:
                insert_pos = docclass_match.end()
                latex_content = latex_content[:insert_pos] + '\\usepackage{fontawesome5}\n' + latex_content[insert_pos:]
        
        # Fix 4.5: Ensure hyperref is configured with URL hyphenation
        if is_resumecv:
            # Check if hyperref is loaded but not configured with URL hyphenation
            has_hyperref = bool(re.search(r'\\usepackage[^\n]*\{hyperref\}', latex_content, re.IGNORECASE))
            has_url_hyphens = bool(re.search(r'PassOptionsToPackage.*hyphens.*url', latex_content, re.IGNORECASE))
            has_hidelinks = bool(re.search(r'\\usepackage\[[^\]]*hidelinks[^\]]*\]\{hyperref\}', latex_content, re.IGNORECASE))
            has_urlmuskip = bool(re.search(r'\\Urlmuskip', latex_content))
            
            if has_hyperref:
                # Find hyperref package line
                hyperref_match = re.search(r'\\usepackage(?:\[([^\]]*)\])?\{hyperref\}', latex_content, re.IGNORECASE)
                if hyperref_match:
                    hyperref_pos = hyperref_match.start()
                    # Insert PassOptionsToPackage before hyperref if not present
                    if not has_url_hyphens:
                        # Check if there's already a PassOptionsToPackage before hyperref
                        before_hyperref = latex_content[:hyperref_pos]
                        if 'PassOptionsToPackage' not in before_hyperref[-200:]:
                            latex_content = latex_content[:hyperref_pos] + '\\PassOptionsToPackage{hyphens}{url}\n' + latex_content[hyperref_pos:]
                            hyperref_pos += len('\\PassOptionsToPackage{hyphens}{url}\n')
                    
                    # Update hyperref to include hidelinks if not present
                    if not has_hidelinks:
                        hyperref_line_match = re.search(r'\\usepackage(?:\[([^\]]*)\])?\{hyperref\}', latex_content[hyperref_pos:], re.IGNORECASE)
                        if hyperref_line_match:
                            full_match = hyperref_line_match.group(0)
                            options = hyperref_line_match.group(1) if hyperref_line_match.group(1) else ''
                            # Add hidelinks to options
                            if options:
                                if 'hidelinks' not in options.lower():
                                    new_options = options.rstrip(']') + ',hidelinks]'
                                    new_line = full_match.replace('[' + options + ']', '[' + new_options + ']')
                            else:
                                new_line = '\\usepackage[hidelinks]{hyperref}'
                            
                            # Replace the hyperref line
                            start_replace = hyperref_pos + hyperref_line_match.start()
                            end_replace = hyperref_pos + hyperref_line_match.end()
                            latex_content = latex_content[:start_replace] + new_line + latex_content[end_replace:]
                    
                    # Add Urlmuskip after hyperref if not present
                    if not has_urlmuskip:
                        # Find end of hyperref line
                        hyperref_end_match = re.search(r'\\usepackage(?:\[[^\]]*\])?\{hyperref\}', latex_content[hyperref_pos:], re.IGNORECASE)
                        if hyperref_end_match:
                            urlmuskip_pos = hyperref_pos + hyperref_end_match.end()
                            # Check if Urlmuskip is already nearby
                            nearby_text = latex_content[urlmuskip_pos:urlmuskip_pos+200]
                            if '\\Urlmuskip' not in nearby_text:
                                latex_content = latex_content[:urlmuskip_pos] + '\n\\Urlmuskip=0mu plus 1mu  % Allow URL breaking with minimal penalty\n' + latex_content[urlmuskip_pos:]
        
        # Note: \href{url} missing {text} is handled by the placeholder+wrap logic in repair_latex_file
        # No need to fix it here to avoid double-wrapping conflicts
        
        # Fix 4.6: Remove stray pipe characters at the start of document (common table rendering issue)
        # CRITICAL: Remove pipe characters that appear at the top of the document
        # This is a persistent issue where pipes appear after \begin{document} or \makecvtitle
        # Root cause: Empty table cells, malformed LaTeX, or agent-generated content with pipes
        
        # First, use regex to remove pipes immediately after document start markers
        doc_start_patterns = [
            # Patterns with newlines and whitespace variations
            (r'\\begin\{document\}\s*\n\s*\|+\s*\n', r'\\begin{document}\n'),
            (r'\\makecvtitle\s*\n\s*\|+\s*\n', r'\\makecvtitle\n'),
            (r'\\begin\{document\}\s*\n\s*\|{1,}\s*\n', r'\\begin{document}\n'),  # 1 or more pipes
            (r'\\makecvtitle\s*\n\s*\|{1,}\s*\n', r'\\makecvtitle\n'),  # 1 or more pipes
            # Patterns with spaces between pipes (e.g., "| | | |")
            (r'\\begin\{document\}\s*\n\s*(\|\s*){1,}\n', r'\\begin{document}\n'),
            (r'\\makecvtitle\s*\n\s*(\|\s*){1,}\n', r'\\makecvtitle\n'),
            # Patterns with mixed whitespace
            (r'\\begin\{document\}\s*\n\s*\|[\s\|]*\n', r'\\begin{document}\n'),
            (r'\\makecvtitle\s*\n\s*\|[\s\|]*\n', r'\\makecvtitle\n'),
        ]
        for pattern, replacement in doc_start_patterns:
            latex_content = re.sub(pattern, replacement, latex_content)
        
        # Second, use line-by-line processing to catch any remaining pipe lines
        # This is more comprehensive and handles edge cases
        lines = latex_content.split('\n')
        cleaned_lines = []
        skip_next_pipe_lines = False
        doc_started = False
        
        for i, line in enumerate(lines):
            # Check if this is \begin{document} or \makecvtitle
            if re.search(r'\\begin\{document\}|\\makecvtitle', line):
                cleaned_lines.append(line)
                skip_next_pipe_lines = True
                doc_started = True
            # If we're in the skip zone (first 10 lines after document start) and line is only pipes/whitespace, skip it
            elif skip_next_pipe_lines and i < len(lines) and i < 15:  # Check first 15 lines after doc start
                # Match lines that are ONLY pipes (with optional whitespace)
                # This catches: "|", "| |", "||||", "  |  |  ", etc.
                if re.match(r'^\s*(\|\s*){1,}\s*$', line):
                    # Skip this line (don't add it)
                    logger.debug(f"Removed pipe line at position {i}: {repr(line)}")
                    continue
                # If we hit a non-empty, non-pipe line, stop skipping
                elif line.strip() and not re.match(r'^\s*(\|\s*){1,}\s*$', line):
                    skip_next_pipe_lines = False
                    cleaned_lines.append(line)
                else:
                    # Empty line or whitespace - keep it
                    cleaned_lines.append(line)
            else:
                # Normal line processing
                # Also remove any standalone pipe lines anywhere in the first 20 lines (safety check)
                if doc_started and i < 20 and re.match(r'^\s*(\|\s*){1,}\s*$', line):
                    logger.debug(f"Removed pipe line at position {i} (safety check): {repr(line)}")
                    continue
                cleaned_lines.append(line)
        
        latex_content = '\n'.join(cleaned_lines)
        
        # Third, final cleanup pass: remove any remaining pipe-only lines in the first 25 lines
        # This is a safety net for any edge cases we might have missed
        lines = latex_content.split('\n')
        final_cleaned = []
        for i, line in enumerate(lines):
            # Only check first 25 lines for standalone pipe lines
            if i < 25 and re.match(r'^\s*(\|\s*){1,}\s*$', line):
                logger.debug(f"Final cleanup: Removed pipe line at position {i}: {repr(line)}")
                continue
            final_cleaned.append(line)
        latex_content = '\n'.join(final_cleaned)
        
        # Fix 5: Replace \maincolumnwidth with \linewidth in customcventry definitions
        # This fixes the narrow column issue - \maincolumnwidth is ModernCV-specific and creates skinny columns
        # Use \linewidth (always available) instead of \cvMainWidth to avoid definition ordering issues
        if is_resumecv:
            # Replace \maincolumnwidth in \customcventry macro definitions
            # Pattern: \begin{minipage}{\maincolumnwidth} -> \begin{minipage}{\linewidth}
            latex_content = re.sub(
                r'\\begin\{minipage\}\{\\maincolumnwidth\}',
                r'\\begin{minipage}{\\linewidth}',
                latex_content
            )
            # Also replace standalone \maincolumnwidth references
            latex_content = re.sub(r'\\maincolumnwidth', r'\\linewidth', latex_content)
            
            # Fix 5.5: Reduce spacing in \customcventry to fit more content on first page
            # Reduce default spacing from .13em to .08em and reduce \\[.25em] to \\[.15em]
            latex_content = re.sub(
                r'\\newcommand\*?\{\\customcventry\}\[7\]\[\.13em\]',
                r'\\newcommand*{\\customcventry}[7][.08em]',
                latex_content
            )
            # Also reduce the \\[.25em] spacing before description
            latex_content = re.sub(
                r'\\\[\.25em\]',
                r'\\[.15em]',
                latex_content
            )
            
            # Fix 5.6: Remove minipage from \customcventry macro to allow page breaks
            # Replace \begin{minipage}{\linewidth}\small #7\end{minipage} with {\small #7}
            # Match the pattern with escaped braces and parameter #7
            latex_content = re.sub(
                r'\\begin\{minipage\}\{\\linewidth\}\\small\s*#7\\end\{minipage\}',
                r'{\\small #7}%  % no minipage: allows page breaks',
                latex_content
            )
            # Also handle \textwidth variant
            latex_content = re.sub(
                r'\\begin\{minipage\}\{\\textwidth\}\\small\s*#7\\end\{minipage\}',
                r'{\\small #7}%  % no minipage: allows page breaks',
                latex_content
            )
            # Handle cases with optional spacing before \small
            latex_content = re.sub(
                r'\\begin\{minipage\}\{\\linewidth\}\\small\s+#7\\end\{minipage\}',
                r'{\\small #7}%  % no minipage: allows page breaks',
                latex_content
            )
            latex_content = re.sub(
                r'\\begin\{minipage\}\{\\textwidth\}\\small\s+#7\\end\{minipage\}',
                r'{\\small #7}%  % no minipage: allows page breaks',
                latex_content
            )
        
        # Fix 6: Apply layout width fixes for resumecv (widen layout, fix narrow column issue)
        # Only apply if resumecv is detected and fixes aren't already present
        if is_resumecv:
            # Check if layout fixes are already present
            has_geometry_override = bool(re.search(r'\\geometry\{margin=', latex_content))
            has_enumitem_settings = bool(re.search(r'\\setlist\[itemize\]', latex_content))
            has_sloppy = bool(re.search(r'\\sloppy', latex_content))
            
            # Find insertion point (after documentclass and any existing geometry, before \begin{document})
            doc_start = latex_content.find('\\begin{document}')
            if doc_start > 0:
                preamble = latex_content[:doc_start]
                body = latex_content[doc_start:]
                
                # Build layout fixes block
                layout_fixes = []
                
                if not has_geometry_override:
                    layout_fixes.append('% --- Widen layout & fix ModernCV/resumecv mix ---')
                    layout_fixes.append('% Widen page margins (resumecv already loads geometry; override after class)')
                    layout_fixes.append('\\geometry{margin=0.75in}')
                    layout_fixes.append('')
                
                
                if not has_enumitem_settings:
                    layout_fixes.append('% Gentler lists and fewer breaks to pull content up')
                    layout_fixes.append('\\usepackage{enumitem}')
                    layout_fixes.append('\\setlist[itemize]{leftmargin=*, labelsep=0.5em, topsep=.15em, itemsep=.15em, parsep=0em}')
                    layout_fixes.append('')
                
                if not has_sloppy:
                    layout_fixes.append('% Ease line-breaking so LaTeX hyphenates less aggressively without overfull boxes')
                    layout_fixes.append('\\sloppy')
                    layout_fixes.append('\\emergencystretch=3em')
                
                if layout_fixes:
                    # Insert after last package or after documentclass if no packages
                    last_package = max(
                        preamble.rfind('\\usepackage'),
                        preamble.rfind('\\geometry'),
                        preamble.rfind('\\nopagenumbers')
                    )
                    if last_package > 0:
                        # Find end of that line
                        insert_pos = preamble.find('\n', last_package) + 1
                    else:
                        # Insert after documentclass
                        docclass_match = re.search(r'\\documentclass[^\n]*\n', preamble)
                        insert_pos = docclass_match.end() if docclass_match else len(preamble)
                    
                    preamble = preamble[:insert_pos] + '\n'.join(layout_fixes) + '\n' + preamble[insert_pos:]
                    latex_content = preamble + body
        
        return latex_content
    
    def _add_intelligent_page_breaks(self, latex_content: str) -> str:
        """
        Add intelligent page breaks to prevent large gaps on the first page.
        
        Strategy:
        1. If Summary section is followed by a very large section (Research Experience, Experience, etc.),
           add \newpage after Summary to force the large section to start on page 2
        2. Detect sections that are too large and add page breaks within them
        """
        import re
        
        # Find the document body (after \begin{document})
        doc_start = latex_content.find('\\begin{document}')
        if doc_start == -1:
            return latex_content
        
        body = latex_content[doc_start:]
        
        # Pattern to find section markers
        section_pattern = r'\\section\*?\{([^}]+)\}'
        
        # Find all sections and their positions
        sections = []
        for match in re.finditer(section_pattern, body):
            section_name = match.group(1)
            section_start = match.start()
            sections.append((section_name, section_start))
        
        if len(sections) < 2:
            return latex_content
        
        # Find Summary section and the section immediately after it
        summary_idx = None
        for i, (name, pos) in enumerate(sections):
            if 'summary' in name.lower():
                summary_idx = i
                break
        
        if summary_idx is None or summary_idx + 1 >= len(sections):
            return latex_content
        
        # Get the section after Summary
        next_section_name, next_section_start = sections[summary_idx + 1]
        summary_section_start = sections[summary_idx][1]
        
        # Calculate the size of Summary section content
        summary_content = body[summary_section_start:next_section_start]
        summary_lines = summary_content.count('\n')
        
        # Calculate the size of the next section (up to next section or end)
        if summary_idx + 2 < len(sections):
            next_next_section_start = sections[summary_idx + 2][1]
            next_section_content = body[next_section_start:next_next_section_start]
        else:
            # Last section, go to end of document
            doc_end = body.find('\\end{document}')
            if doc_end == -1:
                doc_end = len(body)
            next_section_content = body[next_section_start:doc_end]
        
        next_section_lines = next_section_content.count('\n')
        
        # Only add \newpage if:
        # 1. Summary is very short (< 5 lines) AND next section is very large (> 70 lines)
        #    This indicates a big gap would occur on first page
        # 2. OR next section is extremely large (> 100 lines) regardless of Summary size
        # This prevents huge gaps on the first page while avoiding unnecessary page breaks
        should_add_newpage = False
        if summary_lines < 5 and next_section_lines > 70:
            should_add_newpage = True
        elif next_section_lines > 100:
            should_add_newpage = True
        
        if should_add_newpage:
            # Find the end of Summary section (start of next section)
            # Insert \newpage right before the next section
            summary_end_pos = next_section_start
            
            # Check if there's already a page break there
            before_section = body[max(0, summary_end_pos - 50):summary_end_pos]
            if '\\newpage' not in before_section and '\\pagebreak' not in before_section:
                # Insert \newpage before the next section
                body = body[:summary_end_pos] + '\\newpage\n\n' + body[summary_end_pos:]
                latex_content = latex_content[:doc_start] + body
        
        # Also check for very large individual entries within sections
        # Look for \customcventry that spans many lines
        customcventry_pattern = r'\\customcventry[^\n]*\n(?:[^\\]|\\[^{])*?\{[^}]*\}(?:[^\\]|\\[^{])*?\{[^}]*\}(?:[^\\]|\\[^{])*?\{[^}]*\}(?:[^\\]|\\[^{])*?\{[^}]*\}(?:[^\\]|\\[^{])*?\{[^}]*\}(?:[^\\]|\\[^{])*?\{(.*?)\}'
        
        # Find large \customcventry blocks (more than 30 lines)
        for match in re.finditer(r'\\customcventry', body):
            entry_start = match.start()
            # Find the end of this entry (next \customcventry, \section, or \end{document})
            next_entry = body.find('\\customcventry', entry_start + 1)
            next_section = body.find('\\section', entry_start + 1)
            doc_end = body.find('\\end{document}', entry_start + 1)
            
            end_positions = [pos for pos in [next_entry, next_section, doc_end] if pos != -1]
            if not end_positions:
                continue
            
            entry_end = min(end_positions)
            entry_content = body[entry_start:entry_end]
            entry_lines = entry_content.count('\n')
            
            # If entry is very large (more than 35 lines), consider adding a page break
            # But only if it's not already at the start of a page
            if entry_lines > 35:
                # Check if there's already a page break before this entry
                before_entry = body[max(0, entry_start - 100):entry_start]
                if '\\newpage' not in before_entry and '\\pagebreak' not in before_entry:
                    # Check if this is the first entry in a section (if so, \newpage was already added above)
                    # Otherwise, add a soft page break before this entry
                    prev_section = body.rfind('\\section', 0, entry_start)
                    if prev_section != -1:
                        content_after_section = body[prev_section:entry_start]
                        # If this is the first entry after a section and section already has \newpage, skip
                        if '\\newpage' in content_after_section:
                            continue
                        # Otherwise, add \pagebreak[2] before this large entry
                        body = body[:entry_start] + '\\pagebreak[2]\n' + body[entry_start:]
                        latex_content = latex_content[:doc_start] + body
                        break  # Only add one break at a time to avoid over-breaking
        
        return latex_content
    
    def _get_default_template(self) -> str:
        """Return default resume template using custom resumecv class."""
        return r"""\documentclass[11pt,a4paper]{resumecv}
\nopagenumbers
% Note: geometry, hyperref, xcolor, inputenc, enumitem, multicol, ragged2e are already loaded by resumecv.cls
% Only add packages that are NOT already loaded by the class
% fontawesome5 will be added automatically by _post_process_latex if \fa... commands are detected
% Use XeLaTeX if you want emoji in the header
\usepackage{amssymb}

% --- Widen layout & fix ModernCV/resumecv mix ---
% Do NOT use \moderncvstyle/\moderncvcolor with "resumecv" (remove if present)
% Widen page margins (resumecv already loads geometry; override after class)
\geometry{margin=0.75in}

% Gentler lists and fewer breaks to pull content up (tighter spacing for more content)
\usepackage{enumitem}
\setlist[itemize]{leftmargin=*, labelsep=0.5em, topsep=.15em, itemsep=.15em, parsep=0em}

% Ease line-breaking so LaTeX hyphenates less aggressively without overfull boxes
\sloppy
\emergencystretch=3em

% === AUTO:PREAMBLE ===

\begin{document}
\makecvtitle

% === AUTO:HEADER ===

% === AUTO:SUMMARY ===

% === AUTO:EXPERIENCE ===

% === AUTO:EDUCATION ===

% === AUTO:SKILLS ===

% === AUTO:ACHIEVEMENTS ===

\end{document}
"""


# _clean_json_content moved to resume_builder.utils


def _load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON file with error handling for markdown-wrapped content.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            cleaned_content = clean_json_content(content)
            if not cleaned_content:
                return {}
            return json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        # Log the error and return empty dict
        print(f"Warning: Failed to parse JSON from {file_path}: {e}")
        return {}


def enforce_length_budget(
    experiences: list,
    projects: list,
    skills_data: dict,
    education_data: dict,
    page_budget_pages: int = 2,
) -> dict:
    """
    Heuristic pass to keep resume layout within the page budget.
    Uses counts + priority, NOT actual TeX layout calculation.
    
    Args:
        experiences: List of experience dicts with 'priority' and 'bullets' fields
        projects: List of project dicts with 'priority' and 'bullets' fields
        skills_data: Dict with 'skills' list (and optional 'groups')
        education_data: List of education entries
        page_budget_pages: Target page count (default: 2)
    
    Returns:
        Dict with trimmed content and 'used_compact_layout' flag
    """
    LINES_PER_PAGE = 25  # Very conservative - actual resumes with spacing, wrapping, and formatting use fewer lines
    
    def estimate_lines(exp_list, proj_list, skills_dict, edu_list):
        """Estimate total lines based on content. Accounts for text wrapping, nested lists, and spacing."""
        total = 0
        
        # Header + summary: ~12-15 lines (more realistic with spacing and formatting)
        total += 14
        
        # Experiences: base 6 lines + estimate based on actual text length
        for exp in exp_list:
            total += 6  # Title, company, dates, spacing
            bullets = exp.get('bullets', [])
            for bullet in bullets:
                if isinstance(bullet, str):
                    # Estimate lines based on text length: ~60 chars per line, account for wrapping
                    words = len(bullet.split())
                    # Average word length ~5 chars, so ~12 words per line, but bullets indent so ~10 words/line
                    bullet_lines = max(1, int(words / 10) + 1)  # At least 1 line, add 1 for spacing
                    total += bullet_lines
                else:
                    total += 1.5  # Fallback for non-string bullets
        
        # Projects: base 5 lines + estimate based on actual text length
        for proj in proj_list:
            total += 5  # Name, description, spacing
            bullets = proj.get('bullets', [])
            for bullet in bullets:
                if isinstance(bullet, str):
                    words = len(bullet.split())
                    bullet_lines = max(1, int(words / 10) + 1)
                    total += bullet_lines
                else:
                    total += 1.5
        
        # Skills: ~8 lines if <= 15 skills, else ~12 lines (accounts for wrapping)
        skills_list = skills_dict.get('skills', [])
        if len(skills_list) <= 15:
            total += 8
        else:
            # Skills wrap to multiple lines
            total += 12 + int((len(skills_list) - 15) / 5)  # Extra line per 5 skills
        
        # Education: ~5 lines per entry (accounts for spacing and formatting)
        total += len(edu_list) * 5
        
        # Add section headers and spacing: ~3 lines per section (headers are taller)
        section_count = 1  # Summary
        if exp_list:
            section_count += 1  # Experience
        if proj_list:
            section_count += 1  # Projects
        if skills_list:
            section_count += 1  # Skills
        if edu_list:
            section_count += 1  # Education
        total += section_count * 3
        
        return int(total)
    
    trimmed_experiences = list(experiences)
    trimmed_projects = list(projects) if projects else []
    trimmed_skills_data = dict(skills_data)
    
    # Check initial estimate - if over budget, enable compact layout
    estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
    estimated_pages = estimated_lines / LINES_PER_PAGE
    
    # CRITICAL: Set compact layout flag if initial estimate exceeds budget
    # This ensures compact layout is applied even if trimming brings it under budget
    used_compact_layout = estimated_pages > page_budget_pages
    
    logger.info(f"Initial length estimate: {estimated_lines} lines (~{estimated_pages:.1f} pages)")
    if used_compact_layout:
        logger.info(f"Content exceeds page budget ({estimated_pages:.1f} > {page_budget_pages}) - compact layout will be enabled")
    else:
        logger.debug(f"Content within page budget ({estimated_pages:.1f} <= {page_budget_pages}) - compact layout not needed yet")
    
    # While over budget, trim in priority order
    while estimated_pages > page_budget_pages:
        original_pages = estimated_pages
        
        # 1) Drop experiences with priority=2 (keep priority=1)
        if trimmed_experiences and any(exp.get('priority', 1) == 2 for exp in trimmed_experiences):
            for i, exp in enumerate(trimmed_experiences):
                if exp.get('priority', 1) == 2:
                    logger.info(f"Dropping low-priority experience '{exp.get('title', 'Unknown')}' to fit {page_budget_pages}-page budget")
                    trimmed_experiences.pop(i)
                    used_compact_layout = True
                    break
            estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
            estimated_pages = estimated_lines / LINES_PER_PAGE
            if estimated_pages <= page_budget_pages:
                break
        
        # 2) Drop projects with priority=2
        if trimmed_projects and any(proj.get('priority', 1) == 2 for proj in trimmed_projects):
            for i, proj in enumerate(trimmed_projects):
                if proj.get('priority', 1) == 2:
                    logger.info(f"Dropping low-priority project '{proj.get('name', 'Unknown')}' to fit {page_budget_pages}-page budget")
                    trimmed_projects.pop(i)
                    used_compact_layout = True
                    break
            estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
            estimated_pages = estimated_lines / LINES_PER_PAGE
            if estimated_pages <= page_budget_pages:
                break
        
        # 3) Truncate bullets to max 2 per experience/project (more aggressive for 1-2 page target)
        for exp in trimmed_experiences:
            bullets = exp.get('bullets', [])
            if len(bullets) > 2:
                logger.info(f"Truncating experience '{exp.get('title', 'Unknown')}' bullets from {len(bullets)} to 2")
                exp['bullets'] = bullets[:2]
                used_compact_layout = True
        
        for proj in trimmed_projects:
            bullets = proj.get('bullets', [])
            if len(bullets) > 2:
                logger.info(f"Truncating project '{proj.get('name', 'Unknown')}' bullets from {len(bullets)} to 2")
                proj['bullets'] = bullets[:2]
                used_compact_layout = True
        
        estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
        estimated_pages = estimated_lines / LINES_PER_PAGE
        if estimated_pages <= page_budget_pages:
            break
        
        # 4) Truncate projects list beyond top 2
        if len(trimmed_projects) > 2:
            logger.info(f"Truncating projects list from {len(trimmed_projects)} to top 2")
            trimmed_projects = trimmed_projects[:2]
            used_compact_layout = True
            estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
            estimated_pages = estimated_lines / LINES_PER_PAGE
            if estimated_pages <= page_budget_pages:
                break
        
        # 5) Truncate oldest experiences (last entries) - more aggressive for 1-2 pages
        if len(trimmed_experiences) > 2:
            logger.info(f"Truncating experiences list from {len(trimmed_experiences)} to top 2")
            trimmed_experiences = trimmed_experiences[:2]
            used_compact_layout = True
            estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
            estimated_pages = estimated_lines / LINES_PER_PAGE
            if estimated_pages <= page_budget_pages:
                break
        
        # If no progress made, apply more aggressive trimming
        if estimated_pages >= original_pages:
            logger.warning(f"Standard trimming insufficient ({estimated_pages:.1f} pages), applying aggressive trimming")
            
            # Aggressive: Keep only top 2 experiences, 1 project, reduce all bullets to 1
            if len(trimmed_experiences) > 2:
                logger.info(f"Aggressively truncating experiences from {len(trimmed_experiences)} to top 2")
                trimmed_experiences = trimmed_experiences[:2]
                used_compact_layout = True
            
            if len(trimmed_projects) > 1:
                logger.info(f"Aggressively truncating projects from {len(trimmed_projects)} to top 1")
                trimmed_projects = trimmed_projects[:1]
                used_compact_layout = True
            
            # Reduce all bullets to 1 per item
            for exp in trimmed_experiences:
                bullets = exp.get('bullets', [])
                if len(bullets) > 1:
                    logger.info(f"Aggressively reducing experience '{exp.get('title', 'Unknown')}' bullets from {len(bullets)} to 1")
                    exp['bullets'] = bullets[:1]
                    used_compact_layout = True
            
            for proj in trimmed_projects:
                bullets = proj.get('bullets', [])
                if len(bullets) > 1:
                    logger.info(f"Aggressively reducing project '{proj.get('name', 'Unknown')}' bullets from {len(bullets)} to 1")
                    proj['bullets'] = bullets[:1]
                    used_compact_layout = True
            
            # Re-estimate
            estimated_lines = estimate_lines(trimmed_experiences, trimmed_projects, trimmed_skills_data, education_data)
            estimated_pages = estimated_lines / LINES_PER_PAGE
            
            # If still over budget, we've done our best - log warning but continue
            if estimated_pages > page_budget_pages:
                logger.warning(f"⚠️ Resume still exceeds {page_budget_pages}-page budget after aggressive trimming: {estimated_pages:.1f} pages. Consider manual editing.")
            break
    
    if used_compact_layout:
        logger.info(f"Final length estimate: {estimated_lines} lines (~{estimated_pages:.1f} pages) - compact layout enabled")
    else:
        logger.info(f"Final length estimate: {estimated_lines} lines (~{estimated_pages:.1f} pages) - within budget")
    
    return {
        "experiences": trimmed_experiences,
        "projects": trimmed_projects,
        "skills": trimmed_skills_data,
        "education": education_data,
        "used_compact_layout": used_compact_layout
    }


def build_resume_from_json_files(
    identity_path: Path,
    summary_path: Path,
    experience_path: Path,
    education_path: Path,
    skills_path: Path,
    projects_path: Optional[Path] = None,
    header_path: Optional[Path] = None,
    template_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    page_budget_pages: int = 2
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
    
    # Use centralized JSON loaders with schema validation
    from resume_builder.json_loaders import (
        load_summary_block, load_selected_experiences, load_selected_skills,
        load_education_block, load_selected_projects, load_header_block
    )
    
    # Check for refined summary first, fallback to regular summary
    summary_refined_path = summary_path.parent / "summary_refined.json"
    if summary_refined_path.exists():
        try:
            summary_refined_data = load_summary_block(summary_refined_path)
            if summary_refined_data.get('status') == 'success' and summary_refined_data.get('refined_summary'):
                logger.info("Using refined summary from summary_refined.json")
                summary = summary_refined_data.get('refined_summary', '')
            else:
                summary_data = load_summary_block(summary_path)
                summary = summary_data.get('summary', '')
        except Exception as e:
            logger.warning(f"Failed to load refined summary, using regular: {e}")
            summary_data = load_summary_block(summary_path)
            summary = summary_data.get('summary', '')
    else:
        summary_data = load_summary_block(summary_path)
        summary = summary_data.get('summary', '')
    
    exp_data = load_selected_experiences(experience_path)
    experiences = exp_data.get('selected_experiences', [])
    
    edu_data = load_education_block(education_path)
    education = edu_data.get('education', [])
    
    skills_json_data = load_selected_skills(skills_path)
    # New format: skills_json_data has 'skills' and optional 'groups'
    # Pass the entire dict to build_complete_resume which will handle it
    skills_data = {
        'skills': skills_json_data.get('skills', skills_json_data.get('selected_skills', [])),
        'groups': skills_json_data.get('groups')
    }
    
    projects = None
    if projects_path and projects_path.exists():
        proj_data = load_selected_projects(projects_path)
        projects = proj_data.get('selected_projects', [])
    
    header_data = None
    if header_path and header_path.exists():
        header_json_data = load_header_block(header_path)
        # load_header_block already converts old format to new format
        # Pass it directly - build_complete_resume will handle both formats
        header_data = header_json_data
    
    # Enforce length budget before building LaTeX
    condensed = enforce_length_budget(
        experiences=experiences,
        projects=projects or [],
        skills_data=skills_data,
        education_data=education,
        page_budget_pages=page_budget_pages
    )
    
    # Build resume with condensed content
    latex = builder.build_complete_resume(
        identity=identity,
        summary=summary,
        experiences=condensed["experiences"],
        education=condensed["education"],
        skills=condensed["skills"],  # Pass as dict with 'skills' and 'groups'
        projects=condensed["projects"] if condensed["projects"] else None,
        header_data=header_data,
        template_path=template_path
    )
    
    # Apply compact layout if needed
    # Also check final estimate - if still over budget, force compact layout
    from resume_builder.length_budget import estimate_lines as estimate_lines_global, TARGET_LINES_PER_PAGE
    
    # Get skills list (handle both dict and list formats)
    skills_list = condensed["skills"]
    if isinstance(skills_list, dict):
        skills_list = skills_list.get('skills', skills_list.get('selected_skills', []))
    
    final_estimated_lines = estimate_lines_global(
        summary,  # Use the summary that was passed in
        condensed["experiences"],
        condensed["projects"] or [],
        skills_list,
        condensed["education"]
    )
    final_estimated_pages = final_estimated_lines / TARGET_LINES_PER_PAGE
    
    # Force compact layout if final estimate still exceeds budget
    if not condensed["used_compact_layout"] and final_estimated_pages > page_budget_pages:
        logger.warning(f"Final estimate ({final_estimated_pages:.1f} pages) exceeds budget ({page_budget_pages}) - forcing compact layout")
        condensed["used_compact_layout"] = True
    elif condensed["used_compact_layout"]:
        logger.info(f"Compact layout already enabled (final estimate: {final_estimated_pages:.1f} pages)")
    else:
        logger.debug(f"Final estimate ({final_estimated_pages:.1f} pages) within budget - compact layout not needed")
    
    if condensed["used_compact_layout"]:
        logger.info("Compact layout is enabled - ensuring \\compactresumelayout is defined and called")
        # Always ensure \compactresumelayout is defined and called
        # Check if \compactresumelayout is already defined in the template
        # Also check for corrupted versions (missing backslashes)
        has_compact_command = (
            r'\newcommand{\compactresumelayout}' in latex or
            r'\newcommand*{\compactresumelayout}' in latex or
            r'\def\compactresumelayout' in latex
        )
        logger.debug(f"Compact command check: has_compact_command={has_compact_command}, latex length={len(latex)}")
        
        # Check for corrupted version and fix it
        if r'ewcommand{\compactresumelayout}' in latex or r'ewif\ifcompactresume' in latex:
            logger.warning("Detected corrupted compact layout definition (missing backslashes), fixing...")
            # Fix corrupted definitions
            latex = re.sub(r'ewif\s*\\ifcompactresume', r'\\newif\\ifcompactresume', latex)
            latex = re.sub(r'ewcommand\{\\compactresumelayout\}', r'\\newcommand{\\compactresumelayout}', latex)
            has_compact_command = True  # Mark as fixed
        
        # CRITICAL: Always inject the definition if not present (even if template had it, it might have been lost)
        # This ensures the definition is always present when compact layout is enabled
        if not has_compact_command:
            # Find the preamble end (before \begin{document})
            if r'\begin{document}' in latex:
                doc_start = latex.find(r'\begin{document}')
                preamble = latex[:doc_start]
                document_body = latex[doc_start:]
                
                # Check if enumitem is loaded (required for \setlist)
                has_enumitem = r'\usepackage{enumitem}' in latex or r'\usepackage[enumitem]' in latex
                
                # Inject compact layout definition before \begin{document}
                # Use explicit backslashes to ensure they're preserved
                compact_definition = "\n% Compact layout toggle for page budget enforcement (auto-injected)\n"
                compact_definition += "\\newif\\ifcompactresume\n"
                compact_definition += "\\compactresumefalse\n"
                
                # Add enumitem if not present (required for \setlist)
                if not has_enumitem:
                    compact_definition += "\\usepackage{enumitem}\n"
                
                compact_definition += "\n"
                compact_definition += "\\newcommand{\\compactresumelayout}{%\n"
                compact_definition += "  \\compactresumetrue\n"
                compact_definition += "  \\setlength{\\itemsep}{0.2em}\n"
                compact_definition += "  \\setlength{\\parskip}{0.15em}\n"
                compact_definition += "  \\setlist[itemize]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_definition += "  \\setlist[enumerate]{leftmargin=*, labelsep=0.4em, topsep=0.1em, itemsep=0.1em, parsep=0em}\n"
                compact_definition += "}\n"
                latex = preamble + compact_definition + document_body
                logger.info("Auto-injected \\compactresumelayout definition into template")
            else:
                logger.warning("Could not find \\begin{document} to inject compact layout definition")
        else:
            logger.debug("\\compactresumelayout command already defined in template")
        
        # Always inject compact layout toggle call (even if command is already defined)
        # Check if it's already called (look for the call in document body, not the definition in preamble)
        doc_start_pos = latex.find(r'\begin{document}')
        if doc_start_pos > 0:
            document_body = latex[doc_start_pos:]
            # Check if \compactresumelayout appears in document body (not as part of \newcommand)
            compact_pos = document_body.find(r'\compactresumelayout')
            if compact_pos >= 0:
                # Check if it's part of a \newcommand definition (look backwards)
                context_before = document_body[max(0, compact_pos-30):compact_pos]
                has_compact_call = r'\newcommand' not in context_before and r'\newcommand*' not in context_before
            else:
                has_compact_call = False
        else:
            has_compact_call = False
        
        if not has_compact_call:
            # Inject compact layout toggle after \begin{document}
            if r'\begin{document}' in latex:
                latex = latex.replace(
                    r'\begin{document}',
                    r'\begin{document}' + '\n\\compactresumelayout',
                    1  # Only replace first occurrence
                )
                logger.info("Auto-injected \\compactresumelayout call after \\begin{document}")
            # Fallback: inject before \makecvtitle if \begin{document} not found
            elif r'\makecvtitle' in latex:
                latex = latex.replace(
                    r'\makecvtitle',
                    r'\\compactresumelayout' + '\n\\makecvtitle',
                    1  # Only replace first occurrence
                )
                logger.info("Auto-injected \\compactresumelayout call before \\makecvtitle")
        else:
            logger.debug("\\compactresumelayout call already present in LaTeX")
        
        # Post-process again AFTER compact layout injection to fix any backslashes that got corrupted
        # This is a safety net in case the injection or template reading corrupted backslashes
        is_resumecv = bool(re.search(r'\\documentclass[^\n]*\{resumecv\}', latex))
        latex = builder._post_process_latex(latex, assume_class_loads_core_pkgs=is_resumecv)
    
    # Write to file if output path provided
    if output_path:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(latex, encoding='utf-8')
    
    return latex


def rebuild_resume_from_existing_json(
    output_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
    rendered_tex_path: Optional[Path] = None,
) -> Path:
    """
    Rebuild the LaTeX resume from existing JSON files without rerunning Crew.
    
    This is used after JSON edits (manual or LLM-based).
    
    Args:
        output_dir: Directory containing JSON files (defaults to OUTPUT_DIR)
        template_path: Optional custom LaTeX template path
        rendered_tex_path: Output path for rendered .tex file (defaults to output/generated/rendered_resume.tex)
        
    Returns:
        Path to the generated LaTeX file
    """
    from resume_builder.paths import OUTPUT_DIR, GENERATED_DIR, TEMPLATES
    
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    if rendered_tex_path is None:
        rendered_tex_path = GENERATED_DIR / "rendered_resume.tex"
    
    if template_path is None:
        template_path = TEMPLATES / "main.tex"
    
    # Standard JSON file paths
    identity_path = output_dir / "user_profile.json"
    summary_path = output_dir / "summary.json"
    experience_path = output_dir / "selected_experiences.json"
    education_path = output_dir / "education.json"
    skills_path = output_dir / "selected_skills.json"
    projects_path = output_dir / "selected_projects.json"  # Optional
    header_path = output_dir / "header.json"  # Optional
    
    # Call existing builder
    build_resume_from_json_files(
        identity_path=identity_path,
        summary_path=summary_path,
        experience_path=experience_path,
        education_path=education_path,
        skills_path=skills_path,
        projects_path=projects_path if projects_path.exists() else None,
        header_path=header_path if header_path.exists() else None,
        template_path=template_path if template_path.exists() else None,
        output_path=rendered_tex_path,
        page_budget_pages=2
    )
    
    logger.info(f"Rebuilt resume LaTeX from existing JSON files: {rendered_tex_path}")
    return rendered_tex_path


def repair_latex_file(tex_content: str, *, force: bool = False) -> str:
    """
    Repair LaTeX resume file according to comprehensive LLM repair guidelines.
    
    This function is aggressive and converts ModernCV/resumecv to article class.
    Only run when explicitly opted in (force=True) or when detecting broken ModernCV artifacts.
    
    Comprehensive fixes:
    1. Replace moderncv/resumecv with article class
    2. Add proper UTF-8 encoding for Unicode emoji support
    3. Add hyphenation disabling (hyphenat package + sloppy mode)
    4. Simplify geometry package
    5. Remove microtype completely
    6. Replace FontAwesome icons with Unicode/text
    7. Simplify header section (remove complex tabular, use centered lines)
    8. Replace customcventry and awardentry with simpler paragraph-based macros
    9. Keep only essential packages
    10. Fix custom macros (replace \maincolumnwidth with \textwidth)
    11. Fix link formatting
    12. Remove math symbols used as icons
    
    Args:
        tex_content: Original LaTeX content as string
        force: If True, always run repairs. If False, only run if broken ModernCV detected.
        
    Returns:
        Repaired LaTeX content as string
    """
    content = tex_content
    
    # Only run aggressive repairs if explicitly forced or if we detect broken ModernCV
    # Broken ModernCV = has \documentclass{moderncv} but no \makecvtitle/\name compile path
    has_moderncv = bool(re.search(r'\\documentclass(\[[^\]]*\])?\{moderncv\}', content))
    has_cv_compile_path = bool(re.search(r'\\(?:makecvtitle|name)\{', content))
    should_repair = force or (has_moderncv and not has_cv_compile_path)
    
    if not should_repair:
        # Only apply minimal fixes (lost backslashes, broken textcolor, etc.)
        # without class conversion
        return content
    
    # If this is already using resumecv, skip the aggressive article conversion.
    # The resumecv class provides \cventry, \cvitem, \makecvtitle, etc., so we don't need to replace them.
    is_resumecv = bool(re.search(r'\\documentclass(\[[^\]]*\])?\{resumecv\}', content))
    converting_to_article = not is_resumecv
    
    if converting_to_article:
        # 1. Replace document class: moderncv -> article
        # Note: resumecv won't be in this branch since we checked is_resumecv above
        content = re.sub(
            r'\\documentclass(\[[^\]]*\])?\{moderncv\}',
            r'\\documentclass[11pt,a4paper]{article}',
            content
        )
    
    # IMPORTANT: Replace \maincolumnwidth and \hintscolumnwidth FIRST, before removing definitions
    # This ensures they're replaced even inside command definitions
    content = re.sub(r'\\maincolumnwidth', r'\\textwidth', content)
    content = re.sub(r'\\hintscolumnwidth', r'0.2\\textwidth', content)
    
    # Remove moderncv-specific commands that won't work with article
    # Only do this if we're converting to article (resumecv provides these commands)
    if converting_to_article:
        content = re.sub(r'\\moderncvstyle\{[^\}]*\}', '', content)
        content = re.sub(r'\\moderncvcolor\{[^\}]*\}', '', content)
        content = re.sub(r'\\nopagenumbers\s*', '', content)
        content = re.sub(r'\\makecvtitle\s*', '', content)
    
    # Remove custom command definitions that use tabular (we'll replace their usage)
    # Use a function to properly match nested braces
    def remove_command_definition(content, cmd_name):
        """Remove a \newcommand definition by matching balanced braces"""
        pattern = rf'\\newcommand\*?\{{\\{cmd_name}\}}[^\n]*\n'
        match = re.search(pattern, content)
        if not match:
            return content
        
        start = match.start()
        # Find the opening brace of the definition body
        body_start = match.end()
        brace_count = 0
        i = body_start
        while i < len(content):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found the closing brace
                    end = i + 1
                    # Remove the entire definition including the newline after
                    if end < len(content) and content[end] == '\n':
                        end += 1
                    return content[:start] + content[end:]
            i += 1
        return content
    
    # Remove both command definitions
    content = remove_command_definition(content, 'customcventry')
    content = remove_command_definition(content, 'awardentry')
    
    # 2. Build proper preamble for article class (only when converting)
    if converting_to_article:
        # Find documentclass position
        docclass_match = re.search(r'\\documentclass[^\n]*\n', content)
        if docclass_match:
            insert_pos = docclass_match.end()
            
            # Build preamble packages (in order)
            preamble_packages = [
                '\\usepackage[utf8]{inputenc}',
                '\\usepackage[T1]{fontenc}',
                '\\usepackage[margin=1in]{geometry}',
                '\\usepackage{hyperref}',
                '\\usepackage{xcolor}',
                '\\usepackage{enumitem}',
                '\\usepackage{ragged2e}',
                '\\usepackage{amssymb}',
                '\\usepackage{titlesec}',
                '\\usepackage{multicol}',
                '\\usepackage{setspace}',
                '\\usepackage[none]{hyphenat}',  # Disable hyphenation
            ]
            
            # Check what's already there
            existing_packages = set(re.findall(r'\\usepackage.*?\{([^\}]+)\}', content))
            
            # Insert missing packages
            packages_to_add = []
            for pkg_line in preamble_packages:
                pkg_name = re.search(r'\{([^\}]+)\}', pkg_line).group(1) if re.search(r'\{([^\}]+)\}', pkg_line) else ''
                if pkg_name and pkg_name not in existing_packages:
                    packages_to_add.append(pkg_line)
            
            if packages_to_add:
                content = content[:insert_pos] + '\n'.join(packages_to_add) + '\n' + content[insert_pos:]
            
            # Add formatting commands after packages
            formatting_commands = [
                '\\setstretch{1.1}',
                '\\setlist[itemize]{leftmargin=1.2em, topsep=0.2em, itemsep=0.2em}',
                '\\titleformat{\\section}{\\large\\bfseries\\uppercase}{\\thesection}{0.5em}{}',
                '\\sloppy  % Disable strict line breaking to prevent overfull hboxes',
            ]
            
            # Find position after last usepackage
            last_pkg_match = list(re.finditer(r'\\usepackage[^\n]*\n', content))
            if last_pkg_match:
                insert_pos = last_pkg_match[-1].end()
            else:
                insert_pos = docclass_match.end()
            
            content = content[:insert_pos] + '\n'.join(formatting_commands) + '\n' + content[insert_pos:]
        
        # Replace geometry package if it exists with simpler version (only when converting)
        content = re.sub(
            r'\\usepackage(\[[^\]]*\])?\{geometry\}',
            r'\\usepackage[margin=1in]{geometry}',
            content
        )
        
        # 3. Remove microtype package (only when converting to article)
        content = re.sub(r'\\usepackage(\[[^\]]*\])?\{microtype\}.*\n', '', content)
        content = re.sub(r'\\PassOptionsToPackage\{[^\}]*\}\{microtype\}.*\n', '', content)
        content = re.sub(r'\\microtypesetup\{[^\}]*\}.*\n', '', content)
        
        # 4. Remove fontawesome5 package and replace icons with Unicode/text (only when converting to article)
        content = re.sub(r'\\usepackage(\[[^\]]*\])?\{fontawesome5?\}.*\n', '', content)
        content = re.sub(r'%[^\n]*fontawesome[^\n]*\n', '', content)
        
        # Replace FontAwesome commands with Unicode equivalents
        fa_replacements = {
            r'\\faMobile\s*': '📞 ',
            r'\\faPhone\s*': '📞 ',
            r'\\faEnvelope\s*': '📧 ',
            r'\\faAt\s*': '📧 ',
            r'\\faHome\s*': '🏠 ',
            r'\\faGlobe\s*': '🌐 ',
            r'\\faLinkedin\s*': 'LinkedIn: ',
            r'\\faGithub\s*': 'GitHub: ',
            r'\\faGoogle\s*': 'Google Scholar: ',
            r'\\faTwitter\s*': 'Twitter: ',
            r'\\faFacebook\s*': 'Facebook: ',
        }
        
        for pattern, replacement in fa_replacements.items():
            content = re.sub(pattern, replacement, content)
    
    # 5. Replace customcventry and awardentry usages with formatted content
    # First, define a simple \entry macro before \begin{document}
    if '\\newcommand{\\entry}' not in content and '\\begin{document}' in content:
        doc_start = content.find('\\begin{document}')
        entry_macro = '\\newcommand{\\entry}[3]{\\noindent\\textbf{#1} \\hfill \\textit{#2}\\par\n#3\\par\\vspace{0.5em}}\n\n'
        content = content[:doc_start] + entry_macro + content[doc_start:]
    
    # Function to extract balanced braces content
    # extract_braces moved to resume_builder.utils
    
    # Replace \customcventry[spacing]{date}{location}{title}{location2}{empty}{content}
    def replace_customcventry_usage(match):
        full_text = match.group(0)
        # Skip optional [spacing] if present
        pos = len(r'\customcventry')
        if pos < len(full_text) and full_text[pos] == '[':
            # Skip to closing ]
            pos = full_text.find(']', pos) + 1
        
        # Extract 6 arguments
        args = []
        for _ in range(6):
            if pos >= len(full_text) or full_text[pos] != '{':
                break
            arg_content, pos = extract_braces(full_text, pos)
            if arg_content is None:
                break
            args.append(arg_content)
        
        if len(args) >= 6:
            # args[0] = date, args[1] = location, args[2] = title, args[3] = location2, args[4] = empty, args[5] = content
            date = args[0]
            title = args[2]
            content_text = args[5]
            # Format: Title on left, Date on right, then content
            return f'\\noindent\\textbf{{{title}}} \\hfill \\textit{{{date}}}\\par\n{content_text}\\par\\vspace{{0.5em}}'
        return full_text  # Return original if parsing fails
    
    # Replace \customcventry calls (handle nested braces and multi-line arguments)
    # Process line by line to handle multi-line arguments better
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line starts with \customcventry
        if line.strip().startswith('\\customcventry'):
            # Collect the command and all its arguments (6 arguments)
            cmd_line = line
            args = []
            pos = len('\\customcventry')
            # Skip optional [spacing] if present
            if pos < len(cmd_line) and cmd_line[pos] == '[':
                pos = cmd_line.find(']', pos) + 1
            
            # Collect arguments line by line
            current_arg = ""
            brace_count = 0
            j = i
            arg_start_pos = pos
            
            while j < len(lines) and len(args) < 6:
                if j == i:
                    text = cmd_line[arg_start_pos:]
                else:
                    text = lines[j]
                
                for char in text:
                    if char == '{':
                        if brace_count == 0:
                            current_arg = ""
                        brace_count += 1
                        if brace_count > 1:
                            current_arg += char
                    elif char == '}':
                        brace_count -= 1
                        if brace_count > 0:
                            current_arg += char
                        elif brace_count == 0:
                            # Complete argument found
                            args.append(current_arg)
                            current_arg = ""
                            if len(args) >= 6:
                                break
                    else:
                        if brace_count > 0:
                            current_arg += char
                
                if len(args) >= 6:
                    break
                j += 1
            
            # If we have 6 arguments, format them
            if len(args) >= 6:
                date = args[0]
                title = args[2]
                content_text = args[5]
                formatted = f'\\noindent\\textbf{{{title}}} \\hfill \\textit{{{date}}}\\par\n{content_text}\\par\\vspace{{0.5em}}'
                fixed_lines.append(formatted)
                i = j + 1  # Skip all lines we processed
                continue
        
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    # Also try regex replacement for any remaining single-line cases
    pattern = r'\\customcventry(?:\[[^\]]*\])?(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}){6}'
    content = re.sub(pattern, replace_customcventry_usage, content, flags=re.DOTALL)
    
    # Also handle cases where command was removed but arguments remain (bare braces)
    # Pattern: {arg1}{arg2}{arg3}{arg4}{arg5}{arg6} followed by content in braces
    def fix_bare_braces(match):
        # This is a fallback for when \customcventry was already removed
        # We'll format it as a simple entry
        args_text = match.group(0)
        # Try to extract arguments
        args = []
        pos = 0
        for _ in range(6):
            if pos >= len(args_text) or args_text[pos] != '{':
                break
            arg_content, pos = extract_braces(args_text, pos)
            if arg_content is None:
                break
            args.append(arg_content)
        
        if len(args) >= 6:
            date = args[0]
            title = args[2]
            content_text = args[5]
            return f'\\noindent\\textbf{{{title}}} \\hfill \\textit{{{date}}}\\par\n{content_text}\\par\\vspace{{0.5em}}'
        return args_text
    
    # Fix bare brace sequences (from removed \customcventry commands)
    # Look for lines starting with bare braces that are arguments
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line starts with a bare brace (not part of a command)
        if re.match(r'^\s*\{[^\\]', line):
            # Collect consecutive lines with bare braces (likely arguments)
            brace_lines = [line]
            j = i + 1
            while j < len(lines) and j < i + 15:
                next_line = lines[j]
                # Stop if we hit a section or non-brace line that's not empty
                if re.match(r'^\s*\\section', next_line) or (not re.match(r'^\s*\{', next_line) and next_line.strip() and not next_line.strip().startswith('%')):
                    break
                if re.match(r'^\s*\{', next_line):
                    brace_lines.append(next_line)
                j += 1
            
            # If we have 6+ brace lines, this is likely a removed \customcventry
            if len(brace_lines) >= 6:
                # Combine and extract arguments
                combined = '\n'.join(brace_lines)
                args = []
                pos = 0
                for _ in range(7):  # 6 args + content
                    if pos >= len(combined):
                        break
                    next_brace = combined.find('{', pos)
                    if next_brace == -1:
                        break
                    arg_content, pos = extract_braces(combined, next_brace)
                    if arg_content is None:
                        break
                    args.append(arg_content)
                
                if len(args) >= 6:
                    date = args[0]
                    title = args[2] if len(args) > 2 else "Position"
                    content_text = args[5] if len(args) > 5 else (args[-1] if args else "")
                    formatted = f'\\noindent\\textbf{{{title}}} \\hfill \\textit{{{date}}}\\par\n{content_text}\\par\\vspace{{0.5em}}'
                    fixed_lines.append(formatted)
                    # Skip all the brace lines we just processed
                    i += len(brace_lines)
                    continue
        
        fixed_lines.append(line)
        i += 1
    content = '\n'.join(fixed_lines)
    
    # Replace \awardentry{title}{location}{date}
    def replace_awardentry(match):
        full_text = match.group(0)
        pos = len(r'\awardentry')
        args = []
        for _ in range(3):
            if pos >= len(full_text) or full_text[pos] != '{':
                break
            arg_content, pos = extract_braces(full_text, pos)
            if arg_content is None:
                break
            args.append(arg_content)
        
        if len(args) >= 3:
            title = args[0]
            location = args[1]
            date = args[2]
            return f'\\noindent\\textbf{{{title}}} \\hfill \\textit{{{date}}}\\par\n{location}\\par\\vspace{{0.5em}}'
        return full_text
    
    content = re.sub(r'\\awardentry\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', replace_awardentry, content)
    
    # --- Add simple fallbacks for \cventry and \cvitem when we converted to article ---
    # Only do this if we're NOT using resumecv (which provides these commands)
    if not is_resumecv:
        def _extract_args(cmd_text: str, n: int) -> list:
            """Extract n balanced brace arguments from cmd_text starting at position 0."""
            args, pos, L = [], 0, len(cmd_text)
            for _ in range(n):
                # find next '{'
                while pos < L and cmd_text[pos] != '{':
                    pos += 1
                if pos >= L:
                    break
                # balanced brace extraction
                depth, pos, start = 0, pos, pos + 1
                while pos < L:
                    ch = cmd_text[pos]
                    if ch == '\\':  # skip escape
                        pos += 2
                        continue
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        if depth == 0:
                            # end of this argument
                            args.append(cmd_text[start:pos])
                            pos += 1
                            break
                        depth -= 1
                    pos += 1
            return args

        # \cventry{dates}{title}{org}{location}{left}{desc} -> bold Title — Org (Location) ..... dates \n desc
        def _replace_cventry(m):
            raw = m.group(0)
            args = _extract_args(raw, 6)
            if len(args) < 6:
                return raw
            dates, title, org, loc, _left, desc = args
            line = f"\\noindent\\textbf{{{title}}} — {org}"
            if loc.strip():
                line += f" ({loc})"
            line += f" \\hfill \\textit{{{dates}}}\\par\n"
            if desc.strip():
                line += desc + "\\par\n"
            line += "\\vspace{0.5em}"
            return line

        content = re.sub(
            r'\\cventry(?:\[[^\]]*\])?(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}){6}',
            _replace_cventry, content, flags=re.DOTALL
        )

        # \cvitem{label}{desc} -> bold label: desc
        def _replace_cvitem(m):
            raw = m.group(0)
            args = _extract_args(raw, 2)
            if len(args) < 2:
                return raw
            label, desc = args
            return f"\\noindent\\textbf{{{label}}} {desc}\\par\\vspace{{0.3em}}"

        content = re.sub(
            r'\\cvitem(?:\[[^\]]*\])?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            _replace_cvitem, content, flags=re.DOTALL
        )
    
    # 6. Simplify header section - replace complex tabular with centered lines
    def simplify_header(match):
        header_content = match.group(0)
        # Extract contact info from tabular or text
        phone_match = re.search(r'\(?\d{3}\)?\s*\d{3}[-.]?\d{4}', header_content)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', header_content)
        website_match = re.search(r'https?://[^\s\)\}]+', header_content)
        linkedin_match = re.search(r'linkedin\.com/in/([\w-]+)', header_content, re.IGNORECASE)
        github_match = re.search(r'github\.com/([\w-]+)', header_content, re.IGNORECASE)
        scholar_match = re.search(r'scholar\.google\.com[^\s\)\}]+', header_content, re.IGNORECASE)
        address_match = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2}(?:,\s*\d{5})?)', header_content)
        
        # Extract name if present
        name_match = re.search(r'\\textbf\{([^}]+)\}', header_content)
        name_text = name_match.group(1) if name_match else None
        
        # Extract tagline if present (text between center blocks)
        tagline_match = re.search(r'AI/ML Engineer.*?ROS2', header_content)
        tagline = tagline_match.group(0) if tagline_match else None
        
        parts = []
        if name_text:
            parts.append(f'{{\\LARGE \\textbf{{{name_text}}}}}')
        if tagline:
            parts.append(tagline)
        
        contact_parts = []
        if phone_match:
            contact_parts.append(f"📞 {phone_match.group(0)}")
        if email_match:
            contact_parts.append(f"📧 {email_match.group(0)}")
        if address_match:
            contact_parts.append(f"📍 {address_match.group(0)}")
        
        # Extract URLs with proper href formatting
        if website_match:
            url = website_match.group(0).rstrip(')').rstrip('}').rstrip(',')
            contact_parts.append(f"🌐 \\href{{{url}}}{{Personal Website}}")
        if linkedin_match:
            username = linkedin_match.group(1)
            contact_parts.append(f"🔗 \\href{{https://linkedin.com/in/{username}}}{{LinkedIn}}")
        if github_match:
            username = github_match.group(1)
            contact_parts.append(f"💻 \\href{{https://github.com/{username}}}{{GitHub}}")
        if scholar_match:
            url = scholar_match.group(0).rstrip(')').rstrip('}').rstrip(',')
            contact_parts.append(f"🎓 \\href{{{url}}}{{Google Scholar}}")
        
        if contact_parts:
            parts.append(' \\quad '.join(contact_parts))
        
        if parts:
            return '\\begin{center}\n' + ' \\\\[4pt]\n'.join(parts) + '\n\\end{center}\n'
        return match.group(0)  # Return original if we can't parse
    
    # Match center blocks with tabular that contain contact info (more flexible pattern)
    content = re.sub(
        r'\\begin\{center\}.*?\\begin\{tabular\}.*?\\end\{tabular\}.*?\\end\{center\}',
        simplify_header,
        content,
        flags=re.DOTALL
    )
    
    # Also handle center blocks that might have multiple lines
    content = re.sub(
        r'\\begin\{center\}.*?\\textbf\{[^}]*\}.*?\\end\{center\}',
        simplify_header,
        content,
        flags=re.DOTALL
    )
    
    # Remove math symbols used as icons (like $\mathbb{E}$, $\mathbb{W}$, $\mathbb{G}$)
    content = re.sub(r'\$\\mathbb\{[EWG]\}\$', '', content)
    content = re.sub(r'\\enspace\s*\$\\mathbb\{[EWG]\}\$\\enspace', '', content)
    
    # 7. Remove non-essential packages that conflict
    packages_to_remove = ['fontawesome', 'fontawesome5', 'microtype', 'lmodern']
    
    # Remove non-essential packages (but keep inputenc, fontenc, geometry, etc. that we added)
    for package_name in packages_to_remove:
        # Match with or without options
        pattern = r'\\usepackage(\[[^\]]*\])?\{' + re.escape(package_name) + r'\}\s*\n?'
        content = re.sub(pattern, '', content)
    
    # 8. Fix custom macros: replace \maincolumnwidth with \textwidth
    # (Already done earlier, but do it again in case anything was missed)
    content = re.sub(r'\\maincolumnwidth', r'\\textwidth', content)
    
    # 8.5. Fix missing backslashes in commands (anywhere in the file, not just line starts)
    # Fix: oindent -> \noindent (anywhere in content) - MUST be before other fixes
    content = re.sub(r'(?<!\\)oindent(?!\w)', r'\\noindent', content)
    # Fix: extbf{ -> \textbf{ (anywhere in content)
    content = re.sub(r'(?<!\\)extbf\{', r'\\textbf{', content)
    # Fix: ewcommand -> \newcommand (anywhere in content) - MUST be before other fixes
    content = re.sub(r'(?<!\\)ewcommand', r'\\newcommand', content)
    # Fix: ewline -> \newline
    content = re.sub(r'(?<!\\)ewline(?!\w)', r'\\newline', content)
    # Fix: ewpage -> \newpage
    content = re.sub(r'(?<!\\)ewpage(?!\w)', r'\\newpage', content)
    
    # 8.5.1. Fix mangled macros with stray \t (tab characters)
    # Fix: \t\textbf -> \textbf (remove tab before command)
    content = re.sub(r'\\t\\textbf', r'\\textbf', content)
    # Fix any other \t\ before commands (remove tab only) - be careful with backreferences
    content = re.sub(r'\\t\\([a-zA-Z@]+)', r'\\\1', content)
    
    # 8.5.2. Fix broken \textcolor commands
    # Fix: \textcolor\{black -> \textcolor{black}{
    content = re.sub(r'\\textcolor\\\{black\s+', r'\\textcolor{black}{', content)
    # Fix broken name block pattern: \textcolor\{black Name \textcolor{black}\n\end{center}\n\vspace{1em}{Lastname}}
    # Replace entire broken block with fixed version
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+\\textcolor\\\{black\s+([^}]+)\s+\\textcolor\{black\}\s*\\end\{center\}\s*\\vspace\{1em\}\{([^}]+)\}\}',
        r'\\begin{center}\n{\\Huge\\bfseries \\textcolor{black}{\1 \2}}\n\\end{center}\n\\vspace{1em}',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    # Also handle simpler broken pattern: \textcolor\{black Name} followed by separate Lastname
    content = re.sub(
        r'\\textcolor\\\{black\s+([^}]+)\}\s*\n\s*\\end\{center\}\s*\n\s*\\vspace\{1em\}\{([^}]+)\}\}',
        r'\\textcolor{black}{\1 \2}}\n\\end{center}\n\\vspace{1em}',
        content,
        flags=re.MULTILINE
    )
    
    # 8.5.3. Fix role line with \t\textbf
    # Fix: {\LARGE \t\textbf{AI/ML Engineer \textbar{}} -> {\LARGE \textbf{AI/ML Engineer} \textbar{}
    content = re.sub(
        r'\{\\LARGE\s+\\t\\textbf\{([^}]+)\s+\\textbar\{\}\}',
        r'{\\LARGE \\textbf{\1} \\textbar{}',
        content
    )
    
    # 8.6. Fix orphaned fragments more aggressively
    # Remove specific orphaned patterns that appear anywhere
    content = re.sub(r'^\s*\{@\{\}l\}\s*$', '', content, flags=re.MULTILINE)
    # Remove stray control line: \else\\[.25em]% (exact match) - handle both \else and else
    content = re.sub(r'^\s*\\?else\\\\\[\.25em\]%\s*$', '', content, flags=re.MULTILINE)
    # Remove multiple consecutive orphaned fragments
    content = re.sub(r'\{@\{\}l\}\s*\n\s*\\else\\\[\.25em\]%\s*\n\s*\{@\{\}l\}', '', content)
    
    # 8.7. Fix href URLs to ensure they use https://
    # Fix URLs that don't start with http:// or https://
    def fix_href_url(match):
        url = match.group(1)
        text = match.group(2) if match.group(2) else url
        # If URL doesn't start with http:// or https://, add https://
        if not url.startswith('http://') and not url.startswith('https://'):
            # Check if it's a domain-like string (contains .com, .org, etc.)
            if '.' in url and not url.startswith('.'):
                url = 'https://' + url
        return f'\\href{{{url}}}{{{text}}}'
    
    # Match \href{url}{text} or \href{url}
    content = re.sub(r'\\href\{([^}]+)\}(?:\{([^}]*)\})?', fix_href_url, content)
    
    # 8.8. Fix encoding issues: Replace malformed Unicode characters with proper text
    # Common encoding issues: (replacement characters) or broken emoji
    # Replace with appropriate text or remove if it's clearly broken
    # Remove Unicode replacement character (U+FFFD) which appears as when encoding fails
    # Remove emojis that will choke pdflatex (keep text/hyperlinks only)
    # Only remove if NOT using xelatex (check for xelatex directive or fontspec package)
    has_xelatex = bool(re.search(r'%\s*!TeX\s+program\s*=\s*xelatex', content, re.IGNORECASE))
    has_fontspec = bool(re.search(r'\\usepackage[^\n]*\{fontspec\}', content, re.IGNORECASE))
    
    if not (has_xelatex or has_fontspec):
        # Remove: 📞, 📧, 📍, 🌐, 🔗, 💻, 🎓 (pdflatex can't handle them)
        emoji_pattern = r'[📞📧📍🌐🔗💻🎓]'
        content = re.sub(emoji_pattern, '', content)
    # Remove replacement characters and control characters (but keep newlines, tabs, carriage returns)
    content = ''.join(char for char in content if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')
    # Specifically remove common broken encoding patterns
    content = re.sub(r'[\uFFFD]', '', content)  # Remove replacement characters
    
    # 8.9. Ensure \begin{document} comes before any content
    # Move \begin{document} to come before any \begin{center} or text content
    doc_start_match = re.search(r'\\begin\{document\}', content)
    if doc_start_match:
        doc_start_pos = doc_start_match.start()
        # Find first \begin{center} before \begin{document}
        center_before_doc = re.search(r'\\begin\{center\}', content[:doc_start_pos])
        if center_before_doc:
            # Move \begin{document} to before the first \begin{center}
            # Find the preamble end (after \sloppy or last package)
            preamble_end = max(
                content.rfind('\\sloppy', 0, center_before_doc.start()),
                content.rfind('\\usepackage', 0, center_before_doc.start())
            )
            if preamble_end > 0:
                # Find end of line after preamble
                preamble_end = content.find('\n', preamble_end) + 1
                # Extract \begin{document} and move it
                doc_block = content[doc_start_pos:doc_start_match.end()]
                # Remove it from original position
                content = content[:doc_start_pos] + content[doc_start_match.end():]
                # Insert it before the first \begin{center}
                content = content[:preamble_end] + doc_block + '\n\n' + content[preamble_end:]
    
    # Also replace \hintscolumnwidth if it exists (moved here to avoid duplication)
    content = re.sub(r'\\hintscolumnwidth', r'0.2\\textwidth', content)
    
    # 9. Fix link formatting: ensure \href is inside \textbf when needed
    # Simple approach: wrap \href{url}{text} with \textbf if not already wrapped
    # We'll do this by checking the context around each match
    def fix_link_format(match):
        full_match = match.group(0)
        url = match.group(1)
        text = match.group(2)
        # Simple check: if the match already contains \textbf, don't wrap again
        # This is a heuristic - we'll wrap all links that aren't obviously already in \textbf
        if '\\textbf' in full_match:
            return full_match
        return f'\\textbf{{\\href{{{url}}}{{{text}}}}}'
    
    # Fix links - but be careful not to double-wrap
    # Simple approach: only wrap \href that are NOT already inside \textbf{...\href...}
    # We'll do this in two passes: first mark those already wrapped, then wrap the rest
    # Replace \textbf{\href{...}{...}} with a placeholder, then wrap remaining \href, then restore
    placeholders = {}
    placeholder_counter = [0]
    
    def store_wrapped_link(match):
        placeholder_id = f"__WRAPPED_LINK_{placeholder_counter[0]}__"
        placeholder_counter[0] += 1
        placeholders[placeholder_id] = match.group(0)
        return placeholder_id
    
    # First, store already-wrapped links
    content = re.sub(
        r'\\textbf\{\\href\{[^\}]+\}\{[^\}]+\}\}',
        store_wrapped_link,
        content
    )
    
    # Now wrap remaining \href commands
    content = re.sub(
        r'\\href\{([^\}]+)\}\{([^\}]+)\}',
        lambda m: f'\\textbf{{\\href{{{m.group(1)}}}{{{m.group(2)}}}}}',
        content
    )
    
    # Restore the original wrapped links
    for placeholder_id, original in placeholders.items():
        content = content.replace(placeholder_id, original)
    
    # 10. Remove any remaining font expansion disabling code (not needed with article)
    content = re.sub(r'\\pdfprotrudechars=0.*\n', '', content)
    content = re.sub(r'\\pdfadjustspacing=0.*\n', '', content)
    content = re.sub(r'\\AtBeginDocument\{[^\}]*pdfprotrude[^\}]*\}', '', content, flags=re.DOTALL)
    
    # Remove \name command and replace with manual name if needed
    name_match = re.search(r'\\name\{([^\}]+)\}\{([^\}]+)\}', content)
    if name_match:
        first = name_match.group(1)
        last = name_match.group(2)
        # Remove \textcolor{black}{...} or \textcolor{black}... patterns
        first = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', first)
        first = re.sub(r'\\textcolor\{[^\}]+\}', '', first)
        first = first.strip('{}').strip()
        last = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', last)
        last = re.sub(r'\\textcolor\{[^\}]+\}', '', last)
        last = last.strip('{}').strip()
        # Escape special LaTeX characters in names (but NOT backslashes - we don't want \textbackslash)
        first = first.replace('&', '\\&').replace('%', '\\%').replace('$', '\\$').replace('#', '\\#').replace('^', '\\textasciicircum{}').replace('_', '\\_').replace('{', '\\{').replace('}', '\\}')
        last = last.replace('&', '\\&').replace('%', '\\%').replace('$', '\\$').replace('#', '\\#').replace('^', '\\textasciicircum{}').replace('_', '\\_').replace('{', '\\{').replace('}', '\\}')
        # Replace \name with centered name - ensure proper brace matching
        name_replacement = f'\\begin{{center}}\n{{\\Huge\\bfseries {first} {last}}}\n\\end{{center}}\n\\vspace{{1em}}'
        # Find and replace the \name command using string replacement
        name_pattern = re.search(r'\\name\{[^\}]+\}\{[^\}]+\}', content)
        if name_pattern:
            content = content[:name_pattern.start()] + name_replacement + content[name_pattern.end():]
    
    # Fix broken name patterns that were already replaced incorrectly
    # Pattern: {\Huge\bfseries \textbackslash{}textcolor{black John}\n\end{center}\n\vspace{1em}}{\textcolor{black}{Doe}}
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+\\textbackslash\{\}textcolor\{[^}]+\}\{([^}]+)\}\s*\\end\{center\}\s*\\vspace\{[^}]+\}\}\{([^}]+)\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1 \2}\n\\end{center}\n\\vspace{1em}',
        content,
        flags=re.MULTILINE
    )
    # Pattern: {\Huge\bfseries \textbackslash{}textcolor{black John}\n\end{center}\n\vspace{1em}}{\textcolor{black}{Doe}}
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+\\textcolor\{[^}]+\}\{([^}]+)\}\s*\\end\{center\}\s*\\vspace\{[^}]+\}\}\{([^}]+)\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1 \2}\n\\end{center}\n\\vspace{1em}',
        content,
        flags=re.MULTILINE
    )
    # Pattern: {\Huge\bfseries \textbackslash{}textcolor{black John} (single line, broken)
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+\\textbackslash\{\}textcolor\{[^}]+\}\{([^}]+)\}\s*\\end\{center\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1}\n\\end{center}',
        content,
        flags=re.MULTILINE
    )
    
    # Clean up any orphaned fragments from removed command definitions
    # Remove lines that are clearly fragments from tabular environments
    lines = content.split('\n')
    cleaned_lines = []
    i = 0
    in_document = False
    while i < len(lines):
        line = lines[i]
        
        # Track when we enter document environment
        if '\\begin{document}' in line:
            in_document = True
        
        # Skip lines that are clearly fragments (both before and after \begin{document})
        # Orphaned fragments can appear anywhere
        # Skip orphaned tabular column specs (can appear anywhere)
        if re.match(r'^\s*\{@\{[^}]*\}\}\s*$', line):
            i += 1
            continue
        # Skip orphaned command argument fragments
        if re.match(r'^\s*\{\\bfseries\s*#\d+\}\\?\\?\s*$', line) or \
           re.match(r'^\s*\{\\itshape\s*#\d+\}\\?\\?\s*$', line) or \
           re.match(r'^\s*\\ifx&#\d+&%\s*$', line) or \
           re.match(r'^\s*\\else\\\[\.\d+em\]%\s*$', line) or \
           re.match(r'^\s*\\else\\\[\.25em\]%\s*$', line) or \
           re.match(r'^\s*\\begin\{minipage\}.*#\d+.*\\end\{minipage\}%\s*$', line) or \
           re.match(r'^\s*\\fi\s*$', line) or \
           re.match(r'^\s*\\par\\addvspace\{#\d+\}\}\s*$', line):
            i += 1
            continue
        # Skip orphaned \hfill lines
        if re.match(r'^\s*\\hfill\s*$', line):
            i += 1
            continue
        # Skip orphaned tabular environments (begin without proper context) - can appear anywhere
        if re.match(r'^\s*\\begin\{tabular\}', line):
            # Check if this is part of a valid structure or orphaned
            # Look ahead to see if there's an end
            found_end = False
            for j in range(i+1, min(i+10, len(lines))):
                if '\\end{tabular}' in lines[j]:
                    found_end = True
                    break
            if found_end:
                # Check if this tabular is orphaned (not in a command definition context)
                # If the previous line doesn't have \newcommand or similar, it might be orphaned
                if i > 0 and '\\newcommand' not in lines[i-1] and '\\customcventry' not in lines[i-1] and '\\awardentry' not in lines[i-1]:
                    # Skip this tabular block
                    while i < len(lines) and '\\end{tabular}' not in lines[i]:
                        i += 1
                    if i < len(lines):
                        i += 1  # Skip the \end{tabular} line too
                    continue
        # Skip lines that are just closing braces from removed definitions
        if re.match(r'^\s*\\end\{tabular\}\s*\}\s*$', line) and i > 0:
            # Check if there's a matching begin nearby
            has_matching_begin = False
            for j in range(max(0, i-10), i):
                if '\\begin{tabular}' in lines[j]:
                    has_matching_begin = True
                    break
            if not has_matching_begin:
                i += 1
                continue
        # Skip orphaned single argument lines like "{@{}l}" or "#1" or "\end{tabular}"
        if re.match(r'^\s*\{@\{[^}]*\}\}\s*$', line) or \
           re.match(r'^\s*#\d+\s*$', line) or \
           (re.match(r'^\s*\\end\{tabular\}\s*$', line) and i > 0 and '\\begin{tabular}' not in lines[i-1]):
            i += 1
            continue
        
        # Fix broken commands missing leading backslash (ewcommand, oindent, etc.)
        if re.match(r'^\s*ewcommand', line):
            # Fix: enewcommand -> \newcommand
            line = line.replace('ewcommand', '\\newcommand', 1)
        if re.match(r'^\s*oindent', line):
            # Fix: oindent -> \noindent
            line = line.replace('oindent', '\\noindent', 1)
        if re.match(r'^\s*ewline', line):
            # Fix: ewline -> \newline
            line = line.replace('ewline', '\\newline', 1)
        if re.match(r'^\s*ewpage', line):
            # Fix: ewpage -> \newpage
            line = line.replace('ewpage', '\\newpage', 1)
        
        # Fix broken name formatting (orphaned braces from name replacement)
        # Check both before and after \begin{document}
        if i > 0:
            # Check for broken name pattern: {\Huge\bfseries \textbackslash{}textcolor... \end{center} followed by orphaned braces
            if '\\begin{center}' in lines[i-1] and '\\Huge' in lines[i-1]:
                # Check if the name line has broken \textcolor syntax
                if '\\textbackslash{}textcolor' in lines[i-1] or '\\textcolor{black' in lines[i-1] and '}' not in lines[i-1]:
                    # Fix the broken name line
                    name_line = lines[i-1]
                    # Extract name from broken pattern: \textbackslash{}textcolor{black John} or \textcolor{black John}
                    name_match = re.search(r'(?:\\textbackslash\{\}|\\textcolor\{[^}]+\})\s*\{?([^}]+)\}?', name_line)
                    if name_match:
                        name_part1 = name_match.group(1).strip()
                        # Look for the next part in the current line or next line
                        if '\\end{center}' in line:
                            # Check next line for second part
                            if i + 1 < len(lines) and '\\textcolor{black}{' in lines[i+1]:
                                name_part2_match = re.search(r'\\textcolor\{[^}]+\}\{([^}]+)\}', lines[i+1])
                                if name_part2_match:
                                    name_part2 = name_part2_match.group(1)
                                    # Replace the broken name section
                                    fixed_name = f'{{\\Huge\\bfseries {name_part1} {name_part2}}}'
                                    lines[i-1] = fixed_name
                                    # Remove the orphaned line
                                    if i + 1 < len(lines):
                                        lines.pop(i+1)
                                    continue
                    # If we can't fix it, try to extract from the pattern
                    # Pattern: {\Huge\bfseries \textbackslash{}textcolor{black John}\n\end{center}\n\vspace{1em}}{\textcolor{black}{Doe}}
                    if '\\end{center}' in line and i + 1 < len(lines):
                        next_line = lines[i+1]
                        if '\\textcolor{black}{' in next_line:
                            # Extract both parts and fix
                            part1_match = re.search(r'\{([^}]+)\}', lines[i-1])
                            part2_match = re.search(r'\\textcolor\{[^}]+\}\{([^}]+)\}', next_line)
                            if part1_match and part2_match:
                                name1 = part1_match.group(1).replace('\\textbackslash{}textcolor{black ', '').strip()
                                name2 = part2_match.group(1)
                                fixed_name = f'{{\\Huge\\bfseries {name1} {name2}}}'
                                lines[i-1] = fixed_name
                                # Remove the broken lines
                                if i < len(lines):
                                    lines.pop(i)  # Remove \end{center} line
                                if i < len(lines) and '\\vspace' in lines[i]:
                                    lines.pop(i)  # Remove \vspace line
                                if i < len(lines) and '\\textcolor' in lines[i]:
                                    lines.pop(i)  # Remove \textcolor line
                                continue
            # Check for broken name pattern: {\Huge\bfseries ... \end{center} followed by orphaned braces
            if '\\begin{center}' in lines[i-1] and '\\Huge' in lines[i-1] and '\\end{center}' in line:
                # Check if the next line has orphaned closing braces
                if i + 1 < len(lines) and re.match(r'^\s*\}\s*$', lines[i+1]):
                    # This is likely an orphaned brace from broken name replacement
                    # Skip the orphaned brace line
                    i += 1
                    continue
                # Also check for patterns like \vspace{1em}}{...}
                if i + 1 < len(lines) and re.match(r'^\\vspace\{[^}]+\}\}\{', lines[i+1]):
                    # Fix this by removing the extra closing brace
                    lines[i+1] = re.sub(r'^\\vspace\{([^}]+)\}\}\{', r'\\vspace{\1}{', lines[i+1])
        
        cleaned_lines.append(line)
        i += 1
    content = '\n'.join(cleaned_lines)
    
    # Additional cleanup: Remove broken name patterns that might have been created
    # Pattern: {\Huge\bfseries ... \end{center} followed by \vspace{...}}{...}
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+([^}]+)\}\s*\\end\{center\}\s*\\vspace\{[^}]+\}\}\{([^}]+)\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1 \2}\n\\end{center}\n\\vspace{1em}',
        content
    )
    
    # Fix any remaining broken name patterns with orphaned braces
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+([^}]+)\}\s*\\end\{center\}\s*\\vspace\{([^}]+)\}\}\{([^}]+)\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1 \3}\n\\end{center}\n\\vspace{\2}',
        content
    )
    
    # Fix broken name pattern: {\Huge\bfseries \textbackslash{}textcolor{black John}\n\end{center}\n\vspace{1em}}{\textcolor{black}{Doe}}
    content = re.sub(
        r'\\begin\{center\}\s*\{\\Huge\\bfseries\s+\\textbackslash\{\}textcolor\{[^}]+\}\{([^}]+)\}\s*\\end\{center\}\s*\\vspace\{[^}]+\}\}\{([^}]+)\}',
        r'\\begin{center}\n{\\Huge\\bfseries \1 \2}\n\\end{center}\n\\vspace{1em}',
        content,
        flags=re.DOTALL
    )
    
    # Fix broken name pattern: {\Huge\bfseries \textbackslash{}textcolor{black John}\n\end{center}\n\vspace{1em}}{\textcolor{black}{Doe}}
    # Handle case where it's split across lines
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check for broken name pattern
        if '\\textbackslash{}textcolor' in line and '\\Huge' in line:
            # Try to fix it
            name_part1_match = re.search(r'\\textbackslash\{\}textcolor\{[^}]+\}\{([^}]+)\}', line)
            if name_part1_match:
                name_part1 = name_part1_match.group(1)
                # Look ahead for the second part
                j = i + 1
                while j < len(lines) and j < i + 5:
                    if '\\textcolor{black}{' in lines[j]:
                        name_part2_match = re.search(r'\\textcolor\{[^}]+\}\{([^}]+)\}', lines[j])
                        if name_part2_match:
                            name_part2 = name_part2_match.group(1)
                            # Replace the broken pattern
                            fixed_line = line.replace(f'\\textbackslash{{}}textcolor{{black {name_part1}}}', f'{name_part1}')
                            fixed_lines.append(fixed_line)
                            # Skip the broken lines
                            i = j + 1
                            # Add the second part to the previous line or as a new entry
                            if '\\end{center}' in fixed_lines[-1]:
                                # Insert before \end{center}
                                fixed_lines[-1] = fixed_lines[-1].replace('\\end{center}', f' {name_part2}\n\\end{center}')
                            else:
                                fixed_lines.append(f' {name_part2}')
                            continue
                    j += 1
        
        fixed_lines.append(line)
        i += 1
    content = '\n'.join(fixed_lines)
    
    # Fix broken name placeholder: {#1} should be replaced with actual name
    # Check if we have a \name command that was processed
    if '{#1}' in content:
        # Try to find the actual name from \name command or identity
        name_match = re.search(r'\\name\{([^\}]+)\}\{([^\}]+)\}', content)
        if name_match:
            first = name_match.group(1)
            last = name_match.group(2)
            # Clean up textcolor commands
            first = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', first).strip('{}')
            last = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', last).strip('{}')
            name = f'{first} {last}'
            content = content.replace('{#1}', name)
        else:
            # If no \name command, just remove the placeholder
            content = content.replace('{#1}', 'Name')
    
    # Fix broken name pattern: {\LARGE \textbfName} should be {\LARGE \textbf{Name}}
    content = re.sub(r'\\textbfName', r'\\textbf{Name}', content)
    
    # Extract name from preamble commands and replace placeholder "Name"
    firstname_match = re.search(r'\\firstname\{([^}]+)\}', content)
    familyname_match = re.search(r'\\familyname\{([^}]+)\}', content)
    full_name = None
    
    if firstname_match and familyname_match:
        first = firstname_match.group(1).strip()
        last = familyname_match.group(1).strip()
        # Remove any \textcolor wrappers
        first = re.sub(r'\\textcolor\{[^}]+\}\{([^}]+)\}', r'\1', first)
        last = re.sub(r'\\textcolor\{[^}]+\}\{([^}]+)\}', r'\1', last)
        full_name = f"{first} {last}"
    else:
        # Fallback: Try to extract name from email (e.g., john.doe@gmail.com -> John Doe)
        email_match = re.search(r'([a-zA-Z]+)\.([a-zA-Z]+)@', content)
        if email_match:
            first_part = email_match.group(1)
            last_part = email_match.group(2)
            # Capitalize first letter of each part
            full_name = f"{first_part.capitalize()} {last_part.capitalize()}"
        # If still no name, try to extract from common name patterns in content
        if not full_name:
            # Look for name patterns in the contact section
            # Try to extract name from common patterns in content
            name_pattern_match = re.search(r'([A-Z][a-z]+)\s+([A-Z][a-z]+)', content)
            if name_pattern_match:
                full_name = f"{name_pattern_match.group(1)} {name_pattern_match.group(2)}"
    
    if full_name:
        # Escape special LaTeX characters
        full_name_escaped = full_name.replace('&', '\\&').replace('%', '\\%').replace('$', '\\$').replace('#', '\\#').replace('^', '\\textasciicircum{}').replace('_', '\\_').replace('{', '\\{').replace('}', '\\}')
        # Replace placeholder "Name" with actual name
        # Use string replacement instead of regex to avoid escape issues
        content = content.replace(
            '{\\LARGE \\textbf{Name}}',
            f'{{\\LARGE \\textbf{{{full_name_escaped}}}}}'
        )
        # Also handle case where it's just "Name" without the full pattern
        content = re.sub(
            r'\\textbf\{Name\}',
            f'\\textbf{{{full_name_escaped}}}',
            content
        )
    
    # Also fix if we have the actual name from \name command
    name_match = re.search(r'\\name\{([^\}]+)\}\{([^\}]+)\}', content)
    if name_match:
        first = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', name_match.group(1)).strip('{}')
        last = re.sub(r'\\textcolor\{[^\}]+\}\{([^\}]+)\}', r'\1', name_match.group(2)).strip('{}')
        name = f'{first} {last}'
        content = re.sub(r'\\textbf\{Name\}', f'\\textbf{{{name}}}', content)
    
    # ----- HOTFIX: global normalization for lost backslashes (incl. TAB-separated) -----
    # Fix common commands missing the leading backslash anywhere in the doc
    #  - ewcommand  -> \newcommand
    #  - oindent    -> \noindent
    #  - extbf{     -> \textbf{
    # Also handle cases where a literal TAB precedes the token (e.g., "\t extbf{")
    content = re.sub(r'(?<!\\)(?<![a-zA-Z])ewcommand\b', r'\\newcommand', content)
    content = re.sub(r'(?<!\\)(?<![a-zA-Z])oindent\b',   r'\\noindent',  content)
    content = re.sub(r'(?<!\\)(?<![a-zA-Z])extbf\s*\{', r'\\textbf{',   content)
    # TAB-aware variants (literal tab before token)
    content = re.sub(r'\t+extbf\s*\{',  r'\\textbf{', content)
    content = re.sub(r'\t+oindent\b',   r'\\noindent', content)
    content = re.sub(r'\t+ewcommand\b', r'\\newcommand', content)

    # ----- HOTFIX: normalize malformed \textcolor patterns -----
    # Case A: "\textcolor\{black Foo"  -> "\textcolor{black}{Foo}"
    content = re.sub(r'\\textcolor\\\{([^\}\s]+)\s+([^{}\n]+)', r'\\textcolor{\1}{\2}', content)
    # Case B: "\textcolor{black Foo"    -> "\textcolor{black}{Foo}"
    content = re.sub(r'\\textcolor\{([^\}\s]+)\s+([^{}\n]+)', r'\\textcolor{\1}{\2}', content)
    # Ensure every \href has both args (already handled earlier, but reinforce)
    content = re.sub(r'\\href\{([^}]+)\}(?!\{)', r'\\href{\1}{\1}', content)

    # ----- HOTFIX: rebuild header if the first center block looks broken -----
    # Try to recover first/last from \firstname/\familyname or from visible text in the broken header lines
    def _extract_name_from_preamble(txt: str):
        f = re.search(r'\\firstname\{([^}]+)\}', txt)
        l = re.search(r'\\familyname\{([^}]+)\}', txt)
        if f and l:
            def decolor(s): return re.sub(r'\\textcolor\{[^}]+\}\{([^}]+)\}', r'\1', s)
            return decolor(f.group(1)).strip(), decolor(l.group(1)).strip()
        return None, None

    # Find first \begin{center} ... \end{center}
    m_center = re.search(r'\\begin\{center\}(.+?)\\end\{center\}', content, flags=re.DOTALL)
    if m_center:
        block = m_center.group(1)
        looks_broken = ('\\textcolor\\{black' in block) or ('\\textcolor{black' in block and '}' not in block.split('\\textcolor{black',1)[1])
        if looks_broken:
            first, last = _extract_name_from_preamble(content)
            if not (first and last):
                # Fallback: try to read two tokens following a broken textcolor
                m_name = re.search(r'textcolor\\?\{black[^}]*\}\s*([A-Za-z.\-]+)\s*(?:\\textcolor\{black\}\s*)?([A-Za-z.\-]+)?', block)
                if m_name:
                    first = first or m_name.group(1)
                    last  = last  or (m_name.group(2) or '')
            if first:
                safe_name = f'{{\\Huge \\bfseries {first} {last or ""}}}'
                new_block = f'\n{safe_name}\n'
                # Replace the entire center block content with the safe name line only
                content = content[:m_center.start(1)] + new_block + content[m_center.end(1):]

    # Extra: collapse any accidental "\vspace{1em}}{Last}" artifacts after header
    content = re.sub(
        r'(\\end\{center\}\s*\n)\s*\\vspace\{([^\}]+)\}\}\{([^}]+)\}',
        r'\1\\vspace{\2}', content
    )

    # Clean up extra blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content



