from __future__ import annotations

from typing import Literal

from axiom_extractors import ExtractedDocument
from pydantic import BaseModel, Field


ExportFormatLiteral = Literal["json", "csv", "markdown", "html", "zip"]


class ExportDownloadRequest(BaseModel):
    """Body for `POST /exports/download`: an `ExtractedDocument` plus target format."""

    format: ExportFormatLiteral = Field(description="Output encoding.")
    document: ExtractedDocument = Field(description="Normalized extraction payload.")
