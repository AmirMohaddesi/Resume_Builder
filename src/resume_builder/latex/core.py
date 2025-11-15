"""
Core LaTeX helper functions for escaping, formatting, and validation.

These are pure utility functions with no dependencies on the rest of the system.
"""

import re
from typing import Optional


def strip_latex_comments(s: str) -> str:
    """Remove LaTeX comments but preserve newlines."""
    return "\n".join(line.split("%", 1)[0] for line in s.splitlines())


def has_pkg(s: str, pkg: str) -> bool:
    """Check if package exists in uncommented text only."""
    s_nc = strip_latex_comments(s)
    return bool(re.search(r'\\usepackage(?:\[[^\]]*\])?\{'+re.escape(pkg)+r'\}', s_nc))


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
    
    # E.g., xxxxxxxxxx (10 digits)
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    
    # Otherwise, return original (international or malformed)
    return phone_stripped


def format_url(url: str) -> str:
    """Clean and format URL for LaTeX hyperref."""
    if not url:
        return ""
    
    url = url.strip()
    
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Ensure protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Escape special LaTeX characters in URL
    # URLs can contain &, #, _, etc. which need escaping for LaTeX
    # But hyperref handles URLs specially, so we only escape if not using hyperref
    # For now, return as-is (hyperref will handle it)
    return url

