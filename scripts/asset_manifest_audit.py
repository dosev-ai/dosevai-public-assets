"""Repository-wide discovery and validation for governed asset packages."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from asset_manifest_core import MIME_BY_SUFFIX, ManifestError, load_mapping, validate_manifest

DEFAULT_AUDIT_ROOTS = ("posts", "social", "diagrams", "shared")
MANIFEST_SUFFIX = ".manifest.yaml"
UNSAFE_CODES = {
    "PUBLIC_SAFE_REQUIRED",
    "UNSAFE_RESOURCE_FLAGS",
    "REMOTE_FONTS_FORBIDDEN",
    "SVG_DTD_FORBIDDEN",
    "SVG_PROCESSING_INSTRUCTION_FORBIDDEN",
    "SVG_JAVASCRIPT_FORBIDDEN",
    "SVG_CSS_IMPORT_FORBIDDEN",
    "SVG_EXTERNAL_CSS_URL_FORBIDDEN",
    "SVG_XINCLUDE_FORBIDDEN",
    "SVG_FOREIGN_NAMESPACE_FORBIDDEN",
    "SVG_ACTIVE_OR_FOREIGN_CONTENT",
    "SVG_EVENT_HANDLER_FORBIDDEN",
    "SVG_XML_BASE_FORBIDDEN",
    "SVG_EXTERNAL_REFERENCE_FORBIDDEN",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _manifest_path(parent: Path, stem: str) -> Path:
    return parent / f"{stem}{MANIFEST_SUFFIX}"


def _classification(code: str) -> str:
    if code == "UNSUPPORTED_PROFILE":
        return "unsupported_profile"
    if code in UNSAFE_CODES:
        return "unsafe"
    return "repair"


def _item(
    *,
    root: Path,
    status: str,
    code: str,
    message: str,
    asset_paths: Iterable[Path] = (),
    manifest_path: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assets = sorted(_relative(path, root) for path in asset_paths)
    result: dict[str, Any] = {
        "status": status,
        "code": code,
        "message": message,
        "assets": assets,
        "manifest": _relative(manifest_path, root) if manifest_path else None,
    }
    if manifest:
        for key in ("asset_id", "content_id", "profile", "role", "source_path", "mime_type", "sha256"):
            if key in manifest:
                result[key] = manifest[key]
    return result


def _discover_roots(repo_root: Path, include_roots: Iterable[str] | None) -> list[Path]:
    names = tuple(include_roots or DEFAULT_AUDIT_ROOTS)
    roots: list[Path] = []
    for name in names:
        candidate = (repo_root / name).resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError as exc:
            raise ManifestError("INVALID_AUDIT_ROOT", name) from exc
        if candidate.is_dir():
            roots.append(candidate)
    if not roots:
        raise ManifestError("NO_AUDIT_ROOTS", ", ".join(names))
    return roots


def audit_repository(repo_root: Path, include_roots: Iterable[str] | None = None) -> dict[str, Any]:
    root = repo_root.resolve()
    if not root.is_dir():
        raise ManifestError("INVALID_REPOSITORY_ROOT", str(repo_root))

    scan_roots = _discover_roots(root, include_roots)
    asset_suffixes = set(MIME_BY_SUFFIX)
    assets: list[Path] = []
    manifests: list[Path] = []
    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            if path.name.endswith(MANIFEST_SUFFIX):
                manifests.append(path)
            elif path.suffix.lower() in asset_suffixes:
                assets.append(path)

    grouped_assets: dict[tuple[Path, str], list[Path]] = {}
    for asset in sorted(assets):
        grouped_assets.setdefault((asset.parent, asset.stem), []).append(asset)

    items: list[dict[str, Any]] = []
    consumed_manifests: set[Path] = set()
    for (parent, stem), variants in sorted(
        grouped_assets.items(),
        key=lambda entry: (_relative(entry[0][0], root), entry[0][1]),
    ):
        manifest_path = _manifest_path(parent, stem)
        if len(variants) > 1:
            if manifest_path.exists():
                consumed_manifests.add(manifest_path)
            items.append(
                _item(
                    root=root,
                    status="repair",
                    code="AMBIGUOUS_ASSET_VARIANTS",
                    message="multiple supported asset extensions share one package stem",
                    asset_paths=variants,
                    manifest_path=manifest_path if manifest_path.exists() else None,
                )
            )
            continue
        asset = variants[0]
        if not manifest_path.exists():
            items.append(
                _item(
                    root=root,
                    status="missing_manifest",
                    code="MISSING_ADJACENT_MANIFEST",
                    message="asset has no adjacent .manifest.yaml file",
                    asset_paths=[asset],
                )
            )
            continue

        consumed_manifests.add(manifest_path)
        manifest: dict[str, Any] | None = None
        try:
            manifest = load_mapping(manifest_path)
            validated = validate_manifest(manifest, asset)
        except ManifestError as exc:
            items.append(
                _item(
                    root=root,
                    status=_classification(exc.code),
                    code=exc.code,
                    message=exc.message,
                    asset_paths=[asset],
                    manifest_path=manifest_path,
                    manifest=manifest,
                )
            )
            continue
        items.append(
            _item(
                root=root,
                status="pass",
                code="PACKAGE_VALID",
                message="manifest and actual asset bytes validate",
                asset_paths=[asset],
                manifest_path=manifest_path,
                manifest=validated,
            )
        )

    for manifest_path in sorted(set(manifests) - consumed_manifests):
        stem = manifest_path.name[: -len(MANIFEST_SUFFIX)]
        candidates = [manifest_path.parent / f"{stem}{suffix}" for suffix in sorted(asset_suffixes)]
        existing = [path for path in candidates if path.exists()]
        items.append(
            _item(
                root=root,
                status="orphan_manifest",
                code="ORPHAN_MANIFEST" if not existing else "UNMATCHED_MANIFEST",
                message="manifest has no unique supported adjacent asset",
                asset_paths=existing,
                manifest_path=manifest_path,
            )
        )

    items.sort(key=lambda item: (item["manifest"] or "", item["assets"], item["status"], item["code"]))
    counts = Counter(item["status"] for item in items)
    summary = {key: counts[key] for key in sorted(counts)}
    findings = sum(count for status, count in counts.items() if status != "pass")
    return {
        "ok": findings == 0,
        "repository_root": str(root),
        "audit_roots": [_relative(path, root) for path in scan_roots],
        "summary": summary,
        "package_count": len(items),
        "finding_count": findings,
        "items": items,
    }


def format_audit_text(report: dict[str, Any]) -> str:
    lines = [
        f"Governed asset audit: {'PASS' if report['ok'] else 'FINDINGS'}",
        f"Packages: {report['package_count']} | Findings: {report['finding_count']}",
    ]
    for status, count in report["summary"].items():
        lines.append(f"- {status}: {count}")
    for item in report["items"]:
        location = item["manifest"] or ", ".join(item["assets"]) or "<unknown>"
        lines.append(f"[{item['status']}] {location}: {item['code']} - {item['message']}")
    return "\n".join(lines)
