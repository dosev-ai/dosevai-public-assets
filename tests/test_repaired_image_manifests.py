from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_core import dump_manifest, load_mapping  # noqa: E402

REPAIRED_PACKAGES = (
    (
        "posts/publishing-workflow-is-live/cover.svg",
        "posts/publishing-workflow-is-live/cover.manifest.yaml",
    ),
    (
        "posts/design-first-ai-delivery-workflow/cover.svg",
        "posts/design-first-ai-delivery-workflow/cover.manifest.yaml",
    ),
    (
        "posts/excel-to-powerpoint-governed-workflow/cover.svg",
        "posts/excel-to-powerpoint-governed-workflow/cover.manifest.yaml",
    ),
    (
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-cover.svg",
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-cover.manifest.yaml",
    ),
    (
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-companion.pdf",
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-companion.manifest.yaml",
    ),
    (
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-companion.v0.1.pdf",
        "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-companion.v0.1.manifest.yaml",
    ),
)


class RepairedManifestTests(unittest.TestCase):
    def test_repaired_manifests_are_generator_stable_against_actual_assets(self) -> None:
        for asset_rel, manifest_rel in REPAIRED_PACKAGES:
            with self.subTest(asset=asset_rel), tempfile.TemporaryDirectory() as directory:
                asset = ROOT / asset_rel
                manifest = ROOT / manifest_rel
                metadata = load_mapping(manifest)
                metadata.pop("sha256", None)
                metadata_path = Path(directory) / "metadata.yaml"
                generated_path = Path(directory) / "generated.manifest.yaml"
                metadata_path.write_text(dump_manifest(metadata), encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "asset_manifest.py"),
                        "generate",
                        str(metadata_path),
                        "--output",
                        str(generated_path),
                        "--asset",
                        str(asset),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    cwd=ROOT,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    generated_path.read_text(encoding="utf-8"),
                    manifest.read_text(encoding="utf-8"),
                )

    def test_required_audit_has_no_temporary_migration_allowances(self) -> None:
        workflow = (ROOT / ".github/workflows/validate-governed-assets.yml").read_text(encoding="utf-8")
        self.assertNotIn("--allow-findings", workflow)
        self.assertNotIn("--allow-status", workflow)
        self.assertNotIn("--allow-manifest", workflow)


if __name__ == "__main__":
    unittest.main()
