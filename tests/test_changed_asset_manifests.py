from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_core import ManifestError  # noqa: E402
from validate_changed_asset_manifests import changed_paths, manifests_for_paths, validate_paths  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc"><title id="title">Test</title><desc id="desc">Safe</desc><rect width="1" height="1"/></svg>'


def manifest_data(source_path: str, asset: Path, mime_type: str = "image/svg+xml") -> dict:
    return {
        "schema_version": 1,
        "profile": "image",
        "asset_id": "test-asset-v1",
        "visual_id": "test-asset-v1",
        "content_id": "post:test",
        "source_class": "project_owned",
        "project": "personal-operating-system",
        "source_repository": "dosev-ai/dosevai-public-assets",
        "source_path": source_path,
        "mime_type": mime_type,
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "role": "explanatory_inline",
        "alt": "Safe alt text.",
        "caption": "Safe caption.",
        "semantic_description": "Safe semantic description.",
        "claims": ["One bounded claim."],
        "boundaries": ["One explicit boundary."],
        "creation_method": "deterministic SVG",
        "contributor": "OpenAI ChatGPT with Delyan Dosev direction",
        "license": "CC0-1.0",
        "public_safe": True,
        "guide_eligible": False,
        "external_resources": False,
        "scripts": False,
        "remote_fonts": False,
    }


class ChangedAssetManifestTests(unittest.TestCase):
    def temp_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return directory, Path(directory.name)

    def test_rejects_manifest_pointing_to_non_adjacent_asset(self) -> None:
        _, repo = self.temp_repo()
        new_dir, old_dir = repo / "posts/new", repo / "posts/old"
        new_dir.mkdir(parents=True)
        old_dir.mkdir(parents=True)
        changed_asset = new_dir / "foo.svg"
        old_asset = old_dir / "foo.svg"
        changed_asset.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', encoding="utf-8")
        old_asset.write_text(SVG, encoding="utf-8")
        manifest = new_dir / "foo.manifest.yaml"
        manifest.write_text(yaml.safe_dump(manifest_data("posts/old/foo.svg", old_asset), sort_keys=False), encoding="utf-8")
        with self.assertRaises(ManifestError) as raised:
            validate_paths(repo, ["posts/new/foo.svg"])
        self.assertEqual(raised.exception.code, "CHANGED_ASSET_NOT_MANIFEST_SOURCE")

    def test_changed_extension_variant_must_be_manifest_source(self) -> None:
        _, repo = self.temp_repo()
        package = repo / "posts/test"
        package.mkdir(parents=True)
        svg = package / "foo.svg"
        png = package / "foo.png"
        manifest = package / "foo.manifest.yaml"
        svg.write_text(SVG, encoding="utf-8")
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        manifest.write_text(yaml.safe_dump(manifest_data("posts/test/foo.svg", svg), sort_keys=False), encoding="utf-8")
        with self.assertRaises(ManifestError) as raised:
            validate_paths(repo, ["posts/test/foo.png"])
        self.assertEqual(raised.exception.code, "CHANGED_ASSET_NOT_MANIFEST_SOURCE")

    def test_deletion_requires_package_pair(self) -> None:
        _, repo = self.temp_repo()
        package = repo / "posts/test"
        package.mkdir(parents=True)
        asset = package / "foo.svg"
        manifest = package / "foo.manifest.yaml"

        asset.write_text(SVG, encoding="utf-8")
        with self.assertRaises(ManifestError) as raised:
            manifests_for_paths(repo, ["posts/test/foo.manifest.yaml"])
        self.assertEqual(raised.exception.code, "ORPHANED_ASSET_AFTER_MANIFEST_DELETE")

        asset.unlink()
        manifest.write_text("schema_version: 1\n", encoding="utf-8")
        with self.assertRaises(ManifestError) as raised:
            manifests_for_paths(repo, ["posts/test/foo.svg"])
        self.assertEqual(raised.exception.code, "ORPHANED_MANIFEST_AFTER_ASSET_DELETE")

        manifest.unlink()
        self.assertEqual(manifests_for_paths(repo, ["posts/test/foo.svg", "posts/test/foo.manifest.yaml"]), [])

    def test_changed_paths_includes_deletions(self) -> None:
        _, repo = self.temp_repo()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        package = repo / "posts/test"
        package.mkdir(parents=True)
        asset = packae / "foo.svg"
        asset.write_text(SVG, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        asset.unlink()
        subprocess.run(["git", "add", "-u"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "delete"], cwd=repo, check=True)
        self.assertIn("posts/test/foo.svg", changed_paths(repo, base))

    def test_changed_paths_preserves_both_rename_endpoints(self) -> None:
        _, repo = self.temp_repo()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        package = repo / "posts/test"
        package.mkdir(parents=True)
        old_asset = package / "foo.svg"
        old_manifest = packae / "foo.manifest.yaml"
        old_asset.write_text(SVG, encoding="utf-8")
        old_manifest.write_text(yaml.safe_dump(manifest_data("posts/test/foo.svg", old_asset), sort_keys=False), encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

        new_asset = package / "bar.svg"
        new_manifest = packae / "bar.manifest.yaml"
        old_asset.rename(new_asset)
        new_manifest.write_text(yaml.safe_dump(manifest_data("posts/test/bar.svg", new_asset), sort_keys=False), encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "rename"], cwd=repo, check=True)

        paths = changed_paths(repo, base)
        self.assertIn("posts/test/foo.svg", paths)
        self.assertIn("posts/test/bar.svg", paths)
        with self.assertRaises(ManifestError) as raised:
            validate_paths(repo, paths)
        self.assertEqual(raised.exception.code, "ORPHANED_MANIFEST_AFTER_ASSET_DELETE")

    def test_zero_base_scans_assets_and_manifests(self) -> None:
        _, repo = self.temp_repo()
        package = repo / "posts/test"
        package.mkdir(parents=True)
        asset = package / "foo.svg"
        manifest = package / "foo.manifest.yaml"
        asset.write_text(SVG, encoding="utf-8")
        manifest.write_text(yaml.safe_dump(manifest_data("posts/test/foo.svg", asset), sort_keys=False), encoding="utf-8")
        paths = changed_paths(repo, "0" * 40)
        self.assertIn("posts/test/foo.svg", paths)
        self.assertIn("posts/test/foo.manifest.yaml", paths)


if __name__ == "__main__":
    unittest.main()
