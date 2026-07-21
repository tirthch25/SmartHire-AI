"""
SmartHire AI — Resume Parser Service (Gemini-powered)

Uses Google Gemini 2.0 Flash to extract structured entities from raw resume text:
- Name, email, phone, LinkedIn, GitHub
- Skills list
- Education history
- Work experience
- Projects
- Certifications

Returns validated Pydantic schema objects.
"""

import json
import re
from typing import Optional

import google.generativeai as genai
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Configure Gemini client once at module load
genai.configure(api_key=settings.GEMINI_API_KEY)


RESUME_EXTRACTION_PROMPT = """
You are an expert resume parser. Extract structured information from the resume text below.

Return ONLY a valid JSON object with this exact schema (no markdown, no explanation):

{
  "name": "Full name or null",
  "email": "Email address or null",
  "phone": "Phone number or null",
  "linkedin": "LinkedIn URL or null",
  "github": "GitHub URL or null",
  "summary": "Professional summary or objective, or null",
  "skills": ["skill1", "skill2"],
  "education": [
    {
      "degree": "Degree name",
      "field": "Field of study",
      "institution": "University/college name",
      "year": 2020,
      "gpa": "GPA if mentioned, or null"
    }
  ],
  "experience": [
    {
      "title": "Job title",
      "company": "Company name",
      "location": "City, Country or null",
      "start_date": "Month Year or null",
      "end_date": "Month Year or 'Present'",
      "duration": "X years Y months or null",
      "description": "Full description of role",
      "achievements": ["quantified achievement 1", "achievement 2"]
    }
  ],
  "projects": [
    {
      "name": "Project name",
      "description": "What it does",
      "technologies": ["tech1", "tech2"],
      "url": "GitHub/demo URL or null"
    }
  ],
  "certifications": [
    {
      "name": "Certification name",
      "issuer": "Issuing body or null",
      "year": 2022
    }
  ]
}

Rules:
- skills must be a flat list of individual skills (not categories)
- Extract ALL skills mentioned anywhere in the document
- For experience, extract achievements separately from general description
- If a field is not found, use null (not empty string)
- year fields must be integers, not strings
- Do not include any text outside the JSON object

RESUME TEXT:
{resume_text}
"""

JOB_DESCRIPTION_PROMPT = """
You are an expert job description analyzer. Extract structured information from the job description below.

Return ONLY a valid JSON object (no markdown, no explanation):

{
  "title": "Job title",
  "company": "Company name or null",
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill3"],
  "required_experience_years": 3,
  "education_requirements": "e.g. Bachelor's degree in CS or equivalent",
  "key_responsibilities": ["responsibility1", "responsibility2"],
  "tech_stack": ["Python", "AWS", "PostgreSQL"],
  "seniority_level": "junior | mid | senior | lead | principal",
  "employment_type": "full-time | part-time | contract | remote"
}

Rules:
- required_skills: all explicitly required skills, technologies, tools
- nice_to_have_skills: "preferred", "bonus", "plus" skills
- required_experience_years: numeric minimum years (0 if not specified)
- Extract tech_stack separately from general skills
- seniority_level: infer from title and requirements

JOB DESCRIPTION:
{jd_text}
"""


class ResumeParser:
    """
    Gemini-powered structured data extraction from resume text.

    Usage:
        parser = ResumeParser()
        parsed = await parser.extract_resume_entities(raw_text)
        jd_data = await parser.extract_job_entities(jd_text)
    """

    def __init__(self):
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def _call_gemini(self, prompt: str) -> dict:
        """
        Call Gemini and return parsed JSON response.

        Args:
            prompt: Full prompt string.

        Returns:
            Parsed dict from Gemini's JSON response.

        Raises:
            ValueError if response is not valid JSON.
        """
        response = self._model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,       # Low temperature for consistent structured output
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text.strip()

        # Strip markdown code fences if Gemini wrapped the JSON
        if raw_text.startswith("```"):
            raw_text = re.sub(r"```(?:json)?\n?", "", raw_text).strip().rstrip("```")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error("Gemini JSON parse failed", raw=raw_text[:500], error=str(e))
            raise ValueError(f"Gemini returned invalid JSON: {e}") from e

    def extract_resume_entities(self, raw_text: str) -> dict:
        """
        Extract structured entities from raw resume text using Gemini.

        Args:
            raw_text: Plain text extracted from PDF.

        Returns:
            Dict matching the ParsedResumeData schema.
        """
        # Truncate to avoid hitting token limits (Gemini 2.0 Flash: 1M tokens, but be safe)
        truncated = raw_text[:15000]
        prompt = RESUME_EXTRACTION_PROMPT.replace("{resume_text}", truncated)

        logger.info("Extracting resume entities with Gemini", text_length=len(truncated))

        data = self._call_gemini(prompt)

        # Normalize and sanitize
        data = self._normalize_resume_data(data)

        logger.info(
            "Resume entities extracted",
            skills_count=len(data.get("skills", [])),
            experience_count=len(data.get("experience", [])),
            education_count=len(data.get("education", [])),
        )

        return data

    def extract_job_entities(self, jd_text: str) -> dict:
        """
        Extract structured requirements from a job description using Gemini.

        Args:
            jd_text: Raw job description text.

        Returns:
            Dict with parsed job requirements.
        """
        truncated = jd_text[:10000]
        prompt = JOB_DESCRIPTION_PROMPT.replace("{jd_text}", truncated)

        logger.info("Extracting job entities with Gemini", text_length=len(truncated))

        data = self._call_gemini(prompt)
        data = self._normalize_job_data(data)

        logger.info(
            "Job entities extracted",
            required_skills=len(data.get("required_skills", [])),
            tech_stack=len(data.get("tech_stack", [])),
        )

        return data

    @staticmethod
    def _normalize_resume_data(data: dict) -> dict:
        """Ensure all expected fields exist with correct types."""
        defaults = {
            "name": None,
            "email": None,
            "phone": None,
            "linkedin": None,
            "github": None,
            "summary": None,
            "skills": [],
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
        }
        result = {**defaults, **data}

        # Ensure skills is a flat list of strings
        if not isinstance(result["skills"], list):
            result["skills"] = []
        result["skills"] = [str(s).strip() for s in result["skills"] if s]

        # Ensure list fields are actually lists
        for list_field in ("education", "experience", "projects", "certifications"):
            if not isinstance(result[list_field], list):
                result[list_field] = []

        return result

    @staticmethod
    def _normalize_job_data(data: dict) -> dict:
        """Ensure all expected fields exist with correct types."""
        defaults = {
            "title": "Unknown Position",
            "company": None,
            "required_skills": [],
            "nice_to_have_skills": [],
            "required_experience_years": 0,
            "education_requirements": None,
            "key_responsibilities": [],
            "tech_stack": [],
            "seniority_level": "mid",
            "employment_type": "full-time",
        }
        result = {**defaults, **data}

        for list_field in ("required_skills", "nice_to_have_skills", "key_responsibilities", "tech_stack"):
            if not isinstance(result[list_field], list):
                result[list_field] = []
            result[list_field] = [str(s).strip() for s in result[list_field] if s]

        if not isinstance(result["required_experience_years"], (int, float)):
            result["required_experience_years"] = 0

        return result


# Module-level singleton
resume_parser = ResumeParser()
