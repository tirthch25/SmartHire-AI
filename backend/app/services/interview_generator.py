"""
SmartHire AI — Interview Question Generator Service

Generates role-specific, multi-category interview questions using Gemini 2.0 Flash.

Categories: Technical, Behavioral, Situational, Culture Fit
Difficulty levels: easy, medium, hard

Returns structured list of Question objects.
"""

import json
import re
from typing import Optional

import google.generativeai as genai
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

INTERVIEW_GENERATION_PROMPT = """
You are an expert technical interviewer. Generate interview questions for a candidate applying to:

Job Title: {job_title}
Seniority Level: {seniority_level}
Key Technologies: {tech_stack}
Focus Areas: {focus_areas}
Total Questions: {question_count}

Generate a mix of question categories:
- Technical ({technical_count} questions): coding, system design, technical concepts
- Behavioral ({behavioral_count} questions): past experience, STAR-format scenarios
- Situational ({situational_count} questions): hypothetical role-specific scenarios
- Culture Fit ({culture_count} questions): values, teamwork, growth mindset

Candidate's background:
- Skills: {candidate_skills}
- Experience: {candidate_experience}

Return ONLY a valid JSON array of question objects:
[
  {{
    "id": 1,
    "question": "Full question text?",
    "category": "Technical|Behavioral|Situational|Culture Fit",
    "difficulty": "easy|medium|hard",
    "hints": ["hint 1", "hint 2"],
    "sample_answer": "A brief indication of what a strong answer covers (1-2 sentences)"
  }}
]

Rules:
- Questions must be specific to the role and technologies
- Behavioral questions must use STAR format prompts
- Hard questions should test deep expertise
- Make questions realistic and commonly asked in real interviews
- Return ONLY the JSON array, nothing else
"""


class InterviewGenerator:
    """
    Gemini-powered interview question generator.

    Usage:
        generator = InterviewGenerator()
        questions = generator.generate(
            resume_parsed=parsed_resume,
            job_parsed=parsed_job,
            focus_areas=["system design", "databases"],
            difficulty="medium",
            question_count=15,
        )
    """

    def __init__(self):
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def generate(
        self,
        resume_parsed: dict,
        job_parsed: dict,
        focus_areas: Optional[list[str]] = None,
        difficulty: str = "medium",
        question_count: int = 15,
    ) -> list[dict]:
        """
        Generate interview questions tailored to the role and candidate.

        Args:
            resume_parsed: Candidate's parsed resume data.
            job_parsed: Parsed job description data.
            focus_areas: Specific areas to emphasize (optional).
            difficulty: Base difficulty level (easy/medium/hard).
            question_count: Total number of questions to generate.

        Returns:
            List of question dicts matching the Question schema.
        """
        # Compute category distribution
        distribution = self._compute_distribution(question_count, focus_areas)

        # Build candidate context
        skills_summary = ", ".join(resume_parsed.get("skills", [])[:15])
        experience_summary = self._summarize_experience(resume_parsed.get("experience", []))
        tech_stack = ", ".join(job_parsed.get("tech_stack", [])[:10])
        focus_str = ", ".join(focus_areas) if focus_areas else "general role competencies"

        prompt = INTERVIEW_GENERATION_PROMPT.format(
            job_title=job_parsed.get("title", "Software Engineer"),
            seniority_level=job_parsed.get("seniority_level", "mid"),
            tech_stack=tech_stack or "Python, general software development",
            focus_areas=focus_str,
            question_count=question_count,
            technical_count=distribution["Technical"],
            behavioral_count=distribution["Behavioral"],
            situational_count=distribution["Situational"],
            culture_count=distribution["Culture Fit"],
            candidate_skills=skills_summary or "General software development",
            candidate_experience=experience_summary,
        )

        logger.info(
            "Generating interview questions with Gemini",
            job_title=job_parsed.get("title"),
            question_count=question_count,
            difficulty=difficulty,
        )

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.6,       # Higher temp for more varied questions
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("```")

            questions = json.loads(raw)

            if not isinstance(questions, list):
                raise ValueError("Expected JSON array")

            # Normalize and validate
            questions = self._normalize_questions(questions, question_count)

            logger.info("Interview questions generated", count=len(questions))
            return questions

        except Exception as e:
            logger.error("Interview generation failed", error=str(e))
            # Return a minimal set of fallback questions
            return self._fallback_questions(job_parsed, question_count)

    @staticmethod
    def _compute_distribution(question_count: int, focus_areas: Optional[list]) -> dict:
        """Compute how many questions per category."""
        # Default distribution
        base = {
            "Technical": int(question_count * 0.45),
            "Behavioral": int(question_count * 0.30),
            "Situational": int(question_count * 0.15),
            "Culture Fit": int(question_count * 0.10),
        }
        # Ensure total equals question_count
        total = sum(base.values())
        diff = question_count - total
        base["Technical"] += diff
        return base

    @staticmethod
    def _summarize_experience(experience: list) -> str:
        """Create a brief experience summary string."""
        if not experience:
            return "No prior work experience listed"
        titles = [e.get("title", "") for e in experience[:3] if e.get("title")]
        return f"Previously worked as: {', '.join(titles)}"

    @staticmethod
    def _normalize_questions(questions: list, target_count: int) -> list[dict]:
        """Validate and normalize question objects."""
        valid_categories = {"Technical", "Behavioral", "Situational", "Culture Fit"}
        valid_difficulties = {"easy", "medium", "hard"}

        normalized = []
        for i, q in enumerate(questions[:target_count], start=1):
            if not isinstance(q, dict):
                continue
            normalized.append({
                "id": i,
                "question": str(q.get("question", "")).strip(),
                "category": q.get("category", "Technical") if q.get("category") in valid_categories else "Technical",
                "difficulty": q.get("difficulty", "medium") if q.get("difficulty") in valid_difficulties else "medium",
                "hints": q.get("hints") if isinstance(q.get("hints"), list) else None,
                "sample_answer": q.get("sample_answer") or None,
            })

        return [q for q in normalized if q["question"]]

    @staticmethod
    def _fallback_questions(job_parsed: dict, count: int) -> list[dict]:
        """Generate generic fallback questions if Gemini fails."""
        job_title = job_parsed.get("title", "Software Engineer")
        return [
            {
                "id": 1,
                "question": f"Tell me about your experience relevant to the {job_title} role.",
                "category": "Behavioral",
                "difficulty": "easy",
                "hints": ["Use the STAR method (Situation, Task, Action, Result)"],
                "sample_answer": None,
            },
            {
                "id": 2,
                "question": "Describe a challenging technical problem you solved recently.",
                "category": "Technical",
                "difficulty": "medium",
                "hints": ["Focus on your approach and the technologies used"],
                "sample_answer": None,
            },
            {
                "id": 3,
                "question": "How do you prioritize tasks when working on multiple projects?",
                "category": "Situational",
                "difficulty": "medium",
                "hints": ["Mention specific frameworks or methods you use"],
                "sample_answer": None,
            },
        ][:count]


# Module-level singleton
interview_generator = InterviewGenerator()
