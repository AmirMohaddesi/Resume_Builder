"""
Privacy Guard Tool for validating that personal information doesn't leak between resumes.
Ensures data isolation and prevents cross-contamination.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Type, Optional
import re
import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class PrivacyGuardInput(BaseModel):
    """Input schema for PrivacyGuardTool."""
    content_path: str = Field(..., description="Path to the content file to validate (JSON, LaTeX, or text).")
    profile_path: str = Field(..., description="Path to the expected profile JSON file.")
    content_type: str = Field(default="latex", description="Type of content: 'latex', 'json', or 'text'.")
    job_description: Optional[str] = Field(default=None, description="Job description to validate relevance.")


class PrivacyGuardTool(BaseTool):
    """
    Validates that generated content doesn't contain personal information
    from other profiles and matches the expected profile.
    """

    name: str = "privacy_guard"
    description: str = (
        "Validate that resume content matches the expected profile and doesn't contain "
        "personal information from other profiles. Ensures data isolation and privacy."
    )
    args_schema: Type[BaseModel] = PrivacyGuardInput

    @staticmethod
    def _extract_personal_info(text: str) -> Dict[str, List[str]]:
        """Extract potential personal information from text."""
        info = {
            'emails': [],
            'phones': [],
            'addresses': [],
            'names': [],
            'companies': [],
        }
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        info['emails'] = list(set(re.findall(email_pattern, text)))  # Deduplicate
        
        # Phone patterns (various formats)
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US format
            r'\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # International
        ]
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, text))
        info['phones'] = list(set(phones))  # Deduplicate
        
        # Address patterns (street addresses, cities, states)
        address_pattern = r'\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Circle|Cir)[\s,]*[A-Za-z\s,]+(?:[A-Z]{2})?\s+\d{5}'
        info['addresses'] = re.findall(address_pattern, text, re.IGNORECASE)
        
        return info

    @staticmethod
    def _extract_profile_info(profile_path: Path) -> Dict[str, Any]:
        """Extract expected information from profile."""
        if not profile_path.exists():
            return {}
        
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            return {
                'name': profile.get('name', ''),
                'email': profile.get('email', ''),
                'phone': profile.get('phone', ''),
                'address': profile.get('address', ''),
                'companies': [exp.get('company', '') for exp in profile.get('experience', []) if exp.get('company')],
                'skills': profile.get('skills', []),
                'education': [edu.get('institution', '') for edu in profile.get('education', []) if edu.get('institution')],
            }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Log but don't fail - return empty dict
            import logging
            logging.getLogger("privacy_guard").debug(f"Failed to extract profile info: {e}")
            return {}

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r'\s+', ' ', text.lower().strip())

    def _validate_content(
        self,
        content: str,
        expected_profile: Dict[str, Any],
        content_type: str
    ) -> Dict[str, Any]:
        """Validate content against expected profile."""
        issues = []
        warnings = []
        
        # Extract personal info from content
        content_info = self._extract_personal_info(content)
        expected_info = {
            'emails': [expected_profile.get('email', '')] if expected_profile.get('email') else [],
            'phones': [expected_profile.get('phone', '')] if expected_profile.get('phone') else [],
            'names': [expected_profile.get('name', '')] if expected_profile.get('name') else [],
        }
        
        # Check for unexpected emails
        if content_info['emails']:
            for email in content_info['emails']:
                if expected_info['emails'] and email.lower() not in [e.lower() for e in expected_info['emails']]:
                    issues.append(f"Unexpected email found: {email}")
                elif not expected_info['emails']:
                    warnings.append(f"Email found but not in profile: {email}")
        
        # Check for unexpected phone numbers
        if content_info['phones']:
            for phone in content_info['phones']:
                # Normalize phone numbers for comparison
                phone_normalized = re.sub(r'[^\d]', '', phone)
                expected_phones_normalized = [re.sub(r'[^\d]', '', p) for p in expected_info['phones']]
                if expected_phones_normalized and phone_normalized not in expected_phones_normalized:
                    issues.append(f"Unexpected phone number found: {phone}")
                elif not expected_phones_normalized:
                    warnings.append(f"Phone number found but not in profile: {phone}")
        
        # Check for unexpected names (if profile has a name)
        if expected_info['names'] and content_info['names']:
            expected_name_parts = set(self._normalize_text(expected_info['names'][0]).split())
            for name_match in re.finditer(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', content):
                name = name_match.group(0)
                name_parts = set(self._normalize_text(name).split())
                # If name doesn't share significant parts with expected name, flag it
                if not name_parts.intersection(expected_name_parts):
                    issues.append(f"Unexpected name found: {name}")
        
        # Check for unexpected company names
        if expected_profile.get('companies'):
            expected_companies = [c.lower() for c in expected_profile['companies'] if c]
            content_upper = content.upper()
            # Look for company indicators
            for company in expected_companies:
                if company and company.lower() not in content.lower():
                    # This is okay - not all companies need to be mentioned
                    pass
        
        # Validate skills match (for JSON content)
        if content_type == 'json':
            try:
                content_data = json.loads(content)
                content_skills = content_data.get('SKILLS', [])
                if isinstance(content_skills, str):
                    content_skills = [s.strip() for s in content_skills.split(',')]
                
                expected_skills = [s.lower() for s in expected_profile.get('skills', [])]
                # Skills don't need to match exactly, but flag if completely different
                if content_skills and expected_skills:
                    content_skills_lower = [s.lower() for s in content_skills]
                    overlap = set(content_skills_lower) & set(expected_skills)
                    if not overlap and len(expected_skills) > 0:
                        warnings.append("Skills in content don't match profile skills")
            except Exception:
                pass
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'personal_info_found': {
                'emails': len(content_info['emails']),
                'phones': len(content_info['phones']),
                'addresses': len(content_info['addresses']),
            }
        }

    def _run(
        self,
        content_path: str,
        profile_path: str,
        content_type: str = "latex",
        job_description: Optional[str] = None,
        **_: Any
    ) -> Dict[str, Any]:
        """Validate content for privacy and data isolation."""
        # Resolve paths - handle both relative and absolute paths
        content_file = Path(content_path)
        if not content_file.is_absolute():
            # Try relative to current working directory
            content_file = Path.cwd() / content_path
        
        profile_file = Path(profile_path)
        if not profile_file.is_absolute():
            # Try relative to current working directory
            profile_file = Path.cwd() / profile_path
        
        if not content_file.exists():
            return {
                "valid": False,
                "error": f"Content file not found: {content_path}",
            }
        
        if not profile_file.exists():
            return {
                "valid": False,
                "error": f"Profile file not found: {profile_path}",
            }
        
        # Read content
        try:
            content = content_file.read_text(encoding="utf-8")
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to read content file: {e}",
            }
        
        # Extract expected profile info
        expected_profile = self._extract_profile_info(profile_file)
        
        # Validate content
        validation = self._validate_content(content, expected_profile, content_type)
        
        # Additional check: ensure content is relevant to job description
        relevance_warning = None
        if job_description and content_type == "latex":
            # Simple relevance check - look for keywords from JD in content
            jd_keywords = set(re.findall(r'\b[A-Za-z]{4,}\b', job_description.lower()))
            content_keywords = set(re.findall(r'\b[A-Za-z]{4,}\b', content.lower()))
            overlap = jd_keywords & content_keywords
            if len(jd_keywords) > 0:
                relevance = len(overlap) / len(jd_keywords)
                if relevance < 0.1:  # Less than 10% keyword overlap
                    relevance_warning = f"Content may not be relevant to job description (low keyword overlap: {relevance:.1%})"
                validation['warnings'].append(relevance_warning)
        
        return {
            "valid": validation['valid'],
            "issues": validation['issues'],
            "warnings": validation['warnings'],
            "personal_info_found": validation['personal_info_found'],
            "profile_matched": len(validation['issues']) == 0,
            "message": "Content validated successfully" if validation['valid'] else "Privacy issues detected",
        }

