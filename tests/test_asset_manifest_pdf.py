from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

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
semantic_description: An owner-attested document fixture.
claims:
- One bounded claim.
boundaries:
- Not production evidence.
- Document contents are reviewed by the owner, not parsed by the packager.
creation_method: Rendered and visually inspected by the owner.
public_safety_state: reviewed-public-safe
"""


class PdfManifestTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def workspace(self, asset_bytes: bytes = b"owner-attested-pdf-bytes") -> tuple[Path, Path, Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        legacy = root / "legacy.yaml"
        asset = root / "sample-companion.pdf"
        output = root / "sample-companion.manifest.yaml"
        legacy.write_text(LEGACY, encoding="utf-8")
        asset.write_bytes(asset_bytes)
        return legacy, asset, output

    def normalize(self, asset_bytes: bytes = b"owner-attested-pdf-bytes") -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        legacy, asset, output = self.workspace(asset_bytes)
        args = [
            "normalize", str(legacy), "--profile", "document_pdf", "--output", str(output),
            "--project", "personal-operating-system", "--contributor", "Delyan Dosev",
            "--content-id", "post:sample", "--source-repository", "example/assets",
            "--source-path", "posts/sample/sample-companion.pdf", "--render-inspected",
            "--private-notes-removed", "--render-evidence", "owner rendered and inspected",
            "--asset", str(asset),
        ]
        return self.run_cli(*args), output, asset

    def test_pdf_legacy_normalization_and_envelope_validation(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(data["profile"], "document_pdf")
        self.assertEqual(data["page_count"], 1)
        self.assertEqual(data["mime_type"], "application/pdf")
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(data["render_inspected"])
        self.assertTrue(data["private_notes_removed"])
        self.assertEqual(data["embedded_object_policy"], "forbid")
        self.assertEqual(self.run_cli("validate", str(output), "--asset", str(asset)).returncode, 0)

    def test_pdf_requires_explicit_render_and_note_attestations(self) -> None:
        legacy, asset, output = self.workspace()
        result = self.run_cli(
            "normalize", str(legacy), "--profile", "document_pdf", "--output", str(output),
            "--project", "personal-operating-system", "--contributor", "Delyan Dosev",
            "--content-id", "post:sample", "--source-repository", "example/assets",
            "--source-path", "posts/sample/sample-companion.pdf", "--render-evidence", "owner inspected",
            "--asset", str(asset),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("PDF_RENDER_INSPECTION_REQUIRED", result.stderr)

    def test_pdf_requires_sha256_binding(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        data.pop("sha256")
        output.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        checked = self.run_cli("validate", str(output), "--asset", str(asset))
        self.assertEqual(checked.returncode, 2)
        self.assertIn("MISSING_FIELD", checked.stderr)
        self.assertIn("sha256", checked.stderr)

    def test_pdf_rejects_checksum_mismatch(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        data["sha256"] = "0" * 64
        output.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        checked = self.run_cli("validate", str(output), "--asset", str(asset))
        self.assertEqual(checked.returncode, 2)
        self.assertIn("CHECKSUM_MISMATCH", checked.stderr)

    def test_pdf_contents_are_not_parsed_by_packager(self) -> None:
        arbitrary_document_bytes = (
            b"not a structurally valid PDF; may mention JavaScript, attachments, annotations, or encryption"
        )
        result, output, asset = self.normalize(arbitrary_document_bytes)
        self.assertEqual(result.returncode, 0, result.stderr)
        checked = self.run_cli("validate", str(output), "--asset", str(asset))
        self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
