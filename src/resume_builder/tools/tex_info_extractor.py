"""
Tool to extract information from LaTeX/TeX files.
Extracts personal information, links, and style patterns.
"""
import re
from pathlib import Path
from typing import Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class TexInfoExtractorInput(BaseModel):
    """Input for TeX info extractor."""
    tex_file_path: str = Field(..., description="Path to the .tex file to extract information from")


class TexInfoExtractorTool(BaseTool):
    """
    Extract information from LaTeX/TeX files including personal details, links, and contact info.
    This helps recover information that might be lost during resume parsing.
    """
    name: str = "tex_info_extractor"
    description: str = (
        "Extract information from LaTeX/TeX files including name, email, phone, websites, "
        "LinkedIn, GitHub, and other URLs. Use this when you need to recover information "
        "from an existing .tex resume file."
    )
    args_schema: type[BaseModel] = TexInfoExtractorInput

    def _extract_email(self, content: str) -> str:
        """Extract email address from LaTeX content."""
        # Look for email in various LaTeX formats
        patterns = [
            r'\\email\{([^}]+)\}',
            r'\\href\{mailto:([^}]+)\}',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        return ""

    def _extract_phone(self, content: str) -> str:
        """Extract phone number from LaTeX content."""
        # Look for phone in various formats
        # Priority: LaTeX commands first, then common phone patterns
        patterns = [
            r'\\phone\{([^}]+)\}',
            r'\\mobile\{([^}]+)\}',
            r'\\tel\{([^}]+)\}',
            # Phone number patterns (avoid matching DOIs/years)
            # Match (XXX)XXX-XXXX or (XXX) XXX-XXXX or XXX-XXX-XXXX
            r'\(?\d{3}\)?\s*[-.\s]?\d{3}[-.\s]?\d{4}',
            # Match with country code: +1 (XXX) XXX-XXXX
            r'\+1\s*\(?\d{3}\)?\s*[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        
        # Also look for phone numbers near common indicators like \faMobile, Mobile, Phone, Tel
        # This helps avoid false positives from DOIs
        phone_context_pattern = r'(?:\\faMobile|Mobile|Phone|Tel|phone|tel)[\s\S]{0,50}?\(?\d{3}\)?\s*[-.\s]?\d{3}[-.\s]?\d{4}'
        context_matches = re.findall(phone_context_pattern, content, re.IGNORECASE)
        if context_matches:
            # Extract just the phone number part
            phone_match = re.search(r'\(?\d{3}\)?\s*[-.\s]?\d{3}[-.\s]?\d{4}', context_matches[0])
            if phone_match:
                phone = phone_match.group(0).strip()
                digits_only = re.sub(r'\D', '', phone)
                if len(digits_only) == 10:
                    area_code = digits_only[:3]
                    exchange = digits_only[3:6]
                    # Basic validation: area code and exchange can't start with 0 or 1
                    if area_code[0] not in ('0', '1') and exchange[0] not in ('0', '1'):
                        return phone
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                phone = matches[0].strip()
                # Validate: phone numbers should be 10 digits (excluding formatting)
                digits_only = re.sub(r'\D', '', phone)
                
                # Reject if too short or too long (should be 10-11 digits for US numbers)
                if len(digits_only) < 10 or len(digits_only) > 11:
                    continue
                
                # For 11-digit numbers, first digit should be 1 (US country code)
                if len(digits_only) == 11 and not digits_only.startswith('1'):
                    continue
                
                # For 10-digit numbers, validate area code and exchange
                if len(digits_only) == 10:
                    area_code = digits_only[:3]
                    exchange = digits_only[3:6]
                    # Area code and exchange can't start with 0 or 1
                    if area_code[0] in ('0', '1') or exchange[0] in ('0', '1'):
                        continue
                    # Additional check: if area code is 202 and the full number looks like a year+DOI pattern, reject
                    # e.g., "2024.1064459" would match as "2021064459" (area code 202, exchange 106)
                    # But "202" is DC area code, so we need context. Check if it's near DOI indicators
                    # For now, we'll rely on the context pattern above to catch phone numbers near \faMobile
                
                return phone
        return ""

    def _extract_name(self, content: str) -> Dict[str, str]:
        """Extract first and last name from LaTeX content."""
        name_patterns = [
            (r'\\name\{([^}]+)\}\{([^}]+)\}', 1, 2),  # \name{First}{Last}
            (r'\\firstname\{([^}]+)\}', 1, 0),  # \firstname{First}
            (r'\\familyname\{([^}]+)\}', 0, 1),  # \familyname{Last}
            (r'\\author\{([^}]+)\s+([^}]+)\}', 1, 2),  # \author{First Last}
        ]
        
        first_name = ""
        last_name = ""
        
        for pattern, first_idx, last_idx in name_patterns:
            matches = re.findall(pattern, content)
            if matches:
                if first_idx > 0:
                    first_name = first_name or matches[0][first_idx - 1].strip()
                if last_idx > 0:
                    last_name = last_name or matches[0][last_idx - 1].strip()
        
        return {"first": first_name, "last": last_name}

    def _extract_urls(self, content: str) -> Dict[str, str]:
        """Extract URLs for website, LinkedIn, GitHub, etc."""
        urls = {
            "website": "",
            "linkedin": "",
            "github": "",
            "other_urls": []
        }
        
        # LinkedIn - handle common variants: /in/, /pub/, query params, FontAwesome patterns
        linkedin_patterns = [
            r'\\social\[linkedin\]\{([^}]+)\}',  # \social[linkedin]{username}
            r'\\href\{https?://(?:www\.)?linkedin\.com/(?:in|pub)/([^}?]+)',  # \href{...linkedin.com/in/...} or /pub/
            r'\\href\{([^}]*)\}\{.*\\faLinkedin.*\}',  # FontAwesome icon pattern
            r'linkedin\.com/(?:in|pub)/([a-zA-Z0-9_-]+)',  # Bare URL pattern
        ]
        for pattern in linkedin_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                linkedin = matches[0].strip()
                # Strip query params if present
                linkedin = linkedin.split('?')[0].split('&')[0]
                # If it's already a full URL, extract username
                if 'linkedin.com' in linkedin.lower():
                    match = re.search(r'linkedin\.com/(?:in|pub)/([^/?]+)', linkedin, re.IGNORECASE)
                    if match:
                        linkedin = match.group(1)
                # Store as full URL for consistency (will be normalized later)
                if not linkedin.startswith('http'):
                    linkedin = f"https://linkedin.com/in/{linkedin}"
                urls["linkedin"] = linkedin
                break
        
        # GitHub - handle FontAwesome patterns and bare URLs
        github_patterns = [
            r'\\social\[github\]\{([^}]+)\}',  # \social[github]{username}
            r'\\href\{https?://(?:www\.)?github\.com/([^}/]+)',  # \href{...github.com/username...}
            r'\\href\{([^}]*)\}\{.*\\faGithub.*\}',  # FontAwesome icon pattern
            r'github\.com/([a-zA-Z0-9_-]+)',  # Bare URL pattern
        ]
        for pattern in github_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                github = matches[0].strip()
                # If it's already a full URL, extract username (first path component)
                if 'github.com' in github.lower():
                    match = re.search(r'github\.com/([^/?]+)', github, re.IGNORECASE)
                    if match:
                        github = match.group(1).split('/')[0]  # Take first path component only
                # Store as full URL for consistency (will be normalized later)
                if not github.startswith('http'):
                    github = f"https://github.com/{github}"
                urls["github"] = github
                break
        
        # Website/Homepage
        website_patterns = [
            r'\\homepage\{([^}]+)\}',
            r'\\website\{([^}]+)\}',
            r'\\url\{([^}]+)\}',
        ]
        for pattern in website_patterns:
            matches = re.findall(pattern, content)
            if matches:
                urls["website"] = matches[0].strip()
                break
        
        # Generic URLs from \href{...}{...} and bare URLs
        # Extract from \href{url}{label} patterns
        href_pattern = r'\\href\{([^}]+)\}\{([^}]*)\}'
        href_matches = re.findall(href_pattern, content)
        for url, label in href_matches:
            url = url.strip()
            # Skip mailto links (handled by email extraction)
            if url.startswith('mailto:'):
                continue
            # Skip LinkedIn/GitHub (already handled)
            if 'linkedin.com' in url.lower() or 'github.com' in url.lower():
                continue
            # Use as website if not already set
            if not urls["website"] and url.startswith(('http://', 'https://')):
                urls["website"] = url
        
        # Also extract bare URLs (not in \href)
        bare_url_pattern = r'(https?://[^\s\)\}]+)'
        bare_urls = re.findall(bare_url_pattern, content)
        for url in bare_urls:
            if 'linkedin.com' not in url.lower() and 'github.com' not in url.lower():
                if not urls["website"]:
                    urls["website"] = url
                elif url not in urls["other_urls"]:
                    urls["other_urls"].append(url)
        
        return urls

    def _extract_address(self, content: str) -> str:
        """Extract address from LaTeX content."""
        patterns = [
            r'\\address\{([^}]+)\}',
            r'\\location\{([^}]+)\}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0].strip()
        return ""

    def _run(self, tex_file_path: str) -> str:
        """
        Extract information from a .tex file.
        
        Args:
            tex_file_path: Path to the .tex file
            
        Returns:
            JSON string with extracted information
        """
        tex_path = Path(tex_file_path)
        
        if not tex_path.exists():
            return f'{{"error": "TeX file not found: {tex_file_path}"}}'
        
        try:
            content = tex_path.read_text(encoding='utf-8')
        except Exception as e:
            return f'{{"error": "Failed to read TeX file: {str(e)}"}}'
        
        # Extract all information
        name_info = self._extract_name(content)
        email = self._extract_email(content)
        phone = self._extract_phone(content)
        urls = self._extract_urls(content)
        address = self._extract_address(content)
        
        # Build result
        result = {
            "identity": {
                "first": name_info.get("first", ""),
                "last": name_info.get("last", ""),
                "email": email,
                "phone": phone,
                "location": address,  # Map address to location for consistency
                "website": urls.get("website", ""),
                "linkedin": urls.get("linkedin", ""),
                "github": urls.get("github", ""),
                "address": address,  # Keep for backward compatibility
            },
            "other_urls": urls.get("other_urls", []),
            "source": "tex_file"
        }
        
        import json
        return json.dumps(result, indent=2)

