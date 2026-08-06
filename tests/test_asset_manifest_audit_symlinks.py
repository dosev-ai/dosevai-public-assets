from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_audit import audit_repository  # noqa: E402


class AuditSymlinkRegressionTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        directory = tempfile.TemporaryDirectory()
        (Path(directory.name) / "posts" / "sample").mkdir(parents=True)
        return directory

    def require_symlink(self, link: Path, target: Path, *, directory: bool = False) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")

    def test_symlinked_directory_is_unsafe(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            target = root / "outside-directory"
            target.mkdir()
            self.require_symlink(package / "linked-directory", target, directory=True)
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsafe": 1})
            self.assertEqual(report["items"][0]["code"], "SYMLINK_FORBIDDEN")
            self.assertEqual(report["items"][0]["assets"], ["posts/sample/linked-directory"])

    def test_symlinked_supported_asset_does_not_emit_manifest_duplicate(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            target = root / "outside.svg"
            target.write_text("<svg/>", encoding="utf-8")
            self.require_symlink(package / "cover.svg", target)
            (package / "cover.manifest.yaml").write_text("invalid: intentionally-not-read\n", encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsafe": 1})
            self.assertEqual([item["code"] for item in report["items"]], ["SYMLINK_FORBIDDEN"])

    def test_symlinked_inactive_asset_does_not_emit_orphan(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            target = root / "outside.pptx"
            target.write_bytes(b"not a presentation")
            self.require_symlink(package / "companion.pptx", target)
            (package / "companion.manifest.yaml").write_text("profile: presentation_pptx\n", encoding="utf-8")
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsafe": 1})
            self.assertEqual([item["code"] for item in report["items"]], ["SYMLINK_FORBIDDEN"])

    def test_symlinked_manifest_is_not_followed(self) -> None:
        with self.make_repo() as directory:
            root = Path(directory)
            package = root / "posts" / "sample"
            (package / "cover.svg").write_text("<svg/>", encoding="utf-8")
            target = root / "outside.manifest.yaml"
            target.write_text("invalid: intentionally-not-read\n", encoding="utf-8")
            self.require_symlink(package / "cover.manifest.yaml", target)
            report = audit_repository(root)
            self.assertEqual(report["summary"], {"unsafe": 1})
            self.assertEqual([item["code"] for item in report["items"]], ["SYMLINK_FORBIDDEN"])


if __name__ == "__main__":
    unittest.main()
