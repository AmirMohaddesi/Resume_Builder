"""
Tool for parsing resumes (PDF/DOCX) to extract profile information.
Converts uploaded resumes into the profile.json format.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


def extract_email(text: str) -> Optional[str]:
    """Extract email address from text, ensuring it's clean and separate from phone numbers."""
    # More specific email pattern that requires word boundaries
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    
    if not matches:
        return None
    
    # Take the first valid email
    email = matches[0]
    
    # Clean up: remove any leading digits/phone fragments that might have been concatenated
    # Example: "426-8113Eamir.mohaddesi@gmail.com" -> "amir.mohaddesi@gmail.com"
    # Strategy: Find @ symbol, work backwards to find where username actually starts
    if '@' in email:
        at_pos = email.find('@')
        username_part = email[:at_pos]
        domain_part = email[at_pos:]
        
        # Remove leading phone number patterns (digits, dashes, spaces)
        # Look for pattern like: digits-dashes-digits followed by a letter
        # We want to keep only the alphabetic part of the username
        username_cleaned = re.sub(r'^[0-9\-.\s]+', '', username_part)
        
        # If we removed something and the result starts with a letter, use it
        if username_cleaned and username_cleaned[0].isalpha() and len(username_cleaned) > 1:
            # Special case: If first letter is uppercase and second is lowercase (like "Eamir"),
            # it might be from phone concatenation. Try to find the actual email start.
            # Common pattern: phone ends with digit, email might start with letter
            # "426-8113Eamir" -> remove "426-8113" -> "Eamir" but real email might be "amir"
            # Strategy: if first char is uppercase and looks like it might be concatenation artifact,
            # try lowercasing it. But be conservative - only if it's a single uppercase letter.
            if (len(username_cleaned) > 2 and 
                username_cleaned[0].isupper() and 
                username_cleaned[1].islower()):
                # Check if removing the first letter gives us a more reasonable email
                # (e.g., "Eamir" -> "amir" if "amir" is more common pattern)
                # For now, just lowercase the first letter if it's uppercase
                username_cleaned = username_cleaned[0].lower() + username_cleaned[1:]
            cleaned_email = username_cleaned + domain_part
        else:
            # Fallback: try to find first letter in username
            first_letter_pos = -1
            for i, char in enumerate(username_part):
                if char.isalpha():
                    first_letter_pos = i
                    break
            if first_letter_pos > 0:
                cleaned_username = username_part[first_letter_pos:]
                # Lowercase first letter if it's uppercase and looks like phone concatenation
                if (len(cleaned_username) > 1 and 
                    cleaned_username[0].isupper() and 
                    cleaned_username[1].islower()):
                    cleaned_username = cleaned_username[0].lower() + cleaned_username[1:]
                cleaned_email = cleaned_username + domain_part
            else:
                cleaned_email = email
    else:
        cleaned_email = email
    
    # Ensure it's still a valid email after cleaning
    if re.match(pattern, cleaned_email):
        return cleaned_email
    
    # If cleaning broke it, return original
    return email


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text, ensuring it's separate from email."""
    # First, remove email addresses from text to avoid concatenation issues
    text_no_email = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Remove years (like 2024) and other date patterns that might be mistaken for phones
    # Remove 4-digit years at word boundaries
    text_no_email = re.sub(r'\b(19|20)\d{2}\b', '', text_no_email)
    
    # Common phone patterns (order matters - more specific first)
    # Be more strict: avoid matching years, IDs, or other numeric patterns
    patterns = [
        # International format with country code
        r'\+?1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US with +1
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',  # International (but not too long)
        # US format: (123) 456-7890 or 123-456-7890
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        # Short format: 123-4567 (local, but less common)
        r'\b\d{3}[-.\s]?\d{4}\b',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_no_email)
        if matches:
            phone = matches[0]
            # Clean up: remove any trailing letters that might have been concatenated
            # Example: "426-8113E" -> "426-8113"
            phone = re.sub(r'([0-9])[A-Za-z]+$', r'\1', phone)
            # Ensure it's a reasonable phone number length (7-15 digits)
            digits_only = re.sub(r'[^\d]', '', phone)
            digit_count = len(digits_only)
            
            # Strict validation: phone numbers should be 7-15 digits
            # Also reject if it looks like a year (4 digits starting with 19 or 20)
            # or if it's too long (likely an ID or other number)
            if 7 <= digit_count <= 15:
                # Reject if it's clearly a year
                if digit_count == 4 and (digits_only.startswith('19') or digits_only.startswith('20')):
                    continue
                # Reject if it contains a year pattern
                if re.search(r'(19|20)\d{2}', phone):
                    continue
                return phone
    
    return None


def extract_urls(text: str) -> Dict[str, str]:
    """Extract URLs (LinkedIn, GitHub, website) from text."""
    result = {}
    
    # Extract full URLs with protocol
    url_pattern = r'https?://[^\s\)\]>]+'
    urls = re.findall(url_pattern, text)
    
    for url in urls:
        # Clean up trailing punctuation
        url = url.rstrip('.,;:')
        url_lower = url.lower()
        if 'linkedin.com' in url_lower:
            result['linkedin'] = url
        elif 'github.com' in url_lower or 'github.io' in url_lower:
            result['github'] = url
        else:
            if 'website' not in result:  # Only set first non-social URL as website
                result['website'] = url
    
    # Extract domains without protocol (e.g., www.example.com or example.com)
    # Pattern: www.domain.tld or domain.tld (but not email addresses)
    # More permissive pattern for personal websites
    domain_pattern = r'\b(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9]\.)+[a-zA-Z]{2,}\b'
    domain_matches = re.findall(domain_pattern, text, re.IGNORECASE)
    
    for domain_match in domain_matches:
        # Reconstruct full domain
        # Find the actual match in text to get full domain (including www. if present)
        domain_pattern_full = r'\b((?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9](?:\.[a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9])*\.[a-zA-Z]{2,})\b'
        full_matches = re.findall(domain_pattern_full, text, re.IGNORECASE)
        
        for domain in full_matches:
            domain_lower = domain.lower()
            # Skip common email domains and social media
            skip_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 
                          'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
                          'linkedin.com', 'github.com']
            
            if any(skip in domain_lower for skip in skip_domains):
                continue
            
            # This is likely a personal website
            if 'website' not in result:
                # Add https:// prefix if not present
                if not domain.startswith('http'):
                    result['website'] = f"https://{domain}"
                else:
                    result['website'] = domain
                break  # Only take the first personal domain
    
    # Extract GitHub/LinkedIn usernames (without full URL)
    # Pattern: github.com/username or linkedin.com/in/username
    github_pattern = r'github\.com[/:]([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})'
    github_matches = re.findall(github_pattern, text, re.IGNORECASE)
    if github_matches and 'github' not in result:
        result['github'] = f"https://github.com/{github_matches[0]}"
    
    linkedin_pattern = r'linkedin\.com/(?:in/|pub/)?([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,100})'
    linkedin_matches = re.findall(linkedin_pattern, text, re.IGNORECASE)
    if linkedin_matches and 'linkedin' not in result:
        result['linkedin'] = f"https://linkedin.com/in/{linkedin_matches[0]}"
    
    return result


def parse_pdf(file_path: Path) -> tuple[str, Dict[str, List[str]]]:
    """
    Extract text and hyperlinks from PDF file.
    Returns (text, hyperlinks_dict) where hyperlinks_dict has keys: 'github', 'linkedin', 'website', 'other'
    """
    if not PDF_AVAILABLE:
        raise ImportError("pypdf not installed. Install with: pip install pypdf")
    
    reader = PdfReader(file_path)
    text_parts = []
    hyperlinks = {
        'github': [],
        'linkedin': [],
        'website': [],
        'other': []
    }
    
    for page in reader.pages:
        # Extract text
        text_parts.append(page.extract_text())
        
        # Extract hyperlinks from annotations
        if '/Annots' in page:
            annotations = page['/Annots']
            for annotation in annotations:
                annotation_obj = annotation.get_object()
                if '/A' in annotation_obj:
                    action = annotation_obj['/A']
                    if '/URI' in action:
                        uri = action['/URI']
                        if isinstance(uri, str):
                            url_lower = uri.lower()
                            if 'github.com' in url_lower or 'github.io' in url_lower:
                                hyperlinks['github'].append(uri)
                            elif 'linkedin.com' in url_lower:
                                hyperlinks['linkedin'].append(uri)
                            elif uri.startswith('http'):
                                # Check if it's a personal website (not social media)
                                if not any(social in url_lower for social in ['facebook.com', 'twitter.com', 'instagram.com', 'youtube.com']):
                                    hyperlinks['website'].append(uri)
                                else:
                                    hyperlinks['other'].append(uri)
    
    # Deduplicate hyperlinks
    for key in hyperlinks:
        hyperlinks[key] = list(dict.fromkeys(hyperlinks[key]))  # Preserves order while removing duplicates
    
    return "\n".join(text_parts), hyperlinks


def parse_docx(file_path: Path) -> str:
    """Extract text from DOCX file."""
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document(file_path)
    text_parts = []
    for paragraph in doc.paragraphs:
        text_parts.append(paragraph.text)
    return "\n".join(text_parts)


def parse_resume_to_profile(resume_path: str | Path) -> Dict[str, Any]:
    """
    Parse a resume file (PDF or DOCX) and extract profile information.
    Returns a profile dict in the expected format.
    """
    resume_path = Path(resume_path)
    
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")
    
    # Extract text based on file type
    pdf_hyperlinks = {}
    if resume_path.suffix.lower() == '.pdf':
        text, pdf_hyperlinks = parse_pdf(resume_path)
    elif resume_path.suffix.lower() in ['.docx', '.doc']:
        text = parse_docx(resume_path)
    else:
        raise ValueError(f"Unsupported file type: {resume_path.suffix}. Use PDF or DOCX.")
    
    # Extract basic information
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Extract contact info from text
    email = extract_email(text)
    phone = extract_phone(text)
    urls = extract_urls(text)
    
    # Merge PDF hyperlinks with text-extracted URLs (PDF hyperlinks take priority)
    if pdf_hyperlinks:
        if pdf_hyperlinks.get('github') and not urls.get('github'):
            urls['github'] = pdf_hyperlinks['github'][0]
        if pdf_hyperlinks.get('linkedin') and not urls.get('linkedin'):
            urls['linkedin'] = pdf_hyperlinks['linkedin'][0]
        if pdf_hyperlinks.get('website') and not urls.get('website'):
            urls['website'] = pdf_hyperlinks['website'][0]
    
    # Try to extract name (usually first line or first two lines)
    name_parts = []
    if lines:
        # First line often contains name
        first_line = lines[0]
        # Remove email/phone if present
        first_line_clean = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', first_line)
        first_line_clean = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', first_line_clean)
        first_line_clean = first_line_clean.strip()
        
        # Split by spaces first
        name_parts = first_line_clean.split()
        
        # If no spaces found, try to detect camelCase or concatenated names
        # Look for capital letters that might indicate name boundaries
        if len(name_parts) == 1 and len(first_line_clean) > 5:
            # Try to split on capital letters (e.g., "AmirhoseinMohaddesi" -> ["Amirhosein", "Mohaddesi"])
            camel_case_split = re.findall(r'[A-Z][a-z]+', first_line_clean)
            if len(camel_case_split) >= 2:
                name_parts = camel_case_split
            else:
                # Try splitting on common name patterns (look for common last name endings or patterns)
                # For now, if it's a single word, we'll try to split it intelligently
                # Check if there's a capital letter in the middle (camelCase)
                if re.search(r'[a-z][A-Z]', first_line_clean):
                    # Split on capital letters
                    parts = re.split(r'([A-Z][a-z]+)', first_line_clean)
                    name_parts = [p for p in parts if p and p[0].isupper()]
    
    # Extract title (often near the top, before experience)
    title = None
    for i, line in enumerate(lines[:10]):
        if any(keyword in line.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'researcher']):
            title = line
            break
    
    # Build profile structure
    profile = {
        "identity": {
            "first": name_parts[0] if name_parts else "",
            "last": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
            "title": title or "",
            "email": email or "",
            "phone": phone or "",
            "website": urls.get("website", ""),
            "linkedin": urls.get("linkedin", ""),
            "github": urls.get("github", ""),
            "education": []
        },
        "experience": [],
        "projects": [],
        "skills": [],
        "awards": []
    }
    
    # Extract sections (basic heuristic parsing)
    current_section = None
    experience_items = []
    skill_items = []
    education_items = []
    project_items = []
    award_items = []
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Detect section headers
        if any(keyword in line_lower for keyword in ['experience', 'work experience', 'employment']):
            current_section = 'experience'
            continue
        elif any(keyword in line_lower for keyword in ['education']):
            current_section = 'education'
            continue
        elif any(keyword in line_lower for keyword in ['skills', 'technical skills', 'competencies']):
            current_section = 'skills'
            continue
        elif any(keyword in line_lower for keyword in ['projects', 'project']):
            current_section = 'projects'
            continue
        elif any(keyword in line_lower for keyword in ['awards', 'award', 'honors', 'honor', 'achievements', 'achievement', 'recognition']):
            current_section = 'awards'
            continue
        
        # Collect items based on current section
        if current_section == 'experience':
            # Experience entries can be:
            # - Job titles (often have keywords like "Engineer", "Developer", "Manager")
            # - Company names followed by dates
            # - Bullet points describing responsibilities
            if line:
                # Skip section headers and very short lines
                if len(line) > 5 and not any(keyword in line_lower for keyword in ['experience', 'work', 'employment', 'section']):
                    # Check if this looks like a job title or company
                    has_job_keywords = any(keyword in line_lower for keyword in [
                        'engineer', 'developer', 'manager', 'analyst', 'researcher', 
                        'scientist', 'specialist', 'consultant', 'director', 'lead',
                        'inc', 'llc', 'corp', 'ltd', 'university', 'college'
                    ])
                    has_dates = bool(re.search(r'\d{4}', line))  # Contains year
                    
                    if has_job_keywords or has_dates or len(line) > 15:
                        experience_items.append(line)
        elif current_section == 'skills':
            # Skills are often bullet points or comma-separated
            if '•' in line or '-' in line or ',' in line:
                skills = re.split(r'[•,\-]', line)
                skill_items.extend([s.strip() for s in skills if s.strip()])
            elif line and len(line) < 50:  # Short lines might be individual skills
                skill_items.append(line.strip())
        elif current_section == 'education':
            # Education entries can be:
            # - University/College names
            # - Degree names
            # - Dates
            if line:
                # Skip section headers
                if not any(keyword in line_lower for keyword in ['education', 'section']):
                    # Check if this looks like education content
                    has_edu_keywords = any(keyword in line_lower for keyword in [
                        'university', 'college', 'bachelor', 'master', 'phd', 'ph.d', 
                        'degree', 'diploma', 'certificate', 'major', 'minor'
                    ])
                    has_dates = bool(re.search(r'\d{4}', line))  # Contains year
                    
                    if has_edu_keywords or has_dates or len(line) > 10:
                        education_items.append(line)
        elif current_section == 'projects':
            # Project entries can be:
            # - Project names/titles
            # - Project descriptions
            # - Bullet points describing project features
            if line:
                # Skip section headers
                if not any(keyword in line_lower for keyword in ['projects', 'project', 'section']):
                    # Check if this looks like project content
                    has_project_keywords = any(keyword in line_lower for keyword in [
                        'system', 'application', 'platform', 'tool', 'framework', 'algorithm',
                        'developed', 'designed', 'implemented', 'built', 'created', 'engineered'
                    ])
                    has_tech_keywords = any(keyword in line_lower for keyword in [
                        'python', 'java', 'javascript', 'c++', 'react', 'node', 'api', 'database',
                        'machine learning', 'ai', 'neural', 'deep learning', 'tensorflow', 'pytorch'
                    ])
                    
                    if has_project_keywords or has_tech_keywords or len(line) > 10:
                        project_items.append(line)
        elif current_section == 'awards':
            # Award entries can be:
            # - Award names
            # - Competition names
            # - Recognition titles
            # - Dates
            if line:
                # Skip section headers
                if not any(keyword in line_lower for keyword in ['awards', 'award', 'honors', 'honor', 'achievements', 'achievement', 'section']):
                    # Check if this looks like award content
                    has_award_keywords = any(keyword in line_lower for keyword in [
                        'medal', 'prize', 'winner', 'champion', 'finalist', 'scholarship',
                        'grant', 'fellowship', 'recognition', 'distinction', 'excellence',
                        'olympiad', 'competition', 'contest', 'hackathon', 'icpc', 'acm'
                    ])
                    has_dates = bool(re.search(r'\d{4}', line))  # Contains year
                    has_place = any(keyword in line_lower for keyword in ['1st', '2nd', '3rd', 'first', 'second', 'third', 'gold', 'silver', 'bronze'])
                    
                    if has_award_keywords or has_dates or has_place or len(line) > 5:
                        award_items.append(line)
    
    # Add extracted items to profile
    if skill_items:
        profile["skills"] = list(set(skill_items[:20]))  # Limit and deduplicate
    
    # Parse experience items into structured format
    if experience_items:
        parsed_experiences = []
        current_exp = None
        
        for item in experience_items[:10]:  # Limit to 10 items
            # Try to detect if this is a job title, company, or bullet point
            item_lower = item.lower()
            
            # If it looks like a job title or company (has keywords or is short)
            if any(keyword in item_lower for keyword in ['engineer', 'developer', 'manager', 'at', 'inc', 'llc', 'corp']) or len(item) < 60:
                # Start a new experience entry
                if current_exp:
                    parsed_experiences.append(current_exp)
                
                # Try to extract company and title
                if ' at ' in item_lower:
                    parts = item.split(' at ', 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                elif ' - ' in item:
                    parts = item.split(' - ', 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                else:
                    title = item.strip()
                    company = ""
                
                current_exp = {
                    "organization": company,
                    "title": title,
                    "dates": "",
                    "location": "",
                    "bullets": []
                }
            elif current_exp and (item.startswith('•') or item.startswith('-') or len(item) > 20):
                # This is a bullet point for the current experience
                bullet = item.lstrip('•- ').strip()
                if bullet:
                    current_exp["bullets"].append(bullet)
            elif not current_exp:
                # Create a basic experience entry
                current_exp = {
                    "organization": "",
                    "title": item.strip(),
                    "dates": "",
                    "location": "",
                    "bullets": []
                }
        
        if current_exp:
            parsed_experiences.append(current_exp)
        
        profile["experience"] = parsed_experiences
    
    # Parse education items into structured format
    if education_items:
        parsed_education = []
        
        for item in education_items[:5]:  # Limit to 5 items
            # Try to extract school, degree, dates
            item_clean = item.strip()
            item_lower = item_clean.lower()
            
            # Look for degree keywords
            degree_match = re.search(r'(bachelor|master|ph\.?d|phd|doctorate|associate|diploma|certificate)', item_lower)
            degree = degree_match.group(0) if degree_match else ""
            
            # Look for dates
            date_match = re.search(r'\d{4}', item)
            dates = date_match.group(0) if date_match else ""
            
            # Extract school name (usually the longest capitalized word sequence)
            # Remove degree and dates to get school name
            school_text = item_clean
            if degree_match:
                school_text = school_text[:degree_match.start()] + school_text[degree_match.end():]
            if date_match:
                school_text = re.sub(r'\d{4}.*', '', school_text)
            
            school = school_text.strip()
            
            parsed_education.append({
                "school": school,
                "degree": degree.title() if degree else "",
                "dates": dates,
                "location": ""
            })
        
        profile["identity"]["education"] = parsed_education
    
    # Parse project items into structured format
    if project_items:
        parsed_projects = []
        current_project = None
        
        for item in project_items[:10]:  # Limit to 10 items
            item_lower = item.lower()
            
            # Check if this is a project title/name (usually shorter, capitalized, or has project keywords)
            is_title = (
                len(item) < 60 and 
                (item[0].isupper() or any(keyword in item_lower for keyword in ['system', 'platform', 'tool', 'application', 'framework']))
            )
            
            if is_title and not item.startswith('•') and not item.startswith('-'):
                # Start a new project entry
                if current_project:
                    parsed_projects.append(current_project)
                
                current_project = {
                    "name": item.strip(),
                    "bullets": []
                }
            elif current_project and (item.startswith('•') or item.startswith('-') or len(item) > 20):
                # This is a bullet point for the current project
                bullet = item.lstrip('•- ').strip()
                if bullet:
                    current_project["bullets"].append(bullet)
            elif not current_project:
                # Create a basic project entry
                current_project = {
                    "name": item.strip(),
                    "bullets": []
                }
        
        if current_project:
            parsed_projects.append(current_project)
        
        profile["projects"] = parsed_projects
    
    # Parse award items into structured format
    if award_items:
        parsed_awards = []
        
        for item in award_items[:10]:  # Limit to 10 items
            item_clean = item.strip()
            item_lower = item_clean.lower()
            
            # Awards are usually single-line entries with name, date, and sometimes place
            # Extract date if present
            date_match = re.search(r'\d{4}', item_clean)
            dates = date_match.group(0) if date_match else ""
            
            # Extract place/rank if present
            place_match = re.search(r'(1st|2nd|3rd|first|second|third|gold|silver|bronze)', item_lower)
            place = place_match.group(0) if place_match else ""
            
            # Clean up the award name (remove dates and place indicators)
            award_name = item_clean
            if date_match:
                award_name = re.sub(r'\d{4}.*', '', award_name).strip()
            if place_match:
                award_name = re.sub(r'(1st|2nd|3rd|first|second|third|gold|silver|bronze)', '', award_name, flags=re.IGNORECASE).strip()
            
            # If award name is empty after cleaning, use the original item
            if not award_name:
                award_name = item_clean
            
            parsed_awards.append(award_name)
        
        profile["awards"] = parsed_awards
    
    return profile


def save_profile_json(profile: Dict[str, Any], output_path: str | Path) -> Path:
    """Save profile dict to JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    return output_path

