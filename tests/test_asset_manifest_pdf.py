from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfWriter
from pypdf.annotations import FreeText

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "asset_manifest.py"

LEGACY = """schema_version: 1
asset_id: sample-companion
title: Sample companion
subtitle: A governed PDF
asset_type: public-safe-pdf-companion
source_format: governed-public-presentation
pages: 1
sha256: 0000000000000000000000000000000000000000000000000000000000000000
license: CC0-1.0
filename_policy: unversioned-current-companion
update_policy: replace through reviewed commit
alt_text: A one-page governed PDF.
caption: A sample public-safe PDF.
semantic_description: A structural validation fixture.
claims:
- One bounded claim.
boundaries:
- Not production evidence.
- The public PDF contains no speaker notes.
creation_method: Rendered and visually inspected.
public_safety_state: reviewed-public-safe
"""


class PdfManifestTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, capture_output=True, check=False)

    def workspace(self, writer: PdfWriter | None = None) -> tuple[Path, Path, Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        legacy = root / "legacy.yaml"
        asset = root / "sample-companion.pdf"
        output = root / "sample-companion.manifest.yaml"
        legacy.write_text(LEGACY, encoding="utf-8")
        if writer is None:
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
        with asset.open("wb") as handle:
            writer.write(handle)
        return legacy, asset, output

    def normalize(self, writer: PdfWriter | None = None) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        legacy, asset, output = self.workspace(writer)
        args = [
            "normalize", str(legacy), "--profile", "document_pdf", "--output", str(output),
            "--project", "personal-operating-system", "--contributor", "Delyan Dosev",
            "--content-id", "post:sample", "--source-repository", "example/assets",
            "--source-path", "posts/sample/sample-companion.pdf", "--render-inspected",
            "--private-notes-removed", "--render-evidence", "rendered with pdfium and inspected",
            "--asset", str(asset),
        ]
        return self.run_cli(*args), output, asset

    def test_pdf_legacy_normalization_and_validation(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "document_pdf")
        self.assertEqual(data["page_count"], 1)
        self.assertEqual(data["mime_type"], "application/pdf")
        self.assertTrue(data["render_inspected"])
        self.assertTrue(data["private_notes_removed"])
        self.assertEqual(data["embedded_object_policy"], "forbid")
        self.assertEqual(self.run_cli("validate", str(output), "--asset", str(asset)).returncode, 0)

    def test_pdf_requires_explicit_render_and_note_evidence(self) -> None:
        legacy, asset, output = self.workspace()
        result = self.run_cli(
            "normalize", str(legacy), "--profile", "document_pdf", "--output", str(output),
            "--project", "personal-operating-system", "--contributor", "Delyan Dosev",
            "--content-id", "post:sample", "--source-repository", "example/assets",
            "--source-path", "posts/sample/sample-companion.pdf", "--render-evidence", "inspected",
            "--asset", str(asset),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("PDF_RENDER_INSPECTION_REQUIRED", result.stderr)

    def assert_rejected(self, writer: PdfWriter, code: str) -> None:
        result, _, _ = self.normalize(writer)
        self.assertEqual(result.returncode, 2)
        self.assertIn(code, result.stderr)

    def test_pdf_rejects_page_count_mismatch(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_blank_page(width=100, height=100)
        self.assert_rejected(writer, "PDF_PAGE_COUNT_MISMATCH")

    def test_pdf_rejects_encryption(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret")
        self.assert_rejected(writer, "PDF_ENCRYPTION_FORBIDDEN")

    def test_pdf_rejects_attachments_javascript_and_annotations(self) -> None:
        attachment = PdfWriter()
        attachment.add_blank_page(width=100, height=100)
        attachment.add_attachment("x.txt", b"secret")
        javascript = PdfWriter()
        javascript.add_blank_page(width=100, height=100)
        javascript.add_js("app.alert('x')")
        annotation = PdfWriter()
        annotation.add_blank_page(width=100, height=100)
        annotation.add_annotation(0, FreeText(text="private", rect=(10, 10, 50, 50)))
        for writer, code in (
            (attachment, "PDF_EMBEDDED_OBJECTS_FORBIDDEN"),
            (javascript, "PDF_JAVASCRIPT_FORBIDDEN"),
            (annotation, "PDF_ANNOTATIONS_FORBIDDEN"),
        ):
            with self.subTest(code=code):
                self.assert_rejected(writer, code)

    def test_pdf_rejects_malformed_file(self) -> None:
        legacy, asset, output = self.workspace()
        asset.write_bytes(b"%PDF-1.7\nnot a pdf\n%%EOF\n")
        result = self.run_cli(
            "normalize", str(legacy), "--profile", "document_pdf", "--output", str(output),
            "--project", "personal-operating-system", "--contributor", "Delyan Dosev",
            "--content-id", "post:sample", "--source-repository", "example/assets",
            "--source-path", "posts/sample/sample-companion.pdf", "--render-inspected",
            "--private-notes-removed", "--render-evidence", "inspected", "--asset", str(asset),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("PDF_PARSE_FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
