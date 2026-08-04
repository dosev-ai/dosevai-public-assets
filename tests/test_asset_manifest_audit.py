from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_audit import audit_repository  # noqa: E402

VALID_SVG = """<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-labelledby=\"title desc\"><title id=\"title\">Title</title><desc id=\"desc\">Description</desc><rect width=\"10\" height=\"10\"/></svg>"""


def manifest_text(*, asset_id: str = "sample", profile: str = "image", scripts: bool = False) -> str:
    return f"""schema_version: 1
profile: {profile}
asset_id: {asset_id}
visual_id: {asset_id}
content_id: post:sample
source_class: project_owned
project: test
source_repository: example/assets
source_path: posts/sample/cover.svg
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


class AuditTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        directory = tempfile.TemporaryDirectory()
        (Path(directory.name) / "posts" / "sample").mkdir(parents=True)
        return directory

    def test_valid_package_passes(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(manifest_text(), encoding="utf-8")
            report = audit_repository(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"], {"pass": 1})
            self.assertEqual(report["items"][0]["code"], "PACKAGE_VALID")

    def test_missing_and_orphan_are_distinct(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "unused.manifest.yaml").write_text(manifest_text(), encoding="utf-8")
            report = audit_repository(root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["summary"], {"missing_manifest": 1, "orphan_manifest": 1})

    def test_unsafe_manifest_is_classified(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(manifest_text(scripts=True), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "unsafe")
            self.assertEqual(report["items"][0]["code"], "UNSAFE_RESOURCE_FLAGS")

    def test_unsupported_profile_is_classified(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.manifest.yaml").write_text(manifest_text(profile="audio"), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["items"][0]["status"], "unsupported_profile")
            self.assertEqual(report["items"][0]["code"], "UNSUPPORTED_PROFILE")

    def test_alternate_extensions_fail_closed(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
            (package / "cover.png").write_bytes(b"not a real png")
            (package / "cover.manifest.yaml").write_text(manifest_text(), encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"repair": 1})
            self.assertEqual(report["items"][0]["code"], "AMBIGUOUS_ASSET_VARIANTS")
            self.assertEqual(len(report["items"][0]["assets"]), 2)

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
