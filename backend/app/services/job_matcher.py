"""
SmartHire AI — Job Matcher Service

Computes semantic similarity between a resume and a job description using:
1. Cosine similarity between SentenceTransformer embeddings (primary)
2. Direct skills overlap (secondary)
3. Education match heuristic (tertiary)

Returns structured match result with breakdown by dimension.
"""

from typing import Optional

import structlog

from app.services.embedding_service import embedding_service

logger = structlog.get_logger(__name__)


class JobMatcher:
    """
    Semantic matching between resume and job description.

    Usage:
        matcher = JobMatcher()
        result = matcher.match(
            resume_parsed=parsed_resume_dict,
            job_parsed=parsed_job_dict,
            resume_embedding=[...],
            job_embedding=[...],
        )
    """

    def match(
        self,
        resume_parsed: dict,
        job_parsed: dict,
        resume_embedding: Optional[list[float]] = None,
        job_embedding: Optional[list[float]] = None,
    ) -> dict:
        """
        Compute multi-dimensional match between resume and job.

        Args:
            resume_parsed: Gemini-extracted resume data.
            job_parsed: Gemini-extracted job data.
            resume_embedding: Pre-computed embedding for resume text.
            job_embedding: Pre-computed embedding for job description.

        Returns:
            Dict with overall_match_score, skills_overlap,
            experience_similarity, education_match,
            matched_skills, missing_skills, bonus_skills.
        """
        # ── Skills overlap ─────────────────────────────────────
        resume_skills = {s.lower().strip() for s in resume_parsed.get("skills", [])}
        all_job_skills = set(
            s.lower().strip()
            for s in (
                job_parsed.get("required_skills", [])
                + job_parsed.get("tech_stack", [])
                + job_parsed.get("nice_to_have_skills", [])
            )
        )
        required_skills = {
            s.lower().strip()
            for s in (
                job_parsed.get("required_skills", [])
                + job_parsed.get("tech_stack", [])
            )
        }

        matched = list(resume_skills & required_skills)
        missing = list(required_skills - resume_skills)
        bonus = list(resume_skills - all_job_skills)

        skills_overlap = len(matched) / max(len(required_skills), 1)

        # ── Semantic similarity ────────────────────────────────
        if resume_embedding and job_embedding:
            semantic_sim = embedding_service.compute_similarity(resume_embedding, job_embedding)
        else:
            # Fall back to skills overlap if no embeddings
            semantic_sim = skills_overlap

        # ── Education match ────────────────────────────────────
        education_match = self._check_education_match(resume_parsed, job_parsed)

        # ── Overall match score ────────────────────────────────
        # Weighted: 50% semantic, 35% skills, 15% education
        edu_score = 1.0 if education_match else 0.5
        overall = (
            (semantic_sim * 0.50)
            + (skills_overlap * 0.35)
            + (edu_score * 0.15)
        ) * 100
        overall = round(min(max(overall, 0.0), 100.0), 2)

        logger.info(
            "Job match computed",
            overall=overall,
            semantic_sim=round(semantic_sim, 4),
            skills_overlap=round(skills_overlap, 4),
            education_match=education_match,
        )

        return {
            "overall_match_score": overall,
            "skills_overlap": round(skills_overlap, 4),
            "experience_similarity": round(semantic_sim, 4),
            "education_match": education_match,
            "matched_skills": matched,
            "missing_skills": missing,
            "bonus_skills": bonus[:15],  # Cap at 15
        }

    @staticmethod
    def _check_education_match(resume_parsed: dict, job_parsed: dict) -> bool:
        """
        Simple heuristic: check if education requirement is met.
        Returns True if requirement is not specified or there's a degree in the resume.
        """
        edu_requirement = (job_parsed.get("education_requirements") or "").lower()
        resume_education = resume_parsed.get("education", [])

        if not edu_requirement:
            return True  # No requirement specified

        if not resume_education:
            return False  # No education listed

        # Check if resume mentions common degree types that satisfy requirement
        degree_keywords = {
            "bachelor": ["bachelor", "b.s", "b.e", "b.tech", "b.sc", "undergraduate"],
            "master": ["master", "m.s", "m.e", "m.tech", "m.sc", "mba", "graduate"],
            "phd": ["ph.d", "phd", "doctorate", "doctoral"],
        }

        resume_degrees = " ".join(
            f"{e.get('degree', '')} {e.get('field', '')}" for e in resume_education
        ).lower()

        for level, keywords in degree_keywords.items():
            if level in edu_requirement:
                if any(kw in resume_degrees for kw in keywords):
                    return True
                # Higher degrees satisfy lower requirements
                if level == "bachelor" and any(
                    kw in resume_degrees
                    for kw in degree_keywords["master"] + degree_keywords["phd"]
                ):
                    return True

        return False


# Module-level singleton
job_matcher = JobMatcher()
