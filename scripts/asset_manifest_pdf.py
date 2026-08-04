"""Fail-closed validation for governed public PDF assets."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _fail(code: str, message: str) -> None:
    raise PdfValidationError(code, message)


def _resolve(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _read_boundaries(path: Path) -> tuple[bytes, bytes]:
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 2048))
            trailer = handle.read()
    except FileNotFoundError:
        _fail("ASSET_NOT_FOUND", str(path))
    except OSError as exc:
        _fail("PDF_READ_FAILED", f"{path.name}: {exc}")
    return header, trailer


def validate_pdf(path: Path, *, expected_page_count: int) -> dict[str, Any]:
    header, trailer = _read_boundaries(path)
    if not header.startswith(b"%PDF-"):
        _fail("PDF_SIGNATURE_MISMATCH", path.name)
    if b"%%EOF" not in trailer:
        _fail("PDF_EOF_MARKER_MISSING", path.name)

    try:
        reader = PdfReader(path, strict=True)
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        _fail("PDF_PARSE_FAILED", f"{path.name}: {exc}")

    if reader.is_encrypted:
        _fail("PDF_ENCRYPTION_FORBIDDEN", path.name)

    try:
        page_count = len(reader.pages)
    except (PdfReadError, KeyError, TypeError, ValueError) as exc:
        _fail("PDF_PAGE_TREE_INVALID", f"{path.name}: {exc}")
    if page_count <= 0:
        _fail("PDF_PAGE_COUNT_INVALID", f"{path.name}: {page_count}")
    if page_count != expected_page_count:
        _fail("PDF_PAGE_COUNT_MISMATCH", f"{path.name}: {page_count} != {expected_page_count}")

    try:
        root = _resolve(reader.trailer["/Root"])
    except (KeyError, TypeError, ValueError) as exc:
        _fail("PDF_CATALOG_INVALID", f"{path.name}: {exc}")
    if not isinstance(root, dict):
        _fail("PDF_CATALOG_INVALID", path.name)

    if "/OpenAction" in root or "/AA" in root:
        _fail("PDF_ACTIVE_CONTENT_FORBIDDEN", "catalog OpenAction/AA")
    if "/AcroForm" in root:
        _fail("PDF_INTERACTIVE_FORM_FORBIDDEN", path.name)
    if "/AF" in root:
        _fail("PDF_EMBEDDED_OBJECTS_FORBIDDEN", "catalog associated files")

    names = _resolve(root.get("/Names"))
    if isinstance(names, dict):
        if "/JavaScript" in names:
            _fail("PDF_JAVASCRIPT_FORBIDDEN", "catalog names")
        if "/EmbeddedFiles" in names:
            _fail("PDF_EMBEDDED_OBJECTS_FORBIDDEN", "catalog embedded files")

    try:
        attachments = list(reader.attachment_list)
    except (PdfReadError, KeyError, TypeError, ValueError) as exc:
        _fail("PDF_ATTACHMENT_SCAN_FAILED", f"{path.name}: {exc}")
    if attachments:
        _fail("PDF_EMBEDDED_OBJECTS_FORBIDDEN", f"{len(attachments)} attachment(s)")

    for index, page in enumerate(reader.pages, start=1):
        page_obj = _resolve(page)
        if not isinstance(page_obj, dict):
            _fail("PDF_PAGE_TREE_INVALID", f"page {index}")
        if "/AA" in page_obj:
            _fail("PDF_ACTIVE_CONTENT_FORBIDDEN", f"page {index} additional actions")
        annots = _resolve(page_obj.get("/Annots"))
        if annots:
            _fail("PDF_ANNOTATIONS_FORBIDDEN", f"page {index}: {len(annots)} annotation(s)")

    return {
        "page_count": page_count,
        "encrypted": False,
        "attachments": 0,
        "annotations": 0,
    }
