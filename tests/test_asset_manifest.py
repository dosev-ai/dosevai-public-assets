from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

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

    def workspace(self, legacy_text: str = LEGACY, svg_text: str = SVG) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        temp = Path(directory.name)
        legacy, asset, output = temp / "legacy.yaml", temp / "figure.svg", temp / "figure.manifest.yaml"
        legacy.write_text(legacy_text, encoding="utf-8")
        asset.write_text(svg_text, encoding="utf-8")
        return directory, legacy, asset, output

    def normalize(self, legacy_text: str = LEGACY, svg_text: str = SVG, *, license_id: str | None = "CC0-1.0") -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        _, legacy, asset, output = self.workspace(legacy_text, svg_text)
        args = ["normalize", str(legacy), "--output", str(output), "--asset", str(asset), "--project", "personal-operating-system", "--contributor", "OpenAI ChatGPT with Delyan Dosev direction"]
        if license_id is not None:
            args += ["--license", license_id]
        args += ["--sequence", "1"]
        return self.run_cli(*args), output, asset

    def test_normalize_and_validate(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(data["asset_id"], data["visual_id"])
        self.assertEqual(data["license"], "CC0-1.0")
        self.assertTrue(data["public_safe"])
        self.assertFalse(data["scripts"])
        self.assertRegex(data["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.run_cli("validate", str(output), "--asset", str(asset)).returncode, 0)

    def test_legacy_normalization_boundaries(self) -> None:
        cases = [
            (LEGACY + "invented_field: true\n", "UNKNOWN_LEGACY_FIELDS", "CC0-1.0"),
            (LEGACY + "role: cover\n", "INVALID_YAML", "CC0-1.0"),
            (LEGACY + "1: value\n", "INVALID_YAML", "CC0-1.0"),
            (LEGACY, "LEGACY_LICENSE_MAPPING_REQUIRED", None),
        ]
        for source, code, license_id in cases:
            with self.subTest(code=code):
                result, _, _ = self.normalize(source, license_id=license_id)
                self.assertEqual(result.returncode, 2)
                self.assertIn(code, result.stderr)
        result, output, _ = self.normalize(LEGACY.replace("guide_eligible: true", 'guide_eligible: "false"'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(yaml.safe_load(output.read_text(encoding="utf-8"))["guide_eligible"])

    def test_schema_types_and_asset_requirement(self) -> None:
        result, output, asset = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        output.write_text(output.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: true"), encoding="utf-8")
        invalid = self.run_cli("validate", str(output), "--asset", str(asset))
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("INVALID_FIELD_TYPE", invalid.stderr)
        missing_asset = self.run_cli("validate", str(output))
        self.assertEqual(missing_asset.returncode, 2)
        self.assertIn("--asset", missing_asset.stderr)

    def test_svg_fail_closed_cases(self) -> None:
        cases = [
            (SVG.replace("</svg>", "<script>alert(1)</script></svg>"), "SVG_ACTIVE_OR_FOREIGN_CONTENT"),
            (SVG.replace("</svg>", '<style>@import url("https://example.com/x.css")</style></svg>'), "SVG_CSS_IMPORT_FORBIDDEN"),
            (SVG.replace("</svg>", '<style>@im&#x70;ort url(&#x68;ttps://example.com/x.css)</style></svg>'), "SVG_CSS_IMPORT_FORBIDDEN"),
            (SVG.replace("<rect", '<rect style="fill:url(&quot;https://example.com/x.svg&quot;)"'), "SVG_EXTERNAL_CSS_URL_FORBIDDEN"),
            (SVG.replace("<rect", r'<rect style="fill:url(\68 ttps://example.com/x.svg)"'), "SVG_EXTERNAL_CSS_URL_FORBIDDEN"),
            (SVG.replace("<rect", '<rect style="fill:url(image.png)"'), "SVG_EXTERNAL_CSS_URL_FORBIDDEN"),
            (SVG.replace("</svg>", '<use href="other.svg#thing"/></svg>'), "SVG_EXTERNAL_REFERENCE_FORBIDDEN"),
            (SVG.replace("</svg>", '<fallback xmlns="http://www.w3.org/2001/XInclude"><rect width="1" height="1"/></fallback></svg>'), "SVG_XINCLUDE_FORBIDDEN"),
            (SVG.replace('<title id="title">', '<title xmlns="" id="title">'), "SVG_FOREIGN_NAMESPACE_FORBIDDEN"),
            (SVG.replace('aria-labelledby="title desc"', 'aria-labelledby="shape-a shape-b"').replace('<rect ', '<rect id="shape-a" ').replace('</svg>', '<g id="shape-b"/></svg>'), "SVG_ARIA_TITLE_DESC_BINDING_REQUIRED"),
        ]
        for unsafe, code in cases:
            with self.subTest(code=code):
                result, _, _ = self.normalize(svg_text=unsafe)
                self.assertEqual(result.returncode, 2)
                self.assertIn(code, result.stderr)

    def test_image_format_and_decode_boundaries(self) -> None:
        cases = [
            (".html", "text/html", b"<script>alert(1)</script>", "UNSUPPORTED_IMAGE_FORMAT"),
            (".png", "image/png", b"\x89PNG\r\n\x1a\n", "IMAGE_DECODE_FAILED"),
            (".jpg", "image/jpeg", b"\xff\xd8\xff", "IMAGE_DECODE_FAILED"),
            (".webp", "image/webp", b"RIFF\x04\x00\x00\x00WEBP", "IMAGE_DECODE_FAILED"),
        ]
        for suffix, mime, payload_bytes, expected in cases:
            with self.subTest(suffix=suffix):
                result, output, _ = self.normalize()
                self.assertEqual(result.returncode, 0, result.stderr)
                data = yaml.safe_load(output.read_text(encoding="utf-8"))
                data.pop("sha256", None)
                data["source_path"], data["mime_type"] = f"posts/test/payload{suffix}", mime
                output.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                payload = output.parent / f"payload{suffix}"
                payload.write_bytes(payload_bytes)
                invalid = self.run_cli("validate", str(output), "--asset", str(payload))
                self.assertEqual(invalid.returncode, 2)
                self.assertIn(expected, invalid.stderr)

    def test_valid_raster_decodes(self) -> None:
        result, output, _ = self.normalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(output.read_text(encoding="utf-8"))
        payload = output.parent / "payload.png"
        Image.new("RGB", (2, 2), (255, 255, 255)).save(payload, format="PNG")
        data.pop("sha256", None)
        data["source_path"] = "posts/test/payload.png"
        data["mime_type"] = "image/png"
        output.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        valid = self.run_cli("validate", str(output), "--asset", str(payload))
        self.assertEqual(valid.returncode, 0, valid.stderr)


if __name__ == "__main__":
    unittest.main()
