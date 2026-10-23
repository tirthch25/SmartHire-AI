"""
SmartHire AI — PDF Export Service (ReportLab)

Generates professional PDF reports for:
1. ATS Score Reports — includes score breakdown, charts, recommendations
2. Cover Letter PDFs — clean formatted letter

Uploads generated PDFs to AWS S3 and returns presigned download URLs.
"""

import io
from datetime import datetime
from typing import Optional

import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.blob_client import (
    build_cover_letter_key,
    build_report_key,
    generate_presigned_url,
    upload_bytes,
)

logger = structlog.get_logger(__name__)

# ── Color Palette ─────────────────────────────────────────────────────────────
PRIMARY = colors.HexColor("#1a56db")      # Deep blue
SUCCESS = colors.HexColor("#057a55")      # Green (good score)
WARNING = colors.HexColor("#c27803")      # Amber (medium score)
DANGER = colors.HexColor("#c81e1e")       # Red (low score)
MUTED = colors.HexColor("#6b7280")        # Gray
LIGHT_GRAY = colors.HexColor("#f3f4f6")
DARK = colors.HexColor("#111827")


def _score_color(score: float) -> colors.Color:
    """Return a color based on the score value."""
    if score >= 75:
        return SUCCESS
    elif score >= 50:
        return WARNING
    else:
        return DANGER


class PDFExportService:
    """
    ReportLab-based PDF report generator.

    Usage:
        svc = PDFExportService()
        url = svc.export_ats_report(analysis_data, user_id)
        url = svc.export_cover_letter(letter_content, user_id, letter_id)
    """

    def export_ats_report(
        self,
        analysis_data: dict,
        user_id: str,
    ) -> tuple[str, str]:
        """
        Generate an ATS score report PDF and upload to S3.

        Args:
            analysis_data: Full ATS analysis dict (from DB).
            user_id: Owner's user UUID.

        Returns:
            Tuple of (s3_key, presigned_download_url).
        """
        analysis_id = str(analysis_data.get("id", "report"))
        pdf_bytes = self._build_ats_report(analysis_data)

        s3_key = build_report_key(user_id, analysis_id)
        upload_bytes(pdf_bytes, s3_key, content_type="application/pdf")
        download_url = generate_presigned_url(s3_key)

        logger.info("ATS report PDF exported", s3_key=s3_key, user_id=user_id)
        return s3_key, download_url

    def export_cover_letter(
        self,
        content: str,
        user_id: str,
        letter_id: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Generate a cover letter PDF and upload to S3.

        Args:
            content: Plain text cover letter.
            user_id: Owner's user UUID.
            letter_id: Cover letter UUID.
            job_title: Optional job title for the header.
            company: Optional company name for the header.

        Returns:
            Tuple of (s3_key, presigned_download_url).
        """
        pdf_bytes = self._build_cover_letter_pdf(content, job_title, company)

        s3_key = build_cover_letter_key(user_id, letter_id)
        upload_bytes(pdf_bytes, s3_key, content_type="application/pdf")
        download_url = generate_presigned_url(s3_key)

        logger.info("Cover letter PDF exported", s3_key=s3_key, user_id=user_id)
        return s3_key, download_url

    # ── ATS Report Builder ────────────────────────────────────────────────────

    def _build_ats_report(self, data: dict) -> bytes:
        """Build the ATS report PDF as bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Header ────────────────────────────────────────────
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=20,
            textColor=PRIMARY,
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=MUTED,
            spaceAfter=16,
        )

        story.append(Paragraph("SmartHire AI — ATS Score Report", title_style))
        story.append(
            Paragraph(
                f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
                subtitle_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY))
        story.append(Spacer(1, 0.4 * cm))

        # ── Overall Score ─────────────────────────────────────
        overall = data.get("overall_score", 0)
        score_color = _score_color(overall)

        score_style = ParagraphStyle(
            "OverallScore",
            parent=styles["Normal"],
            fontSize=48,
            textColor=score_color,
            alignment=1,  # Center
            spaceAfter=4,
        )
        label_style = ParagraphStyle(
            "ScoreLabel",
            parent=styles["Normal"],
            fontSize=12,
            textColor=MUTED,
            alignment=1,
            spaceAfter=20,
        )

        story.append(Paragraph(f"{overall:.0f}", score_style))
        story.append(Paragraph("Overall ATS Score / 100", label_style))
        story.append(Spacer(1, 0.3 * cm))

        # ── Score Breakdown Table ─────────────────────────────
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=DARK,
            spaceBefore=12,
            spaceAfter=8,
        )
        story.append(Paragraph("Score Breakdown", section_style))

        components = data.get("components", {})
        component_labels = {
            "keyword_match": ("Keyword Match", "30%"),
            "formatting": ("Formatting Quality", "15%"),
            "section_completeness": ("Section Completeness", "15%"),
            "skills_match": ("Skills Match", "20%"),
            "experience_relevance": ("Experience Relevance", "20%"),
        }

        table_data = [["Component", "Weight", "Score", "Weighted Score"]]
        for key, (label, weight) in component_labels.items():
            comp = components.get(key, {})
            score = comp.get("score", data.get(f"{key.split('_')[0]}_score", 0))
            weighted = comp.get("weighted", score * float(weight.strip("%")) / 100)
            table_data.append([
                label,
                weight,
                f"{score:.1f}",
                f"{weighted:.1f}",
            ])

        table = Table(table_data, colWidths=[7 * cm, 2.5 * cm, 2.5 * cm, 3 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)

        # ── Detailed Report Sections ──────────────────────────
        report = data.get("detailed_report", {})
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=9,
            textColor=DARK,
            spaceAfter=4,
            leading=14,
        )

        def add_bullet_section(title: str, items: list, bullet_color=MUTED):
            if not items:
                return
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(title, section_style))
            for item in items[:10]:
                story.append(Paragraph(f"• {item}", body_style))

        add_bullet_section("Matched Keywords", report.get("matched_keywords", []), SUCCESS)
        add_bullet_section("Missing Keywords", report.get("missing_keywords", []), DANGER)
        add_bullet_section("Missing Sections", report.get("missing_sections", []), WARNING)
        add_bullet_section("Formatting Issues", report.get("formatting_issues", []), WARNING)
        add_bullet_section("Strengths", report.get("strengths", []), SUCCESS)
        add_bullet_section("Recommendations", report.get("recommendations", []), PRIMARY)

        # ── Skills Summary ────────────────────────────────────
        skill_details = report.get("skill_match_details", {})
        if skill_details:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Skills Analysis", section_style))

            skills_data = [["Matched Skills", "Missing Skills"]]
            matched = skill_details.get("matched", [])[:8]
            missing = skill_details.get("missing", [])[:8]
            max_rows = max(len(matched), len(missing), 1)
            for i in range(max_rows):
                skills_data.append([
                    matched[i] if i < len(matched) else "",
                    missing[i] if i < len(missing) else "",
                ])

            skills_table = Table(skills_data, colWidths=[7.5 * cm, 7.5 * cm])
            skills_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), SUCCESS),
                ("BACKGROUND", (1, 0), (1, 0), DANGER),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(skills_table)

        # ── Footer ────────────────────────────────────────────
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=MUTED,
            alignment=1,
            spaceBefore=8,
        )
        story.append(Paragraph("Generated by SmartHire AI · smarthire-ai.vercel.app", footer_style))

        doc.build(story)
        return buffer.getvalue()

    # ── Cover Letter PDF Builder ──────────────────────────────────────────────

    def _build_cover_letter_pdf(
        self,
        content: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
    ) -> bytes:
        """Build a clean cover letter PDF as bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=3 * cm,
            leftMargin=3 * cm,
            topMargin=3 * cm,
            bottomMargin=3 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # Header
        if job_title or company:
            header_text = " — ".join(filter(None, [job_title, company]))
            story.append(Paragraph(
                header_text,
                ParagraphStyle("Header", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=4),
            ))
            story.append(Paragraph(
                datetime.now().strftime("%B %d, %Y"),
                ParagraphStyle("Date", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=20),
            ))

        # Body
        body_style = ParagraphStyle(
            "LetterBody",
            parent=styles["Normal"],
            fontSize=11,
            leading=18,
            textColor=DARK,
            spaceAfter=12,
        )

        for paragraph in content.split("\n\n"):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), body_style))

        # Footer
        story.append(Spacer(1, 1 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        story.append(Paragraph(
            "Generated by SmartHire AI",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=MUTED, alignment=2, spaceBefore=8),
        ))

        doc.build(story)
        return buffer.getvalue()


# Module-level singleton
pdf_export_service = PDFExportService()
