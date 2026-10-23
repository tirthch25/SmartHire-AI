"""
SmartHire AI — ATS Scoring Engine

Computes an ATS (Applicant Tracking System) compatibility score from 5 components:

    Component               Weight  Method
    ─────────────────────────────────────────────────────────────────
    Keyword Match           30%     TF-IDF token overlap
    Formatting              15%     Structural heuristics
    Section Completeness    15%     Required section detection
    Skills Match            20%     Cosine similarity (SentenceTransformers)
    Experience Relevance    20%     Semantic vector search (pgvector)
    ─────────────────────────────────────────────────────────────────
    Overall Score           100%    Weighted sum (0–100)

All individual scores are 0–100. The weighted sum is also 0–100.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = structlog.get_logger(__name__)

# ── Required resume sections ──────────────────────────────────────────────────
REQUIRED_SECTIONS = {
    "experience": ["experience", "work experience", "employment", "professional experience"],
    "education": ["education", "academic", "qualifications", "degree"],
    "skills": ["skills", "technical skills", "competencies", "expertise"],
    "contact": ["email", "phone", "linkedin", "contact"],
    "summary": ["summary", "objective", "profile", "about"],
}

IMPORTANT_SECTIONS = {
    "projects": ["project", "portfolio"],
    "certifications": ["certification", "license", "credential"],
}


@dataclass
class ComponentScore:
    """Score and metadata for one ATS component."""
    score: float        # 0-100
    weight: float
    weighted: float     # score * weight
    details: dict = field(default_factory=dict)


@dataclass
class ATSScoreResult:
    """Full ATS scoring result with all components."""
    overall_score: float
    keyword_score: float
    formatting_score: float
    section_score: float
    skills_score: float
    experience_score: float
    components: dict[str, ComponentScore]
    detailed_report: dict


class ATSScorer:
    """
    Five-component ATS scoring engine.

    Usage:
        scorer = ATSScorer()
        result = scorer.score(
            resume_text=raw_text,
            resume_parsed=parsed_data,
            job_parsed=job_data,
            resume_embedding=embedding_vector,    # from EmbeddingService
            job_embedding=job_embedding_vector,   # from EmbeddingService
        )
    """

    WEIGHTS = {
        "keyword_match": 0.30,
        "formatting": 0.15,
        "section_completeness": 0.15,
        "skills_match": 0.20,
        "experience_relevance": 0.20,
    }

    def score(
        self,
        resume_text: str,
        resume_parsed: dict,
        job_parsed: dict,
        resume_embedding: Optional[list] = None,
        job_embedding: Optional[list] = None,
    ) -> ATSScoreResult:
        """
        Compute the full ATS score.

        Args:
            resume_text: Raw text extracted from the resume PDF.
            resume_parsed: Gemini-extracted structured resume data.
            job_parsed: Gemini-extracted structured job data.
            resume_embedding: 384-dim vector from SentenceTransformers (optional).
            job_embedding: 384-dim vector for job description (optional).

        Returns:
            ATSScoreResult with all component scores and detailed report.
        """
        # ── Component 1: Keyword Match (30%) ──────────────────
        keyword_comp = self._score_keyword_match(resume_text, job_parsed)

        # ── Component 2: Formatting (15%) ─────────────────────
        formatting_comp = self._score_formatting(resume_text, resume_parsed)

        # ── Component 3: Section Completeness (15%) ───────────
        section_comp = self._score_section_completeness(resume_text, resume_parsed)

        # ── Component 4: Skills Match (20%) ───────────────────
        skills_comp = self._score_skills_match(
            resume_parsed, job_parsed, resume_embedding, job_embedding
        )

        # ── Component 5: Experience Relevance (20%) ───────────
        experience_comp = self._score_experience_relevance(
            resume_parsed, job_parsed, resume_embedding, job_embedding
        )

        # ── Overall weighted score ─────────────────────────────
        overall = (
            keyword_comp.weighted
            + formatting_comp.weighted
            + section_comp.weighted
            + skills_comp.weighted
            + experience_comp.weighted
        )
        overall = round(min(max(overall, 0.0), 100.0), 2)

        components = {
            "keyword_match": keyword_comp,
            "formatting": formatting_comp,
            "section_completeness": section_comp,
            "skills_match": skills_comp,
            "experience_relevance": experience_comp,
        }

        # ── Build detailed report ──────────────────────────────
        report = self._build_report(
            resume_text, resume_parsed, job_parsed, components
        )

        logger.info(
            "ATS scoring complete",
            overall=overall,
            keyword=keyword_comp.score,
            formatting=formatting_comp.score,
            section=section_comp.score,
            skills=skills_comp.score,
            experience=experience_comp.score,
        )

        return ATSScoreResult(
            overall_score=overall,
            keyword_score=keyword_comp.score,
            formatting_score=formatting_comp.score,
            section_score=section_comp.score,
            skills_score=skills_comp.score,
            experience_score=experience_comp.score,
            components=components,
            detailed_report=report,
        )

    # ── Component 1: Keyword Match ────────────────────────────────────────────

    def _score_keyword_match(self, resume_text: str, job_parsed: dict) -> ComponentScore:
        """
        Compute keyword overlap between resume and job description using TF-IDF.

        Method:
        1. Extract job keywords from required_skills + tech_stack + key_responsibilities.
        2. Check which keywords appear in resume text.
        3. Score = matched / total * 100.
        """
        job_keywords = self._extract_job_keywords(job_parsed)

        if not job_keywords:
            return ComponentScore(
                score=50.0,
                weight=self.WEIGHTS["keyword_match"],
                weighted=50.0 * self.WEIGHTS["keyword_match"],
                details={"matched_keywords": [], "missing_keywords": [], "note": "No keywords in JD"},
            )

        resume_lower = resume_text.lower()
        matched = []
        missing = []

        for keyword in job_keywords:
            kw_lower = keyword.lower()
            # Match whole word or phrase
            pattern = r"\b" + re.escape(kw_lower) + r"\b"
            if re.search(pattern, resume_lower):
                matched.append(keyword)
            else:
                missing.append(keyword)

        score = (len(matched) / len(job_keywords)) * 100
        score = round(min(score, 100.0), 2)

        # Boost for high keyword density
        if score >= 80:
            score = min(score + 5, 100)

        return ComponentScore(
            score=score,
            weight=self.WEIGHTS["keyword_match"],
            weighted=round(score * self.WEIGHTS["keyword_match"], 2),
            details={
                "matched_keywords": matched,
                "missing_keywords": missing,
                "total_keywords": len(job_keywords),
                "match_rate": f"{score:.1f}%",
            },
        )

    @staticmethod
    def _extract_job_keywords(job_parsed: dict) -> list[str]:
        """Collect all unique keywords from the job parsed data."""
        keywords = set()
        for field_name in ("required_skills", "tech_stack", "nice_to_have_skills"):
            for kw in job_parsed.get(field_name, []):
                if kw and len(kw.strip()) > 1:
                    keywords.add(kw.strip())
        return list(keywords)

    # ── Component 2: Formatting ────────────────────────────────────────────────

    def _score_formatting(self, resume_text: str, resume_parsed: dict) -> ComponentScore:
        """
        Score resume formatting quality using heuristics.

        Checks:
        - Has bullet points (+20 pts)
        - Word count in optimal range 300-800 (+25 pts)
        - Has clear section headers (+20 pts)
        - Contact info present (+15 pts)
        - No wall-of-text paragraphs (+10 pts)
        - Not excessively long (-15 pts if >1200 words)
        """
        score = 0.0
        issues = []
        positives = []

        # Bullet points
        has_bullets = bool(re.search(r"^[\s]*[•·▪▸◆\-\*]\s+", resume_text, re.MULTILINE))
        if has_bullets:
            score += 20
            positives.append("Uses bullet points for readability")
        else:
            issues.append("Add bullet points to list achievements and responsibilities")

        # Word count
        word_count = len(resume_text.split())
        if 300 <= word_count <= 1000:
            score += 25
            positives.append(f"Appropriate length ({word_count} words)")
        elif word_count < 300:
            issues.append(f"Resume appears too short ({word_count} words). Add more detail.")
        elif 1001 <= word_count <= 1200:
            score += 15
        else:
            score += 10
            issues.append(f"Resume may be too long ({word_count} words). Aim for 1-2 pages.")

        # Section headers (look for lines in ALL CAPS or Title Case that are short)
        lines = resume_text.split("\n")
        header_like = [
            line for line in lines
            if line.strip() and len(line.strip()) < 40
            and (line.strip().isupper() or line.strip().istitle())
        ]
        if len(header_like) >= 3:
            score += 20
            positives.append("Clear section headers detected")
        else:
            issues.append("Add clear, distinct section headers (e.g., EXPERIENCE, EDUCATION)")

        # Contact info
        has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resume_text))
        has_phone = bool(re.search(r"[\+\(]?[\d\s\-\.]{7,15}", resume_text))
        if has_email and has_phone:
            score += 15
            positives.append("Contact information is present")
        elif has_email:
            score += 8
            issues.append("Add phone number to contact information")
        else:
            issues.append("Add email and phone to contact information")

        # No massive unbroken paragraphs (>200 word paragraphs = bad formatting)
        paragraphs = re.split(r"\n\s*\n", resume_text)
        large_paragraphs = [p for p in paragraphs if len(p.split()) > 200]
        if not large_paragraphs:
            score += 10
            positives.append("Content is well-organized without text walls")
        else:
            issues.append("Break up large text blocks into shorter bullet points")

        # Quantified achievements bonus
        quantified = re.findall(r"\d+[\%\+]?[\s]*(percent|%|\+|x|times|users|employees|revenue)", resume_text, re.IGNORECASE)
        if len(quantified) >= 3:
            score += 10
            positives.append("Contains quantified achievements")

        score = round(min(score, 100.0), 2)

        return ComponentScore(
            score=score,
            weight=self.WEIGHTS["formatting"],
            weighted=round(score * self.WEIGHTS["formatting"], 2),
            details={
                "formatting_issues": issues,
                "formatting_positives": positives,
                "word_count": word_count,
                "has_bullet_points": has_bullets,
            },
        )

    # ── Component 3: Section Completeness ────────────────────────────────────

    def _score_section_completeness(self, resume_text: str, resume_parsed: dict) -> ComponentScore:
        """
        Check presence of required and important resume sections.

        Required sections (each = 15 pts): experience, education, skills, contact, summary
        Important sections (each = 5 pts): projects, certifications
        Max = 100 pts.
        """
        resume_lower = resume_text.lower()
        found_sections = []
        missing_sections = []

        points = 0.0

        for section_name, keywords in REQUIRED_SECTIONS.items():
            found = any(kw in resume_lower for kw in keywords)
            if found:
                found_sections.append(section_name)
                points += 15
            else:
                missing_sections.append(section_name)

        for section_name, keywords in IMPORTANT_SECTIONS.items():
            found = any(kw in resume_lower for kw in keywords)
            if found:
                found_sections.append(section_name)
                points += 5

        # Also check parsed data for completeness confirmation
        if resume_parsed.get("skills") and len(resume_parsed["skills"]) >= 5:
            points += 5
        if resume_parsed.get("experience"):
            points += 5

        score = round(min(points, 100.0), 2)

        return ComponentScore(
            score=score,
            weight=self.WEIGHTS["section_completeness"],
            weighted=round(score * self.WEIGHTS["section_completeness"], 2),
            details={
                "found_sections": found_sections,
                "missing_sections": missing_sections,
                "completeness_rate": f"{score:.0f}%",
            },
        )

    # ── Component 4: Skills Match ────────────────────────────────────────────

    def _score_skills_match(
        self,
        resume_parsed: dict,
        job_parsed: dict,
        resume_embedding: Optional[list],
        job_embedding: Optional[list],
    ) -> ComponentScore:
        """
        Score skills match using two methods:
        1. Direct string overlap (primary): resume skills vs. job required_skills
        2. Semantic similarity fallback: cosine similarity of embeddings

        Final score = 70% direct overlap + 30% semantic (if embeddings available)
        """
        resume_skills = {s.lower().strip() for s in resume_parsed.get("skills", [])}
        job_skills = {s.lower().strip() for s in job_parsed.get("required_skills", []) + job_parsed.get("tech_stack", [])}

        matched = []
        missing = []
        bonus = []

        # Direct matching
        if job_skills:
            for skill in job_skills:
                if skill in resume_skills:
                    matched.append(skill)
                else:
                    missing.append(skill)

            # Bonus skills: in resume but not required
            for skill in resume_skills:
                if skill not in job_skills:
                    bonus.append(skill)

            overlap_score = (len(matched) / len(job_skills)) * 100
        else:
            overlap_score = 50.0

        # Semantic similarity component (if embeddings provided)
        if resume_embedding and job_embedding:
            import numpy as np
            rv = np.array(resume_embedding).reshape(1, -1)
            jv = np.array(job_embedding).reshape(1, -1)
            sem_sim = float(cosine_similarity(rv, jv)[0][0])
            semantic_score = sem_sim * 100
            # Weighted combination: 70% direct + 30% semantic
            final_score = (overlap_score * 0.70) + (semantic_score * 0.30)
        else:
            final_score = overlap_score

        final_score = round(min(max(final_score, 0.0), 100.0), 2)

        return ComponentScore(
            score=final_score,
            weight=self.WEIGHTS["skills_match"],
            weighted=round(final_score * self.WEIGHTS["skills_match"], 2),
            details={
                "matched_skills": matched,
                "missing_skills": missing,
                "bonus_skills": bonus[:10],  # Limit bonus list
                "overlap_rate": f"{(len(matched) / max(len(job_skills), 1)) * 100:.1f}%",
            },
        )

    # ── Component 5: Experience Relevance ────────────────────────────────────

    def _score_experience_relevance(
        self,
        resume_parsed: dict,
        job_parsed: dict,
        resume_embedding: Optional[list],
        job_embedding: Optional[list],
    ) -> ComponentScore:
        """
        Score how relevant the candidate's experience is to the job requirements.

        Uses semantic similarity between resume embedding and job embedding as primary signal,
        with heuristic checks on years of experience as a secondary signal.
        """
        details = {}

        # Semantic similarity (primary)
        if resume_embedding and job_embedding:
            import numpy as np
            rv = np.array(resume_embedding).reshape(1, -1)
            jv = np.array(job_embedding).reshape(1, -1)
            cosine_sim = float(cosine_similarity(rv, jv)[0][0])
            semantic_score = cosine_sim * 100
            details["semantic_similarity"] = round(cosine_sim, 4)
        else:
            semantic_score = 50.0
            details["semantic_similarity"] = None

        # Years of experience heuristic
        required_years = job_parsed.get("required_experience_years", 0) or 0
        detected_years = self._estimate_experience_years(resume_parsed)
        details["years_detected"] = detected_years
        details["years_required"] = required_years

        if required_years > 0:
            years_ratio = min(detected_years / required_years, 1.5)
            years_score = min(years_ratio * 100, 100)
        else:
            years_score = 80.0  # Unknown requirement — neutral

        # Experience relevance note
        if detected_years >= required_years:
            details["relevance_notes"] = f"Candidate has {detected_years}+ years; role requires {required_years}+"
        else:
            details["relevance_notes"] = (
                f"Candidate appears to have ~{detected_years} years; role requires {required_years}+"
            )

        # Final: 80% semantic + 20% years heuristic
        final_score = (semantic_score * 0.80) + (years_score * 0.20)
        final_score = round(min(max(final_score, 0.0), 100.0), 2)

        return ComponentScore(
            score=final_score,
            weight=self.WEIGHTS["experience_relevance"],
            weighted=round(final_score * self.WEIGHTS["experience_relevance"], 2),
            details=details,
        )

    @staticmethod
    def _estimate_experience_years(resume_parsed: dict) -> float:
        """
        Estimate total years of experience from the experience list.
        Parses start/end dates if available; falls back to counting entries.
        """
        experience = resume_parsed.get("experience", [])
        if not experience:
            return 0.0

        # Simple heuristic: count number of roles × avg 2 years
        # A more robust approach would parse date ranges
        total_estimated = 0.0
        for exp in experience:
            duration_str = exp.get("duration", "") or ""
            # Try to extract years from duration strings like "2 years 3 months"
            years_match = re.search(r"(\d+)\s*year", duration_str, re.IGNORECASE)
            months_match = re.search(r"(\d+)\s*month", duration_str, re.IGNORECASE)

            if years_match:
                total_estimated += int(years_match.group(1))
                if months_match:
                    total_estimated += int(months_match.group(1)) / 12
            elif months_match:
                total_estimated += int(months_match.group(1)) / 12
            else:
                # Fallback: assume 1.5 years per experience entry
                total_estimated += 1.5

        return round(total_estimated, 1)

    # ── Report Builder ────────────────────────────────────────────────────────

    @staticmethod
    def _build_report(
        resume_text: str,
        resume_parsed: dict,
        job_parsed: dict,
        components: dict[str, ComponentScore],
    ) -> dict:
        """Assemble the full detailed report from all component details."""
        kw_details = components["keyword_match"].details
        fmt_details = components["formatting"].details
        sec_details = components["section_completeness"].details
        skl_details = components["skills_match"].details
        exp_details = components["experience_relevance"].details

        report = {
            # Keywords
            "matched_keywords": kw_details.get("matched_keywords", []),
            "missing_keywords": kw_details.get("missing_keywords", []),
            # Formatting
            "formatting_issues": fmt_details.get("formatting_issues", []),
            "formatting_positives": fmt_details.get("formatting_positives", []),
            # Sections
            "found_sections": sec_details.get("found_sections", []),
            "missing_sections": sec_details.get("missing_sections", []),
            # Skills
            "skill_match_details": {
                "matched": skl_details.get("matched_skills", []),
                "missing": skl_details.get("missing_skills", []),
                "bonus": skl_details.get("bonus_skills", []),
            },
            # Experience
            "experience_analysis": {
                "relevance_notes": exp_details.get("relevance_notes", ""),
                "years_detected": exp_details.get("years_detected"),
                "years_required": exp_details.get("years_required"),
                "semantic_similarity": exp_details.get("semantic_similarity"),
            },
            # Aggregated recommendations
            "recommendations": [],
            "strengths": [],
        }

        # Generate recommendations from component details
        if kw_details.get("missing_keywords"):
            top_missing = kw_details["missing_keywords"][:5]
            report["recommendations"].append(
                f"Add these missing keywords to your resume: {', '.join(top_missing)}"
            )
        if fmt_details.get("formatting_issues"):
            report["recommendations"].extend(fmt_details["formatting_issues"][:3])
        if sec_details.get("missing_sections"):
            report["recommendations"].append(
                f"Add these missing sections: {', '.join(sec_details['missing_sections'])}"
            )
        if skl_details.get("missing_skills"):
            top_skills = skl_details["missing_skills"][:5]
            report["recommendations"].append(
                f"Develop these required skills: {', '.join(top_skills)}"
            )

        # Strengths
        report["strengths"].extend(fmt_details.get("formatting_positives", []))
        if skl_details.get("matched_skills"):
            report["strengths"].append(
                f"Matches {len(skl_details['matched_skills'])} required skills: "
                + ", ".join(skl_details["matched_skills"][:5])
            )

        return report


# Module-level singleton
ats_scorer = ATSScorer()
