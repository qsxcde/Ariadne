from typing import Protocol

from pydantic import BaseModel, Field

from backend.rag.ingestion.document_ir import BBoxUnit


class RawParserResult(BaseModel):
    markdown: str
    page_count: int
    pages: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    source_parser: str | None = None
    warnings: list[str] = Field(default_factory=list)
    # Coordinate system of every bbox in ``pages``. Cloud content_list is
    # normalized to 0-1000; pypdf reports PDF points.
    bbox_unit: BBoxUnit = "points"


class ParserBackend(Protocol):
    name: str
    version: str

    def parse(self, pdf_bytes: bytes, filename: str | None = None) -> RawParserResult:
        """Parse PDF bytes into raw text and layout data."""
