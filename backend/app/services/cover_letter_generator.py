"""
SmartHire AI — Cover Letter Generator Service

Generates personalized cover letters using Google Gemini 2.0 Flash.

Inputs:
- Candidate's parsed resume data (name, skills, experience)
- Job description parsed data (title, company, requirements)
- Tone preference (professional/confident/enthusiastic/formal)
- Highlights to emphasize
- Word limit

Output:
- Polished, role-specific cover letter text (~300-500 words)
"""

import json
import re
from typing import Optional

import google.generativeai as genai
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

COVER_LETTER_PROMPT = """
You are a professional cover letter writer. Write a compelling, personalized cover letter.

Candidate Information:
- Name: {candidate_name}
- Key Skills: {skills}
- Most Recent Role: {recent_role}
- Education: {education}
- Career Highlights: {highlights}

Job Information:
- Position: {job_title}
- Company: {company}
- Key Requirements: {requirements}
- Tech Stack: {tech_stack}

Writing Instructions:
- Tone: {tone}
- Word Limit: approximately {word_limit} words
- Structure: Opening paragraph (hook) → Why this company/role → What you bring → Closing CTA
- Do NOT use generic phrases like "I am writing to apply for..."
- Be specific — reference actual skills, real experience, and the company by name
- Make it sound natural and human, not AI-generated
- End with a clear call to action

Write the complete cover letter text only. Do not include any headers, footers, or explanations.
Start directly with "Dear Hiring Manager," or use the company name if known.
"""

TONE_INSTRUCTIONS = {
    "professional": "Maintain a formal, polished tone. Be direct and confident without being casual.",
    "confident": "Project strong self-assurance. Use active language and assertive statements.",
    "enthusiastic": "Show genuine excitement about the role and company. Use energetic, positive language.",
    "formal": "Use traditional formal business letter conventions. Avoid contractions.",
}


class CoverLetterGenerator:
    """
    Gemini-powered personalized cover letter generator.

    Usage:
        generator = CoverLetterGenerator()
        content = generator.generate(
            resume_parsed=parsed_resume,
            job_parsed=parsed_job,
            tone="professional",
            highlights=["5 years Python experience", "led team of 8"],
            word_limit=400,
        )
    """

    def __init__(self):
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def generate(
        self,
        resume_parsed: dict,
        job_parsed: dict,
        tone: str = "professional",
        highlights: Optional[list[str]] = None,
        word_limit: int = 400,
    ) -> str:
        """
        Generate a personalized cover letter.

        Args:
            resume_parsed: Candidate's structured resume data.
            job_parsed: Structured job description data.
            tone: Writing tone (professional/confident/enthusiastic/formal).
            highlights: Specific achievements or points to emphasize.
            word_limit: Target word count.

        Returns:
            Cover letter as a string (plain text, formatted with paragraphs).
        """
        # Build prompt context
        candidate_name = resume_parsed.get("name") or "the candidate"
        skills_str = ", ".join(resume_parsed.get("skills", [])[:12]) or "software development"
        education = self._format_education(resume_parsed.get("education", []))
        recent_role = self._format_recent_role(resume_parsed.get("experience", []))
        highlights_str = "; ".join(highlights) if highlights else "strong technical expertise and team collaboration"
        requirements_str = ", ".join(
            job_parsed.get("required_skills", [])[:8]
            + job_parsed.get("key_responsibilities", [])[:3]
        ) or "software engineering skills"
        tech_stack_str = ", ".join(job_parsed.get("tech_stack", [])[:8]) or "relevant technologies"
        tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["professional"])

        prompt = COVER_LETTER_PROMPT.format(
            candidate_name=candidate_name,
            skills=skills_str,
            recent_role=recent_role,
            education=education,
            highlights=highlights_str,
            job_title=job_parsed.get("title", "Software Engineer"),
            company=job_parsed.get("company") or "your company",
            requirements=requirements_str,
            tech_stack=tech_stack_str,
            tone=f"{tone.capitalize()} — {tone_instruction}",
            word_limit=word_limit,
        )

        logger.info(
            "Generating cover letter with Gemini",
            tone=tone,
            word_limit=word_limit,
            job_title=job_parsed.get("title"),
        )

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,        # Higher for more creative, natural writing
                    max_output_tokens=2048,
                ),
            )

            content = response.text.strip()

            # Basic cleanup
            content = self._clean_content(content)

            logger.info(
                "Cover letter generated",
                word_count=len(content.split()),
                tone=tone,
            )

            return content

        except Exception as e:
            logger.error("Cover letter generation failed", error=str(e))
            return self._fallback_letter(candidate_name, job_parsed)

    @staticmethod
    def _format_education(education: list) -> str:
        """Format education list into a brief string."""
        if not education:
            return "Not specified"
        edu = education[0]
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        institution = edu.get("institution", "")
        return f"{degree} in {field} from {institution}".strip(" in from")

    @staticmethod
    def _format_recent_role(experience: list) -> str:
        """Format the most recent role into a brief string."""
        if not experience:
            return "No prior experience listed"
        role = experience[0]
        title = role.get("title", "")
        company = role.get("company", "")
        duration = role.get("duration", "")
        return f"{title} at {company} ({duration})".strip(" at ()")

    @staticmethod
    def _clean_content(content: str) -> str:
        """Remove any AI artifacts or formatting issues from the generated letter."""
        # Remove markdown headers
        content = re.sub(r"#+\s+", "", content)
        # Remove asterisks (bold/italic markdown)
        content = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", content)
        # Normalize multiple blank lines to single blank line
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    @staticmethod
    def _fallback_letter(candidate_name: str, job_parsed: dict) -> str:
        """Return a minimal fallback cover letter if Gemini fails."""
        return (
            f"Dear Hiring Manager,\n\n"
            f"I am {candidate_name}, and I am excited to apply for the "
            f"{job_parsed.get('title', 'open position')} role"
            + (f" at {job_parsed.get('company')}" if job_parsed.get("company") else "")
            + ".\n\n"
            "My background and skills make me a strong candidate for this opportunity, "
            "and I look forward to discussing how I can contribute to your team.\n\n"
            "Thank you for your consideration.\n\n"
            f"Sincerely,\n{candidate_name}"
        )


# Module-level singleton
cover_letter_generator = CoverLetterGenerator()
