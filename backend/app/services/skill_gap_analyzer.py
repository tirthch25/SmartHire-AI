"""
SmartHire AI — Skill Gap Analyzer Service

Compares resume skills against job required skills and produces:
1. Matched skills (candidate has)
2. Missing skills (candidate lacks, with importance ranking)
3. Bonus skills (candidate has, not required)
4. Gap score (0 = perfect match, 100 = all skills missing)
5. Learning recommendations via Gemini
"""

import json
import re
from typing import Optional

import google.generativeai as genai
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

SKILL_GAP_PROMPT = """
You are a career advisor. Analyze the skill gap between a candidate and a job requirement.

Missing skills (candidate needs to learn): {missing_skills}
Job title: {job_title}
Required experience level: {seniority_level}

For each missing skill, provide:
1. Its importance level (high/medium/low) based on the job requirements
2. 2 specific, real learning resources (course names and URLs)

Return ONLY a valid JSON array:
[
  {{
    "skill": "skill name",
    "importance": "high|medium|low",
    "learning_resources": [
      {{"title": "Resource name", "url": "https://example.com"}},
      {{"title": "Resource name 2", "url": "https://example2.com"}}
    ]
  }}
]

Focus on the top 8 most important missing skills only.
Return only the JSON array, no other text.
"""

RECOMMENDATIONS_PROMPT = """
As a career coach, provide 3-5 specific, actionable recommendations for a candidate applying to a {job_title} role.

Their situation:
- Has these skills: {matched_skills}
- Missing these skills: {missing_skills}
- Gap score: {gap_score}%

Return ONLY a JSON array of recommendation strings:
["recommendation 1", "recommendation 2", "recommendation 3"]
"""


class SkillGapAnalyzer:
    """
    Analyzes skill gaps between resume and job description.

    Usage:
        analyzer = SkillGapAnalyzer()
        result = analyzer.analyze(
            resume_parsed=parsed_resume,
            job_parsed=parsed_job,
        )
    """

    def __init__(self):
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def analyze(self, resume_parsed: dict, job_parsed: dict) -> dict:
        """
        Perform full skill gap analysis.

        Returns:
            Dict with matched_skills, missing_skills (with resources),
            bonus_skills, gap_score, recommendations.
        """
        resume_skills = {s.lower().strip() for s in resume_parsed.get("skills", [])}
        required_skills = {
            s.lower().strip()
            for s in (
                job_parsed.get("required_skills", [])
                + job_parsed.get("tech_stack", [])
            )
        }
        nice_to_have = {
            s.lower().strip() for s in job_parsed.get("nice_to_have_skills", [])
        }
        all_job_skills = required_skills | nice_to_have

        matched = sorted(resume_skills & required_skills)
        missing_required = sorted(required_skills - resume_skills)
        bonus = sorted(resume_skills - all_job_skills)

        # Gap score: percentage of required skills that are missing
        gap_score = (
            (len(missing_required) / len(required_skills)) * 100
            if required_skills
            else 0.0
        )
        gap_score = round(gap_score, 2)

        # Enrich missing skills with learning resources via Gemini
        if missing_required:
            missing_with_resources = self._enrich_with_resources(
                missing_skills=missing_required[:10],
                job_title=job_parsed.get("title", "the position"),
                seniority_level=job_parsed.get("seniority_level", "mid"),
            )
        else:
            missing_with_resources = []

        # Generate recommendations
        recommendations = self._generate_recommendations(
            matched_skills=matched,
            missing_skills=missing_required,
            job_title=job_parsed.get("title", "the position"),
            gap_score=gap_score,
        )

        logger.info(
            "Skill gap analysis complete",
            matched=len(matched),
            missing=len(missing_required),
            bonus=len(bonus),
            gap_score=gap_score,
        )

        return {
            "matched_skills": matched,
            "missing_skills": missing_with_resources,
            "bonus_skills": bonus[:10],
            "gap_score": gap_score,
            "recommendations": recommendations,
        }

    def _enrich_with_resources(
        self,
        missing_skills: list[str],
        job_title: str,
        seniority_level: str,
    ) -> list[dict]:
        """
        Use Gemini to generate learning resources for each missing skill.

        Returns list of {skill, importance, learning_resources} dicts.
        """
        prompt = SKILL_GAP_PROMPT.format(
            missing_skills=", ".join(missing_skills),
            job_title=job_title,
            seniority_level=seniority_level,
        )

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("```")

            enriched = json.loads(raw)
            if isinstance(enriched, list):
                return enriched[:8]

        except Exception as e:
            logger.warning("Gemini skill enrichment failed", error=str(e))

        # Fallback: return basic structure without resources
        return [
            {"skill": skill, "importance": "medium", "learning_resources": []}
            for skill in missing_skills[:8]
        ]

    def _generate_recommendations(
        self,
        matched_skills: list[str],
        missing_skills: list[str],
        job_title: str,
        gap_score: float,
    ) -> list[str]:
        """Generate actionable career recommendations using Gemini."""
        prompt = RECOMMENDATIONS_PROMPT.format(
            job_title=job_title,
            matched_skills=", ".join(matched_skills[:10]),
            missing_skills=", ".join(missing_skills[:8]),
            gap_score=round(gap_score, 0),
        )

        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("```")

            recs = json.loads(raw)
            if isinstance(recs, list):
                return [str(r) for r in recs[:5]]

        except Exception as e:
            logger.warning("Gemini recommendations failed", error=str(e))

        # Fallback recommendations
        recs = []
        if missing_skills:
            recs.append(f"Prioritize learning {missing_skills[0]} to meet the core requirements")
        if len(missing_skills) > 3:
            recs.append("Consider a structured learning plan to address the skill gaps systematically")
        if matched_skills:
            recs.append(f"Highlight your {matched_skills[0]} experience prominently in your application")
        return recs


# Module-level singleton
skill_gap_analyzer = SkillGapAnalyzer()
