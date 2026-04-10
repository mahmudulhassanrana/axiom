from __future__ import annotations

import json
from uuid import UUID

from axiom_extractors import ExtractedDocument
from axiom_exporters import ExportFormat, export_bytes
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.db.models.extracted_data import ExtractedData
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.db.models.user import User
from axiom_api.core.public_messages import client_safe_detail
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.export import ExportDownloadRequest, ExportFormatLiteral

router = APIRouter(prefix="/exports", tags=["exports"])


def _attachment_response(doc: ExtractedDocument, fmt: ExportFormat) -> Response:
    body, media_type, ext = export_bytes(doc, fmt)
    filename = f"export.{ext}"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/download")
async def export_download_post(
    body: ExportDownloadRequest,
    _user: User = Depends(get_current_user_bearer),
) -> Response:
    """Export a provided extraction payload (JSON body) as a downloadable file."""
    return _attachment_response(body.document, body.format)


@router.get("/download")
async def export_download_get(
    fmt: ExportFormatLiteral = Query(
        ...,
        alias="format",
        description="json | csv | markdown | html | zip",
    ),
    document_json: str = Query(
        ...,
        description="JSON string of an ExtractedDocument (URL-encoded). Prefer POST for large bodies.",
    ),
    _user: User = Depends(get_current_user_bearer),
) -> Response:
    """Export using query parameters (handy for quick tests); large documents should use POST instead."""
    try:
        raw = json.loads(document_json)
        doc = ExtractedDocument.model_validate(raw)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=client_safe_detail(
                code="invalid_document_json",
                production_message="The document_json parameter is not valid JSON or schema.",
                developer_message=f"Invalid document_json: {exc}",
            ),
        ) from exc
    return _attachment_response(doc, fmt)


@router.get("/runs/{run_id}/download")
async def export_run_download(
    run_id: UUID,
    fmt: ExportFormatLiteral = Query(
        ...,
        alias="format",
        description="json | csv | markdown | html | zip",
    ),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_bearer),
) -> Response:
    """Download persisted extraction for a run (first `extracted_data` row for that run)."""
    stmt = (
        select(ExtractedData)
        .join(Run, ExtractedData.run_id == Run.id)
        .join(Job, Run.job_id == Job.id)
        .where(Run.id == run_id, Job.organization_id == user.organization_id)
        .order_by(ExtractedData.created_at.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No extracted data for this run")
    try:
        doc = ExtractedDocument.model_validate(row.payload)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=client_safe_detail(
                code="invalid_stored_document",
                production_message="Stored extraction data could not be read.",
                developer_message=f"Stored payload is not a valid ExtractedDocument: {exc}",
            ),
        ) from exc
    return _attachment_response(doc, fmt)
