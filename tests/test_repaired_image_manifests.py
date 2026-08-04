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
    "posts/publishing-workflow-is-live/cover",
    "posts/design-first-ai-delivery-workflow/cover",
    "posts/excel-to-powerpoint-governed-workflow/cover",
    "posts/governed-finance-agent-operating-model/governed-finance-agent-operating-model-cover",
)


class RepairedImageManifestTests(unittest.TestCase):
    def test_repaired_manifests_are_generator_stable_against_actual_assets(self) -> None:
        for package in REPAIRED_PACKAGES:
            with self.subTest(package=package), tempfile.TemporaryDirectory() as directory:
                stem = ROOT / package
                asset = stem.with_suffix(".svg")
                manifest = stem.parent / f"{stem.name}.manifest.yaml"
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


if __name__ == "__main__":
    unittest.main()
