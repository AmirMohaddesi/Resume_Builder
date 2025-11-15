"""
Tests for LaTeX resume template generation.
"""

import pytest

from resume_builder.latex.resume_template import (
    build_preamble,
    build_header,
    build_summary,
    build_experience_section,
    build_education_section,
    build_skills_section,
    build_projects_section,
)


class TestBuildPreamble:
    """Test preamble generation."""
    
    def test_build_preamble_basic(self):
        """Test basic preamble generation."""
        identity = {
            "first": "John",
            "last": "Doe",
            "email": "john@example.com",
            "phone": "1234567890"
        }
        
        preamble = build_preamble(identity)
        
        assert "\\name{John}{Doe}" in preamble
        assert "\\email{john@example.com}" in preamble
        assert "\\phone" in preamble
    
    def test_build_preamble_with_optional_fields(self):
        """Test preamble with optional fields."""
        identity = {
            "first": "John",
            "last": "Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "website": "https://johndoe.com",
            "linkedin": "johndoe",
            "github": "johndoe"
        }
        
        preamble = build_preamble(identity)
        
        assert "\\homepage" in preamble
        assert "\\social[linkedin]" in preamble
        assert "\\social[github]" in preamble


class TestBuildHeader:
    """Test header generation."""
    
    def test_build_header_basic(self):
        """Test basic header generation."""
        title_line = "Software Engineer | Python | AWS"
        contact_info = {
            "phone": "1234567890",
            "email": "john@example.com",
            "location": "San Francisco, CA"
        }
        
        header = build_header(title_line, contact_info)
        
        assert "Software Engineer" in header
        assert "john@example.com" in header
        assert "1234567890" in header or "(123)" in header  # Phone may be formatted
    
    def test_build_header_empty(self):
        """Test header with empty inputs."""
        header = build_header("", {})
        
        # Should return empty string or minimal content
        assert isinstance(header, str)


class TestBuildSummary:
    """Test summary section generation."""
    
    def test_build_summary_basic(self):
        """Test basic summary generation."""
        summary_text = "Experienced software engineer with 5 years of experience."
        result = build_summary(summary_text)
        
        assert "\\section*{Summary}" in result
        assert "Experienced" in result
    
    def test_build_summary_empty(self):
        """Test empty summary."""
        result = build_summary("")
        
        assert result == ""


class TestBuildExperienceSection:
    """Test experience section generation."""
    
    def test_build_experience_section_basic(self):
        """Test basic experience section."""
        experiences = [
            {
                "organization": "Company A",
                "title": "Software Engineer",
                "dates": "2020-2021",
                "location": "San Francisco",
                "description": "Worked on projects"
            }
        ]
        
        result = build_experience_section(experiences)
        
        assert "\\section*{Experience}" in result
        assert "Company A" in result
        assert "Software Engineer" in result
        assert "\\cventry" in result
    
    def test_build_experience_section_empty(self):
        """Test empty experience section."""
        result = build_experience_section([])
        
        assert result == ""


class TestBuildEducationSection:
    """Test education section generation."""
    
    def test_build_education_section_basic(self):
        """Test basic education section."""
        education = [
            {
                "degree": "BS Computer Science",
                "institution": "University",
                "dates": "2016-2020",
                "location": "City, State"
            }
        ]
        
        result = build_education_section(education)
        
        assert "\\section*{Education}" in result
        assert "BS Computer Science" in result
        assert "\\cventry" in result


class TestBuildSkillsSection:
    """Test skills section generation."""
    
    def test_build_skills_section_basic(self):
        """Test basic skills section."""
        skills = ["Python", "JavaScript", "AWS"]
        
        result = build_skills_section(skills)
        
        assert "\\section*{Skills}" in result
        assert "Python" in result
        assert "JavaScript" in result
        assert "AWS" in result
    
    def test_build_skills_section_empty(self):
        """Test empty skills section."""
        result = build_skills_section([])
        
        assert result == ""


class TestBuildProjectsSection:
    """Test projects section generation."""
    
    def test_build_projects_section_basic(self):
        """Test basic projects section."""
        projects = [
            {
                "name": "Project A",
                "description": "Description of project",
                "url": "https://project.com"
            }
        ]
        
        result = build_projects_section(projects)
        
        assert "\\section*{Projects}" in result
        assert "Project A" in result
        assert "\\href" in result  # Should have hyperlink
    
    def test_build_projects_section_no_url(self):
        """Test projects section without URL."""
        projects = [
            {
                "name": "Project A",
                "description": "Description"
            }
        ]
        
        result = build_projects_section(projects)
        
        assert "Project A" in result
        # Should not have \href if no URL
        assert "\\href{https://project.com}" not in result

