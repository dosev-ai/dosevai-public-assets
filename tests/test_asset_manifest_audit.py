from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_audit import audit_repository  # noqa: E402

VALID_SVG = """<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-labelledby=\"title desc\"><title id=\"title\">Title</title><desc id=\"desc\">Description</desc><rect width=\"10\" height=\"10\"/></svg>"""


def image_manifest(
    *,
    asset_id: str = "sample",
    profile: str = "image",
    scripts: bool = False,
    source_path: str = "posts/sample/cover.svg",
) -> str:
    return f"""schema_version: 1
profile: {profile}
asset_id: {asset_id}
visual_id: {asset_id}
content_id: post:sample
source_class: project_owned
project: test
source_repository: example/assets
source_path: {source_path}
mime_type: image/svg+xml
role: explanatory_cover
alt: Sample alt
caption: Sample caption
semantic_description: Sample semantic description
claims:
- Sample claim
boundaries:
- Sample boundary
creation_method: test fixture
contributor: test
license: CC0-1.0
public_safe: true
guide_eligible: true
external_resources: false
scripts: {str(scripts).lower()}
remote_fonts: false
"""


def pdf_manifest(*, source_path: str = "posts/sample/companion.pdf", pages: int = 1) -> str:
    return f"""schema_version: 1
profile: document_pdf
asset_id: sample-companion
content_id: post:sample
source_class: project_owned
project: test
source_repository: example/assets
source_path: {source_path}
mime_type: application/pdf
role: document_companion
alt: Sample PDF alt
caption: Sample PDF caption
semantic_description: Sample PDF semantic description
claims:
- Sample PDF claim
boundaries:
- Sample PDF boundary
creation_method: test fixture
contributor: test
license: CC0-1.0
public_safe: true
guide_eligible: false
external_resources: false
scripts: false
page_count: {pages}
source_format: governed-public-presentation
render_inspected: true
render_evidence: rendered with pdfium and inspected
private_notes_removed: true
embedded_object_policy: forbid
annotation_policy: forbid
"""


def write_pdf(path: Path, *, attachment: bool = False) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if attachment:
        writer.add_attachment("private.txt", b"secret")
    with path.open("wb") as handle:
        writer.write(handle)


class AuditTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        directory = tempfile.TemporaryDirectory()
        (Path(directory.name) / "posts" / "sample").mkdir(parents=True)
        return directory

    def test_valid_image_package_passes(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(image_manifest(), encoding="utf-8")
            report = audit_repository(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"], {"pass": 1})
            self.assertEqual(report["items"][0]["code"], "PACKAGE_VALID")
            self.assertRegex(report["items"][0]["asset_evidence"][0]["sha256"], r"^[0-9a-f]{64}$")

    def test_valid_pdf_package_passes(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            write_pdf(package / "companion.pdf")
            (package / "companion.manifest.yaml").write_text(pdf_manifest(), encoding="utf-8")
            report = audit_repository(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"], {"pass": 1})
            self.assertEqual(report["items"][0]["profile"], "document_pdf")
            self.assertEqual(report["items"][0]["page_count"], 1)

    def test_expected_repository_must_match_manifest(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(image_manifest(), encoding="utf-8")
            report = audit_repository(root, expected_repository="other/repository")
            self.assertEqual(report["items"][0]["status"], "repair")
            self.assertEqual(report["items"][0]["code"], "SOURCE_REPOSITORY_MISMATCH")

    def test_source_path_must_match_actual_repository_path(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(
                image_manifest(source_path="posts/other/cover.svg"), encoding="utf-8"
            )
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "repair")
            self.assertEqual(report["items"][0]["code"], "ASSET_SOURCE_PATH_MISMATCH")

    def test_missing_and_orphan_are_distinct(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "unused.manifest.yaml").write_text(image_manifest(), encoding="utf-8")
            report = audit_repository(root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["summary"], {"missing_manifest": 1, "orphan_manifest": 1})

    def test_inactive_pptx_is_not_called_orphan(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "companion.pptx").write_bytes(b"not a presentation")
            (package / "companion.manifest.yaml").write_text("profile: presentation_pptx\n", encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsupported_profile": 1})
            self.assertEqual(report["items"][0]["code"], "UNSUPPORTED_ASSET_FORMAT")

    def test_unsafe_image_manifest_is_classified(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(image_manifest(scripts=True), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "unsafe")
            self.assertEqual(report["items"][0]["code"], "UNSAFE_RESOURCE_FLAGS")

    def test_pdf_attachment_is_unsafe(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            write_pdf(package / "companion.pdf", attachment=True)
            (package / "companion.manifest.yaml").write_text(pdf_manifest(), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "unsafe")
            self.assertEqual(report["items"][0]["code"], "PDF_EMBEDDED_OBJECTS_FORBIDDEN")

    def test_symlinked_package_member_is_unsafe(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            target = root / "outside.svg"
            target.write_text(VALID_SVG, encoding="utf-8")
            try:
                (package / "cover.svg").symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsafe": 1})
            self.assertEqual(report["items"][0]["code"], "SYMLINK_FORBIDDEN")

    def test_unsupported_profile_is_classified(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(image_manifest(profile="audio"), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "unsupported_profile")
            self.assertEqual(report["items"][0]["code"], "UNSUPPORTED_PROFILE")

    def test_alternate_extensions_fail_closed(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.png").write_bytes(b"not a real png")
            (package / "cover.manifest.yaml").write_text(image_manifest(), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"repair": 1})
            self.assertEqual(report["items"][0]["code"], "AMBIGUOUS_ASSET_VARIANTS")
            self.assertEqual(len(report["items"][0]["assets"]), 2)

    def test_duplicate_include_roots_do_not_duplicate_packages(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(image_manifest(), encoding="utf-8")
            report = audit_repository(root, ["posts", "posts"])
            self.assertEqual(report["package_count"], 1)
            self.assertEqual(report["summary"], {"pass": 1})

    def test_empty_selected_root_fails_closed(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            report = audit_repository(root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["items"][0]["code"], "NO_ASSET_PACKAGES")

    def test_cli_can_allow_only_inactive_profiles(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "companion.pptx").write_bytes(b"not a presentation")
            (package / "companion.manifest.yaml").write_text("profile: presentation_pptx\n", encoding="utf-8")
            command = [
                sys.executable, str(SCRIPTS / "asset_manifest.py"), "audit",
                "--root", str(root),
                "--allow-status", "unsupported_profile",
                "--allow-manifest", "posts/sample/companion.manifest.yaml",
            ]
            allowed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            report = json.loads(allowed.stdout)
            self.assertTrue(report["gate_ok"])
            self.assertEqual(report["blocking_finding_count"], 0)
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            blocked = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(blocked.returncode, 2)
            report = json.loads(blocked.stdout)
            self.assertFalse(report["gate_ok"])
            self.assertEqual(report["blocking_finding_count"], 1)

    def test_cli_fails_on_findings_and_can_emit_report(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            output = root / "audit.json"
            command = [sys.executable, str(SCRIPTS / "asset_manifest.py"), "audit", "--root", str(root), "--output", str(output)]
            failed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(failed.returncode, 2)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"], {"missing_manifest": 1})
            allowed = subprocess.run([*command, "--allow-findings"], text=True, capture_output=True, check=False)
            self.assertEqual(allowed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
