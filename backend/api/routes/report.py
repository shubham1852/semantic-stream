"""
api/routes/report.py
====================
GET /api/v1/report/{session_id} — Generate and serve a PDF report for a
completed analysis session.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.services.report_service import ReportService

router = APIRouter()


@router.get("/report/{session_id}", summary="Download PDF report for a session")
async def download_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Generate (if not cached) and serve the PDF report for a session.

    Args:
        session_id: UUID of the analysis job (session).
        db: Injected async database session.

    Returns:
        PDF file response with Content-Disposition: attachment.
    """
    service = ReportService(db)
    pdf_path = await service.get_or_generate_report(session_id)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"semanticstream_report_{session_id[:8]}.pdf",
        headers={"Content-Disposition": f'attachment; filename="semanticstream_report_{session_id[:8]}.pdf"'},
    )
