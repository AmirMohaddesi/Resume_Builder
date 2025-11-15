"""
Agent-based resume parser that uses LLM reasoning to extract profile information.
More accurate than regex-based parsing, especially for emails and phone numbers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from crewai import Agent, Task, Crew, Process
from resume_builder.tools.resume_text_reader import ResumeTextReaderTool


def parse_resume_with_agent(resume_path: str | Path) -> Dict[str, Any]:
    """
    Parse a resume file using an LLM agent for more accurate extraction.
    
    Args:
        resume_path: Path to the resume file (PDF, DOCX, DOC, or TXT)
    
    Returns:
        Profile dictionary in the expected format
    """
    resume_path = Path(resume_path)
    
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")
    
    # Create the resume parser agent
    parser_agent = Agent(
        role="Resume Parser",
        goal="Extract structured profile information from resume text with high accuracy. "
             "Pay special attention to correctly identifying email addresses (removing any concatenated phone numbers) "
             "and phone numbers (avoiding dates, IDs, or other numeric patterns).",
        backstory="""You are an expert at parsing resumes and extracting structured information.
        You are meticulous about:
        - Email addresses: Remove any leading digits or phone number fragments. 
          Example: "426-8113Ejohn.doe@gmail.com" should become "john.doe@gmail.com"
        - Phone numbers: Only extract actual phone numbers (7-15 digits), not years (2024), IDs, or dates
        - Names: Extract first and last name correctly
        - URLs: CRITICAL - Only extract URLs that are EXPLICITLY present in the resume text.
          NEVER invent, generate, or infer URLs from email addresses or names.
          If a URL is not explicitly written in the resume, leave that field empty.
        - Experience, Education, Skills: Extract all relevant sections with proper structure
        
        You use the resume_text_reader tool to get the resume text, then carefully analyze it
        to extract all information into a structured JSON format.""",
        verbose=True,
        allow_code_execution=False,
        tools=[ResumeTextReaderTool()],
        llm="gpt-4o-mini",
    )
    
    # Create the parsing task
    parsing_task = Task(
        description=f"""Read the resume file at: {resume_path.absolute()}
        
        Use the resume_text_reader tool to extract the text content from the resume.
        
        Then carefully analyze the text and extract the following information into a JSON object:
        
        {{
            "identity": {{
                "first": "first name",
                "last": "last name",
                "title": "job title or professional title",
                "email": "email address (clean, no phone number fragments)",
                "phone": "phone number (only actual phone numbers, not years or IDs)",
                "website": "personal website URL if explicitly present in resume, otherwise empty string",
                "linkedin": "LinkedIn profile URL if explicitly present in resume, otherwise empty string",
                "github": "GitHub profile URL if explicitly present in resume, otherwise empty string",
                "education": [
                    {{
                        "school": "school/university name",
                        "degree": "degree type and field (e.g., 'B.S. in Computer Science', 'Ph.D. in Computer Science')",
                        "dates": "date range (e.g., '2014 – 2019' or 'September 2019 – June 2025')",
                        "location": "location (city, state, country if available)"
                    }}
                ]
            }},
            "experience": [
                {{
                    "organization": "company name",
                    "title": "job title",
                    "start": "start date",
                    "end": "end date or 'Present'",
                    "description": "description of responsibilities and achievements"
                }}
            ],
            "skills": ["skill1", "skill2", ...],
            "projects": [
                {{
                    "name": "project name",
                    "description": "project description",
                    "technologies": ["tech1", "tech2", ...]
                }}
            ],
            "awards": ["award1", "award2", ...]
        }}
        
        CRITICAL EXTRACTION RULES:
        1. Email: If you see something like "426-8113Ejohn.doe@gmail.com", 
           the email should be "john.doe@gmail.com" (remove phone fragments and extra letters)
        2. Phone: Only extract actual phone numbers (7-15 digits). Do NOT extract:
           - Years like "2024" or "2023"
           - IDs or other numeric patterns
           - Dates in numeric format
        3. URLs: Extract URLs that are EXPLICITLY written in the resume text.
           Look for these patterns:
           - Full URLs: https://example.com, http://example.com
           - Domain with www: www.example.com (add https:// prefix)
           - Plain domains that appear to be websites: example.com, yourname.com (add https:// prefix)
           
           Do NOT invent URLs based on:
           - Email addresses (john@gmail.com does NOT mean website is gmail.com)
           - Names alone without a domain (John Doe does NOT mean website is johndoe.com)
           
           Skip common email/social domains: gmail.com, yahoo.com, facebook.com, etc.
           Include personal portfolio domains like: johndoe.com, janedoe.com, myportfolio.io, etc.
        4. Education: CRITICAL - Education MUST be placed inside identity.education (not at top level).
           Extract ALL education entries you find. Look for sections titled "Education", "Academic Background", 
           "Educational Background", or similar. Each entry should have:
           - school: The full name of the institution
           - degree: The degree type and field (e.g., "B.S. in Computer Science", "Ph.D. in Computer Science")
           - dates: Date range or graduation year (e.g., "2014 – 2019" or "September 2019 – June 2025")
           - location: City, state, country if available
        5. Be thorough: Extract all experiences, education entries, skills, and projects
        6. Output ONLY valid JSON, no markdown code fences or explanatory text
        """,
        agent=parser_agent,
        expected_output="A JSON object with the profile structure above. Output only JSON, no markdown or code fences.",
    )
    
    # Create a minimal crew with just the parsing agent
    crew = Crew(
        agents=[parser_agent],
        tasks=[parsing_task],
        process=Process.sequential,
        verbose=True,
        memory=False,  # No memory needed for parsing
    )
    
    # Execute the parsing task
    result = crew.kickoff()
    
    # Extract JSON from the result
    # The result might be a string containing JSON or a structured object
    result_text = str(result) if hasattr(result, '__str__') else result
    
    # Try to extract JSON from the result
    # Remove markdown code fences if present
    result_text = result_text.strip()
    if result_text.startswith("```json"):
        result_text = result_text[7:]  # Remove ```json
    if result_text.startswith("```"):
        result_text = result_text[3:]  # Remove ```
    if result_text.endswith("```"):
        result_text = result_text[:-3]  # Remove closing ```
    result_text = result_text.strip()
    
    # Parse the JSON
    try:
        profile = json.loads(result_text)
    except json.JSONDecodeError as e:
        # If JSON parsing fails, try to find JSON in the text
        # Look for JSON object boundaries
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                profile = json.loads(result_text[start_idx:end_idx+1])
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse JSON from agent output: {result_text[:200]}...") from e
        else:
            raise ValueError(f"Failed to parse JSON from agent output: {result_text[:200]}...") from e
    
    # Validate and ensure all required fields exist
    if "identity" not in profile:
        profile["identity"] = {}
    if "experience" not in profile:
        profile["experience"] = []
    if "skills" not in profile:
        profile["skills"] = []
    if "projects" not in profile:
        profile["projects"] = []
    if "awards" not in profile:
        profile["awards"] = []
    
    # Ensure identity has all required fields
    identity = profile.get("identity", {})
    for field in ["first", "last", "title", "email", "phone", "website", "linkedin", "github"]:
        if field not in identity:
            identity[field] = ""
    
    # Ensure education is inside identity (not at top level)
    if "education" in profile and "education" not in identity:
        # Move education from top level to identity
        identity["education"] = profile.pop("education")
    elif "education" not in identity:
        identity["education"] = []
    
    # Validate education structure
    if identity.get("education"):
        for edu in identity["education"]:
            # Ensure all required fields exist
            if "school" not in edu:
                edu["school"] = ""
            if "degree" not in edu:
                edu["degree"] = ""
            if "dates" not in edu:
                edu["dates"] = ""
            if "location" not in edu:
                edu["location"] = ""
    
    profile["identity"] = identity
    
    return profile

