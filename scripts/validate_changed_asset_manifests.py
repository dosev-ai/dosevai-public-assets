#!/usr/bin/env python3
"""Validate changed governed asset packages against repository bytes."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

from asset_manifest_core import ManifestError, load_mapping, validate_manifest

ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".m4a", ".pdf", ".pptx"}


def changed_paths(repo_root: Path, base: str) -> list[str]:
    if not base or set(base) == {"0"}:
        return [path.relative_to(repo_root).as_posix() for path in repo_root.glob("posts/**/*.manifest.yaml")]
    commands = (["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
                ["git", "diff", "--name-only", "--diff-filter=ACMR", base, "HEAD"])
    for command in commands:
        result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    raise ManifestError("GIT_DIFF_FAILED", result.stderr.strip() or base)


def manifests_for_paths(repo_root: Path, paths: list[str]) -> list[Path]:
    selected: set[Path] = set()
    for raw in paths:
        rel = PurePosixPath(raw)
        if not rel.parts or rel.parts[0] == "fixtures":
            continue
        candidate = repo_root.joinpath(*rel.parts)
        if raw.endswith(".manifest.yaml"):
            if candidate.exists():
                selected.add(candidate)
            continue
        if rel.suffix.lower() in ASSET_SUFFIXES and rel.parts[0] == "posts":
            manifest = candidate.with_name(candidate.stem + ".manifest.yaml")
            if not manifest.exists():
                raise ManifestError("ADJACENT_MANIFEST_REQUIRED", manifest.relative_to(repo_root).as_posix())
            selected.add(manifest)
    return sorted(selected)


def validate_paths(repo_root: Path, paths: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for manifest in manifests_for_paths(repo_root, paths):
        data = load_mapping(manifest)
        if data.get("schema_version") != 1 or not data.get("profile"):
            raise ManifestError("LEGACY_MANIFEST_CHANGE_FORBIDDEN", manifest.relative_to(repo_root).as_posix())
        source_path = data.get("source_path")
        if not isinstance(source_path, str):
            raise ManifestError("MISSING_FIELD", f"{manifest}: source_path")
        asset = repo_root.joinpath(*PurePosixPath(source_path).parts)
        validate_manifest(data, asset)
        results.append({
            "manifest": manifest.relative_to(repo_root).as_posix(),
            "asset": asset.relative_to(repo_root).as_posix(),
            "profile": data["profile"],
            "asset_id": data["asset_id"],
        })
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="")
    parser.add_argument("--paths", nargs="*")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = args.repo_root.resolve()
    try:
        paths = args.paths if args.paths is not None else changed_paths(repo_root, args.base)
        results = validate_paths(repo_root, paths)
        print(json.dumps({"ok": True, "validated": results, "count": len(results)}, sort_keys=True))
        return 0
    except ManifestError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "message": exc.message}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
