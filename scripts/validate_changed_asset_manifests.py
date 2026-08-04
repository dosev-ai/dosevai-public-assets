#!/usr/bin/env python3
"""Validate changed governed asset packages against repository bytes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

from asset_manifest_core import ManifestError, load_mapping, validate_manifest

ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".m4a", ".pdf", ".pptx"}
MANIFEST_SUFFIX = ".manifest.yaml"


def _unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if path and path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _parse_name_status(output: bytes) -> list[str]:
    fields = output.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    paths: list[str] = []
    index = 0
    while index < len(fields):
        raw_status = fields[index]
        index += 1
        try:
            status = raw_status.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ManifestError("GIT_DIFF_PARSE_FAILED", repr(raw_status)) from exc
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count > len(fields):
            raise ManifestError("GIT_DIFF_PARSE_FAILED", status)
        raw_paths = fields[index:index + path_count]
        if any(not path for path in raw_paths):
            raise ManifestError("GIT_DIFF_PARSE_FAILED", status)
        paths.extend(os.fsdecode(path) for path in raw_paths)
        index += path_count
    return _unique_paths(paths)


def changed_paths(repo_root: Path, base: str) -> list[str]:
    if not base or set(base) == {"0"}:
        candidates = [
            path.relative_to(repo_root).as_posix()
            for path in repo_root.glob("posts/**/*")
            if path.is_file() and (path.name.endswith(MANIFEST_SUFFIX) or path.suffix.lower() in ASSET_SUFFIXES)
        ]
        return sorted(candidates)
    commands = (
        ["git", "diff", "--name-status", "-z", "--find-renames", "--diff-filter=ACMRD", f"{base}...HEAD"],
        ["git", "diff", "--name-status", "-z", "--find-renames", "--diff-filter=ACMRD", base, "HEAD"],
    )
    result: subprocess.CompletedProcess[bytes] | None = None
    for command in commands:
        result = subprocess.run(command, cwd=repo_root, capture_output=True, check=False)
        if result.returncode == 0:
            return _parse_name_status(result.stdout)
    stderr = os.fsdecode(result.stderr).strip() if result else ""
    raise ManifestError("GIT_DIFF_FAILED", stderr or base)


def manifest_for_asset(asset: Path) -> Path:
    return asset.with_name(asset.stem + MANIFEST_SUFFIX)


def adjacent_assets_for_manifest(manifest: Path) -> list[Path]:
    prefix = manifest.name[: -len(MANIFEST_SUFFIX)]
    return sorted(
        path
        for path in manifest.parent.iterdir()
        if path.is_file() and path.stem == prefix and path.suffix.lower() in ASSET_SUFFIXES
    ) if manifest.parent.exists() else []


def manifests_for_paths(repo_root: Path, paths: list[str]) -> list[Path]:
    selected: set[Path] = set()
    for raw in paths:
        rel = PurePosixPath(raw)
        if not rel.parts or rel.parts[0] == "fixtures":
            continue
        candidate = repo_root.joinpath(*rel.parts)
        if raw.endswith(MANIFEST_SUFFIX):
            if candidate.exists():
                selected.add(candidate)
            elif rel.parts[0] == "posts" and adjacent_assets_for_manifest(candidate):
                raise ManifestError(
                    "ORPHANED_ASSET_AFTER_MANIFEST_DELETE",
                    candidate.relative_to(repo_root).as_posix(),
                )
            continue
        if rel.suffix.lower() in ASSET_SUFFIXES and rel.parts[0] == "posts":
            manifest = manifest_for_asset(candidate)
            if candidate.exists():
                if not manifest.exists():
                    raise ManifestError("ADJACENT_MANIFEST_REQUIRED", manifest.relative_to(repo_root).as_posix())
                selected.add(manifest)
            elif manifest.exists():
                if adjacent_assets_for_manifest(manifest):
                    selected.add(manifest)
                else:
                    raise ManifestError(
                        "ORPHANED_MANIFEST_AFTER_ASSET_DELETE",
                        manifest.relative_to(repo_root).as_posix(),
                    )
    return sorted(selected)


def expected_adjacent_source(repo_root: Path, manifest: Path, source_path: str) -> Path:
    source = PurePosixPath(source_path)
    if source.is_absolute() or ".." in source.parts or not source.parts:
        raise ManifestError("INVALID_SOURCE_PATH", source_path)
    prefix = manifest.name[: -len(MANIFEST_SUFFIX)]
    expected = manifest.parent / f"{prefix}{source.suffix}"
    actual = repo_root.joinpath(*source.parts)
    try:
        expected_rel = expected.relative_to(repo_root).as_posix()
        actual_rel = actual.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ManifestError("INVALID_SOURCE_PATH", source_path) from exc
    if actual_rel != expected_rel:
        raise ManifestError(
            "SOURCE_PATH_NOT_ADJACENT",
            f"{manifest.relative_to(repo_root).as_posix()}: {actual_rel} != {expected_rel}",
        )
    return actual


def _validate_changed_asset_binding(repo_root: Path, paths: list[str]) -> None:
    for raw in paths:
        rel = PurePosixPath(raw)
        if not rel.parts or rel.parts[0] != "posts" or rel.suffix.lower() not in ASSET_SUFFIXES:
            continue
        asset = repo_root.joinpath(*rel.parts)
        if not asset.exists():
            continue
        manifest = manifest_for_asset(asset)
        if not manifest.exists():
            raise ManifestError("ADJACENT_MANIFEST_REQUIRED", manifest.relative_to(repo_root).as_posix())
        data = load_mapping(manifest)
        source_path = data.get("source_path")
        actual_path = asset.relative_to(repo_root).as_posix()
        if not isinstance(source_path, str):
            raise ManifestError("MISSING_FIELD", f"{manifest}: source_path")
        if source_path != actual_path:
            raise ManifestError(
                "CHANGED_ASSET_NOT_MANIFEST_SOURCE",
                f"{actual_path} != {source_path}",
            )


def validate_paths(repo_root: Path, paths: list[str]) -> list[dict[str, str]]:
    _validate_changed_asset_binding(repo_root, paths)
    results: list[dict[str, str]] = []
    for manifest in manifests_for_paths(repo_root, paths):
        data = load_mapping(manifest)
        if data.get("schema_version") != 1 or not data.get("profile"):
            raise ManifestError("LEGACY_MANIFEST_CHANGE_FORBIDDEN", manifest.relative_to(repo_root).as_posix())
        source_path = data.get("source_path")
        if not isinstance(source_path, str):
            raise ManifestError("MISSING_FIELD", f"{manifest}: source_path")
        asset = expected_adjacent_source(repo_root, manifest, source_path)
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
