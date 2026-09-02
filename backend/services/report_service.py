"""
services/report_service.py
==========================
Generates PDF reports for completed SemanticStream analysis sessions.

Uses ReportLab to produce a structured PDF containing:
  - Session metadata (job ID, video name, date)
  - Summary metrics table (SSIM, PSNR, bitrate, SEES score)
  - Per-tier quality breakdown
  - Bandwidth profile information

Reports are cached on disk in storage/reports/ and served directly
by the GET /api/v1/report/{session_id} endpoint.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from backend.core.exceptions import ReportGenerationError
from backend.core.logging_config import get_logger
from backend.database import crud

logger = get_logger(__name__)

REPORTS_DIR = Path("storage/reports")

# ── Colour palette matching the SemanticStream design system ──────────────────
COLOR_ACCENT     = colors.HexColor("#4F46E5")
COLOR_BG         = colors.HexColor("#0A0E1A")
COLOR_CARD       = colors.HexColor("#151C34")
COLOR_GREEN      = colors.HexColor("#00FF87")
COLOR_AMBER      = colors.HexColor("#F59E0B")
COLOR_MUTED      = colors.HexColor("#8892A4")
COLOR_TEXT       = colors.HexColor("#F0F0FF")
COLOR_TIER_P1    = colors.HexColor("#00FF87")
COLOR_TIER_P2    = colors.HexColor("#4ADE80")
COLOR_TIER_P3    = colors.HexColor("#F59E0B")
COLOR_TIER_P4    = colors.HexColor("#818CF8")
COLOR_TIER_P5    = colors.HexColor("#EF4444")

TIER_COLORS = {
    "P1": COLOR_TIER_P1,
    "P2": COLOR_TIER_P2,
    "P3": COLOR_TIER_P3,
    "P4": COLOR_TIER_P4,
    "P5": COLOR_TIER_P5,
}

QP_VALUES = {"P1": 18, "P2": 22, "P3": 26, "P4": 32, "P5": 40}
TIER_LABELS = {
    "P1": "Face / Person",
    "P2": "Text / UI",
    "P3": "Motion",
    "P4": "Object",
    "P5": "Background",
}


class ReportService:
    """Generates and caches PDF reports for completed analysis sessions.

    Args:
        db: Async database session injected by FastAPI.
    """

    def __init__(self, db) -> None:
        self._db = db

    async def get_or_generate_report(self, session_id: str) -> str:
        """Return the path to the PDF report, generating it if not cached.

        Args:
            session_id: UUID of the analysis job / session.

        Returns:
            Absolute path to the generated PDF file.

        Raises:
            ReportGenerationError: If the job does not exist or PDF generation fails.
        """
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = REPORTS_DIR / f"report_{session_id}.pdf"

        # Serve cached copy if available
        if pdf_path.exists():
            logger.info("report.cache_hit", session_id=session_id)
            return str(pdf_path)

        # Fetch job and video data
        job = await crud.get_analysis_job(self._db, session_id)
        if job is None:
            raise ReportGenerationError(f"Analysis job '{session_id}' not found.")

        video = await crud.get_video(self._db, job.video_id) if job.video_id else None

        # Build PDF
        try:
            self._build_pdf(pdf_path, job, video)
        except Exception as exc:
            logger.exception("report.generation_error", session_id=session_id)
            raise ReportGenerationError(f"Failed to generate report: {exc}") from exc

        logger.info("report.generated", session_id=session_id, path=str(pdf_path))
        return str(pdf_path)

    # ── PDF builder ───────────────────────────────────────────────────────────

    def _build_pdf(self, path: Path, job: Any, video: Any) -> None:
        """Construct the ReportLab PDF document.

        Args:
            path: Destination path for the PDF file.
            job:  AnalysisJob ORM object.
            video: Video ORM object (may be None).
        """
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Title ──────────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "SSTitle",
            parent=styles["Title"],
            textColor=COLOR_ACCENT,
            fontSize=22,
            spaceAfter=4,
            alignment=TA_CENTER,
        )
        sub_style = ParagraphStyle(
            "SSSub",
            parent=styles["Normal"],
            textColor=COLOR_MUTED,
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=16,
        )

        story.append(Paragraph("SemanticStream", title_style))
        story.append(Paragraph("Semantic-Aware Adaptive Video Analysis Report", sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_ACCENT))
        story.append(Spacer(1, 0.4 * cm))

        # ── Session info ───────────────────────────────────────────────────
        section_style = ParagraphStyle(
            "SSSection",
            parent=styles["Heading2"],
            textColor=COLOR_TEXT,
            fontSize=13,
            spaceBefore=12,
            spaceAfter=6,
        )
        normal_style = ParagraphStyle(
            "SSNormal",
            parent=styles["Normal"],
            textColor=COLOR_MUTED,
            fontSize=10,
            spaceAfter=4,
        )

        story.append(Paragraph("Session Details", section_style))

        session_data = [
            ["Job ID", str(job.id)],
            ["Video", video.filename if video else "—"],
            ["Status", str(job.status).upper()],
            ["Started", _fmt_dt(job.started_at)],
            ["Completed", _fmt_dt(job.completed_at)],
            ["Frame Sample Rate", f"every {job.frame_sample_rate} frames"],
            ["Confidence Threshold", f"{job.confidence_threshold:.2f}"],
            ["Bandwidth Profile", job.bandwidth_profile or "None"],
            ["Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
        ]

        story.append(_two_col_table(session_data))
        story.append(Spacer(1, 0.4 * cm))

        # ── Aggregate metrics ──────────────────────────────────────────────
        story.append(Paragraph("Summary Metrics", section_style))

        metrics_data = [
            ["Metric", "Value", "Description"],
            ["Avg SSIM", _fmt(job.avg_ssim, 4), "Structural Similarity (0–1, higher is better)"],
            ["Avg SPQI", _fmt(job.avg_spqi, 2), "Semantic Perceptual Quality Index"],
            ["Avg Bitrate", _fmt_bitrate(job.avg_bitrate_kbps), "Average encoded bitrate"],
            ["SEES Score", _fmt(job.sees_score, 4), "Semantic Encoding Efficiency Score"],
            ["Bitrate Reduction", _fmt_pct(job.bitrate_reduction_pct), "vs. Uniform ABR baseline"],
        ]

        story.append(_metrics_table(metrics_data))
        story.append(Spacer(1, 0.4 * cm))

        # ── Priority tier legend ───────────────────────────────────────────
        story.append(Paragraph("Priority Tier QP Assignments", section_style))
        story.append(
            Paragraph(
                "SemanticStream dynamically assigns quantization parameters (QP) based on "
                "semantic content. Lower QP = higher quality.",
                normal_style,
            )
        )
        story.append(Spacer(1, 0.2 * cm))

        tier_data = [["Tier", "Content Type", "QP Value", "Quality Level"]]
        tier_quality = {
            "P1": "Highest (lossless-like)",
            "P2": "Very High",
            "P3": "Medium",
            "P4": "Standard",
            "P5": "Lowest (aggressive compression)",
        }
        for tier, label in TIER_LABELS.items():
            tier_data.append([tier, label, str(QP_VALUES[tier]), tier_quality[tier]])

        story.append(_tier_table(tier_data))
        story.append(Spacer(1, 0.6 * cm))

        # ── Footer ─────────────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_MUTED))
        story.append(Spacer(1, 0.2 * cm))
        story.append(
            Paragraph(
                f"Report generated by SemanticStream v1.0.0 · {datetime.utcnow().strftime('%Y-%m-%d')}",
                ParagraphStyle(
                    "Footer", parent=styles["Normal"],
                    textColor=COLOR_MUTED, fontSize=8, alignment=TA_CENTER
                ),
            )
        )

        doc.build(story)


# ── Table helpers ──────────────────────────────────────────────────────────────

def _two_col_table(data: list[list[str]]) -> Table:
    tbl = Table(data, colWidths=[5 * cm, 11 * cm])
    tbl.setStyle(TableStyle([
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1), COLOR_MUTED),
        ("TEXTCOLOR",   (1, 0), (1, -1), COLOR_TEXT),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#0F1426"), colors.HexColor("#151C34")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#1E2A4A")),
    ]))
    return tbl


def _metrics_table(data: list[list[str]]) -> Table:
    tbl = Table(data, colWidths=[4.5 * cm, 3.5 * cm, 9 * cm])
    tbl.setStyle(TableStyle([
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR",   (0, 0), (-1, 0), COLOR_TEXT),
        ("BACKGROUND",  (0, 0), (-1, 0), COLOR_ACCENT),
        ("TEXTCOLOR",   (0, 1), (0, -1), COLOR_MUTED),
        ("TEXTCOLOR",   (1, 1), (1, -1), COLOR_GREEN),
        ("FONTNAME",    (1, 1), (1, -1), "Courier"),
        ("TEXTCOLOR",   (2, 1), (2, -1), COLOR_MUTED),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0F1426"), colors.HexColor("#151C34")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#1E2A4A")),
    ]))
    return tbl


def _tier_table(data: list[list[str]]) -> Table:
    tbl = Table(data, colWidths=[1.8 * cm, 4.5 * cm, 2.5 * cm, 8.2 * cm])
    style = [
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR",   (0, 0), (-1, 0), COLOR_TEXT),
        ("BACKGROUND",  (0, 0), (-1, 0), COLOR_CARD),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#1E2A4A")),
    ]
    tiers = ["P1", "P2", "P3", "P4", "P5"]
    for i, tier in enumerate(tiers, start=1):
        c = TIER_COLORS.get(tier, COLOR_MUTED)
        style.append(("TEXTCOLOR", (0, i), (0, i), c))
        style.append(("FONTNAME",  (0, i), (0, i), "Helvetica-Bold"))
        style.append(("TEXTCOLOR", (1, i), (3, i), COLOR_TEXT))
        bg = colors.HexColor("#0F1426") if i % 2 == 1 else colors.HexColor("#151C34")
        style.append(("BACKGROUND", (0, i), (-1, i), bg))
    tbl.setStyle(TableStyle(style))
    return tbl


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _fmt(value, decimals: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{decimals}f}"


def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}%"


def _fmt_bitrate(kbps) -> str:
    if kbps is None:
        return "—"
    mbps = float(kbps) / 1000
    return f"{mbps:.2f} Mbps"
