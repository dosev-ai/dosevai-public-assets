from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "asset_manifest.py"
VALID_SVG = """<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-labelledby=\"title desc\"><title id=\"title\">Title</title><desc id=\"desc\">Description</desc><rect width=\"10\" height=\"10\"/></svg>"""


def manifest(source_path: str) -> str:
    return f"""schema_version: 1
profile: image
asset_id: cover
visual_id: cover
content_id: post:test
source_class: project_owned
project: test
source_repository: wrong/repository
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
scripts: false
remote_fonts: false
"""


class AuditAllowlistTests(unittest.TestCase):
    def write_package(self, root: Path, name: str) -> str:
        package = root / "posts" / name
        package.mkdir(parents=True)
        source_path = f"posts/{name}/cover.svg"
        (package / "cover.svg").write_text(VALID_SVG, encoding="utf-8")
        (package / "cover.manifest.yaml").write_text(manifest(source_path), encoding="utf-8")
        return f"posts/{name}/cover.manifest.yaml"

    def run_audit(self, root: Path, *allowed_manifests: str) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "audit",
            "--root",
            str(root),
            "--expected-repository",
            "expected/repository",
            "--allow-status",
            "repair",
        ]
        for path in allowed_manifests:
            command.extend(("--allow-manifest", path))
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def test_exact_manifest_and_status_can_be_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = self.write_package(root, "one")
            result = self.run_audit(root, allowed)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["gate_ok"])
            self.assertEqual(report["allowed_finding_count"], 1)
            self.assertEqual(report["blocking_finding_count"], 0)
            self.assertEqual(report["unused_allowed_manifests"], [])

    def test_unlisted_finding_with_same_status_remains_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = self.write_package(root, "one")
            self.write_package(root, "two")
            result = self.run_audit(root, allowed)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertFalse(report["gate_ok"])
            self.assertEqual(report["allowed_finding_count"], 1)
            self.assertEqual(report["blocking_finding_count"], 1)
            self.assertEqual(report["unused_allowed_manifests"], [])

    def test_stale_allowlist_entry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = self.write_package(root, "one")
            stale = "posts/missing/cover.manifest.yaml"
            result = self.run_audit(root, allowed, stale)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertFalse(report["gate_ok"])
            self.assertEqual(report["blocking_finding_count"], 0)
            self.assertEqual(report["unused_allowed_manifests"], [stale])
            self.assertEqual(report["allowlist_error_count"], 1)


if __name__ == "__main__":
    unittest.main()
