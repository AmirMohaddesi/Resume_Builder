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
        patterns = [
            r'\\phone\{([^}]+)\}',
            r'\\mobile\{([^}]+)\}',
            r'\\tel\{([^}]+)\}',
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0].strip()
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
        
        # LinkedIn
        linkedin_patterns = [
            r'\\social\[linkedin\]\{([^}]+)\}',
            r'\\href\{https?://(?:www\.)?linkedin\.com/in/([^}]+)\}',
            r'linkedin\.com/in/([a-zA-Z0-9_-]+)',
        ]
        for pattern in linkedin_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                linkedin = matches[0].strip()
                if not linkedin.startswith('http'):
                    linkedin = f"https://linkedin.com/in/{linkedin}"
                urls["linkedin"] = linkedin
                break
        
        # GitHub
        github_patterns = [
            r'\\social\[github\]\{([^}]+)\}',
            r'\\href\{https?://(?:www\.)?github\.com/([^}]+)\}',
            r'github\.com/([a-zA-Z0-9_-]+)',
        ]
        for pattern in github_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                github = matches[0].strip()
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
        
        # Generic URLs
        url_pattern = r'\\href\{(https?://[^}]+)\}'
        all_urls = re.findall(url_pattern, content)
        for url in all_urls:
            if 'linkedin.com' not in url and 'github.com' not in url:
                if not urls["website"]:
                    urls["website"] = url
                else:
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
                "website": urls.get("website", ""),
                "linkedin": urls.get("linkedin", ""),
                "github": urls.get("github", ""),
                "address": address,
            },
            "other_urls": urls.get("other_urls", []),
            "source": "tex_file"
        }
        
        import json
        return json.dumps(result, indent=2)

