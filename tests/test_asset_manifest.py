from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "asset_manifest.py"
LEGACY = """\
visual_id: test-visual-v1
repository: dosev-ai/dosevai-public-assets
path: posts/test/figure.svg
role: inline
target_content: {type: post, slug: 'post:test'}
alt_text: A safe test figure.
caption: A safe caption.
semantic_description: A semantic description.
claims: [One bounded claim.]
boundaries: [One explicit boundary.]
creation_method: deterministic SVG
rights: legacy prose rights
public_safety: approved-for-publication
external_resources: none
scripts: none
remote_fonts: none
guide_eligible: true
"""
SVG = '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc"><title id="title">Test</title><desc id="desc">Safe</desc><rect width="1" height="1"/></svg>'


class AssetManifestTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, capture_output=True, check=False)

    def normalize(self, legacy_text: str = LEGACY, svg_text: str = SVG) -> tuple[subprocess.CompletedProcess[str], Path, tempfile.TemporaryDirectory[str]]:
        directory = tempfile.TemporaryDirectory()
        temp = Path(directory.name)
        legacy = temp / "legacy.yaml"
        asset = temp / "figure.svg"
        output = temp / "figure.manifest.yaml"
        legacy.write_text(legacy_text, encoding="utf-8")
        asset.write_text(svg_text, encoding="utf-8")
        result = self.run_cli(
            "normalize", str(legacy), "--output", str(output), "--asset", str(asset),
            "--project", "personal-operating-system", "--contributor", "OpenAI ChatGPT with Delyan Dosev direction",
            "--sequence", "1",
        )
        return result, output, directory

    def test_normalize_and_validate(self) -> None:
        result, output, directory = self.normalize()
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(data["asset_id"], data["visual_id"])
        self.assertEqual(data["license"], "CC0-1.0")
        self.assertTrue(data["public_safe"])
        self.assertFalse(data["scripts"])
        self.assertIsInstance(data.get("created_at", ""), str)
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        validated = self.run_cli("validate", str(output), "--asset", str(Path(directory.name) / "figure.svg"))
        self.assertEqual(validated.returncode, 0, validated.stderr)

    def test_rejects_unknown_legacy_field(self) -> None:
        result, _, directory = self.normalize(LEGACY + "invented_field: true\n")
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("UNKNOWN_LEGACY_FIELDS", result.stderr)

    def test_rejects_script(self) -> None:
        result, _, directory = self.normalize(svg_text=SVG.replace("</svg>", "<script>alert(1)</script></svg>"))
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("SVG_ACTIVE_OR_FOREIGN_CONTENT", result.stderr)

    def test_rejects_external_css(self) -> None:
        unsafe = SVG.replace("</svg>", '<style>@import url("https://example.com/x.css")</style></svg>')
        result, _, directory = self.normalize(svg_text=unsafe)
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("SVG_CSS_IMPORT_FORBIDDEN", result.stderr)

    def test_rejects_duplicate_yaml_key(self) -> None:
        result, _, directory = self.normalize(LEGACY + "role: cover\n")
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID_YAML", result.stderr)

    def test_rejects_boolean_schema_version(self) -> None:
        result, output, directory = self.normalize()
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = output.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: true")
        output.write_text(text, encoding="utf-8")
        validated = self.run_cli("validate", str(output))
        self.assertEqual(validated.returncode, 2)
        self.assertIn("INVALID_FIELD_TYPE", validated.stderr)

    def test_rejects_encoded_external_style_url(self) -> None:
        unsafe = SVG.replace("<rect", '<rect style="fill:url(&quot;https://example.com/x.svg&quot;)"')
        result, _, directory = self.normalize(svg_text=unsafe)
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("SVG_EXTERNAL_CSS_URL_FORBIDDEN", result.stderr)

    def test_rejects_xinclude_namespace(self) -> None:
        unsafe = SVG.replace(
            "</svg>",
            '<fallback xmlns="http://www.w3.org/2001/XInclude"><rect width="1" height="1"/></fallback></svg>',
        )
        result, _, directory = self.normalize(svg_text=unsafe)
        self.addCleanup(directory.cleanup)
        self.assertEqual(result.returncode, 2)
        self.assertIn("SVG_XINCLUDE_FORBIDDEN", result.stderr)


if __name__ == "__main__":
    unittest.main()
