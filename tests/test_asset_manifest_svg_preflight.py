from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "asset_manifest_svg_preflight.py"
sys.path.insert(0, str(ROOT / "scripts"))

from asset_manifest_svg_preflight import resolve_evidence_path  # noqa: E402

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
<title id="title">Fallback preview test</title><desc id="desc">Safe governed SVG.</desc>
<rect width="1600" height="900" fill="#ffffff"/><text x="50" y="100" font-family="system-ui,sans-serif" font-size="48" font-weight="700">Fallback text</text></svg>'''


def manifest_data(asset: Path, source_path: str | None = None, asset_id: str = "test.svg-preflight") -> dict:
    return {
        "schema_version": 1,
        "profile": "image",
        "asset_id": asset_id,
        "visual_id": asset_id,
        "content_id": "post:test",
        "source_class": "project_owned",
        "project": "personal-web-presence",
        "source_repository": "dosev-ai/dosevai-public-assets",
        "source_path": source_path or f"fixtures/{asset.name}",
        "mime_type": "image/svg+xml",
        "sha256": "0" * 64,
        "role": "explanatory_inline",
        "alt": "Fallback preview test.",
        "caption": "Fallback preview test.",
        "semantic_description": "Tests fallback-font preview generation and exact-byte manifest refresh.",
        "claims": ["The helper renders three preview widths."],
        "boundaries": ["Preview generation is not publication approval."],
        "creation_method": "test fixture",
        "contributor": "test",
        "license": "CC0-1.0",
        "public_safe": True,
        "guide_eligible": False,
        "external_resources": False,
        "scripts": False,
        "remote_fonts": False,
    }


class SvgPreflightTests(unittest.TestCase):
    def run_preflight(self, svgs: list[Path], output_dir: Path, report: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *(str(svg) for svg in svgs),
                "--output-dir",
                str(output_dir),
                "--report",
                str(report),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_relative_evidence_paths_are_anchored_to_repository_root(self) -> None:
        relative = Path(".preflight/svg")
        self.assertEqual(resolve_evidence_path(relative), ROOT / relative)
        with tempfile.TemporaryDirectory() as directory:
            absolute = Path(directory).resolve()
            self.assertEqual(resolve_evidence_path(absolute), absolute)

    def test_refreshes_manifest_and_renders_fallback_preview_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            svg = root / "fixture.svg"
            manifest = root / "fixture.manifest.yaml"
            output_dir = root / "previews"
            report = root / "report.json"
            svg.write_text(SVG, encoding="utf-8")
            manifest.write_text(yaml.safe_dump(manifest_data(svg), sort_keys=False), encoding="utf-8")

            completed = self.run_preflight([svg], output_dir, report)
            self.assertEqual(completed.returncode, 0, completed.stderr)

            refreshed = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            self.assertEqual(refreshed["sha256"], hashlib.sha256(svg.read_bytes()).hexdigest())

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(completed.stdout), payload)
            self.assertTrue(payload["ok"])
            result = payload["results"][0]
            self.assertTrue(result["inspection_required"])
            self.assertTrue(result["package_refreshed_from_exact_bytes"])
            self.assertEqual(result["font_profile"], "DejaVu Sans")
            self.assertEqual(len(result["previews"]), 3)
            self.assertIn("full artifact again", " ".join(result["inspection_scope"]))

            expected = [("full", 1600, 900), ("card", 800, 450), ("mobile", 480, 270)]
            for label, width, height in expected:
                path = Path(next(item["path"] for item in result["previews"] if item["label"] == label))
                self.assertTrue(path.is_file())
                with Image.open(path) as image:
                    self.assertEqual(image.size, (width, height))

    def test_preview_paths_are_unique_for_same_parent_name_and_stem(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "posts" / "foo" / "cover.svg"
            second = root / "diagrams" / "foo" / "cover.svg"
            for svg in (first, second):
                svg.parent.mkdir(parents=True, exist_ok=True)
                svg.write_text(SVG, encoding="utf-8")
            first_manifest = first.with_name("cover.manifest.yaml")
            second_manifest = second.with_name("cover.manifest.yaml")
            first_manifest.write_text(
                yaml.safe_dump(manifest_data(first, "posts/foo/cover.svg", "test.posts.cover"), sort_keys=False),
                encoding="utf-8",
            )
            second_manifest.write_text(
                yaml.safe_dump(manifest_data(second, "diagrams/foo/cover.svg", "test.diagrams.cover"), sort_keys=False),
                encoding="utf-8",
            )
            output_dir = root / "previews"
            report = root / "report.json"

            completed = self.run_preflight([first, second], output_dir, report)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(completed.stdout), payload)
            paths = [item["path"] for result in payload["results"] for item in result["previews"]]
            self.assertEqual(len(paths), 6)
            self.assertEqual(len(set(paths)), 6)
            self.assertTrue(all(Path(path).is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
