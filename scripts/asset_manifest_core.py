"""Core governed asset-manifest schema, normalization, and validation."""
from __future__ import annotations

import datetime as dt
import hashlib
import mimetypes
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from yaml.constructor import ConstructorError

from asset_manifest_svg import SvgValidationError, validate_svg

SCHEMA_VERSION = 1
SUPPORTED_PROFILES = {"image"}
SAFE_LEGACY_STATES = {"approved-for-publication", "approved-for-review", "reviewed-public-safe", "public-safe"}

ORDERED_KEYS = [
    "schema_version", "profile", "asset_id", "visual_id", "content_id", "source_class", "project",
    "source_repository", "source_path", "mime_type", "sha256", "role", "section_anchor", "sequence",
    "step_key", "title", "alt", "caption", "semantic_description", "claims", "boundaries", "audience",
    "creation_method", "contributor", "license", "public_safe", "guide_eligible", "external_resources",
    "scripts", "remote_fonts", "created_at",
]
ALLOWED_KEYS = set(ORDERED_KEYS)
LEGACY_KEYS = {
    "visual_id", "repository", "path", "role", "target_content", "title", "alt_text", "caption",
    "semantic_description", "claims", "boundaries", "audience", "creation_method", "rights",
    "public_safety", "external_resources", "scripts", "remote_fonts", "guide_eligible", "created_at",
}
REQUIRED = {
    "schema_version": int, "profile": str, "asset_id": str, "content_id": str, "source_class": str,
    "project": str, "source_repository": str, "source_path": str, "mime_type": str, "role": str,
    "alt": str, "caption": str, "semantic_description": str, "claims": list, "boundaries": list,
    "creation_method": str, "contributor": str, "license": str, "public_safe": bool,
    "guide_eligible": bool, "external_resources": bool, "scripts": bool,
}
ROLE_MAP = {"cover": "explanatory_cover", "inline": "explanatory_inline", "gallery": "gallery_item"}
MIME_BY_SUFFIX = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
OPTIONAL_TYPES = {
    "visual_id": str, "sha256": str, "role": str, "section_anchor": (str, type(None)), "sequence": int,
    "step_key": str, "title": str, "audience": list, "remote_fonts": bool, "created_at": str,
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError("while constructing a mapping", node.start_mark, f"duplicate key: {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping

UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


class ManifestError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def fail(code: str, message: str) -> None:
    raise ManifestError(code, message)


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except FileNotFoundError:
        fail("FILE_NOT_FOUND", str(path))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        fail("INVALID_YAML", str(exc))
    if not isinstance(data, dict):
        fail("INVALID_DOCUMENT", "manifest root must be a mapping")
    return data


def canonical(data: dict[str, Any]) -> dict[str, Any]:
    return {key: data[key] for key in ORDERED_KEYS if key in data}


def dump_manifest(data: dict[str, Any]) -> str:
    return yaml.safe_dump(canonical(data), sort_keys=False, allow_unicode=True, width=1000)


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        fail("INVALID_SOURCE_PATH", value)
    return path.as_posix()


def mime_for(source_path: str) -> str:
    suffix = PurePosixPath(source_path).suffix.lower()
    mime = MIME_BY_SUFFIX.get(suffix) or mimetypes.guess_type(source_path)[0]
    if not mime:
        fail("UNKNOWN_MIME_TYPE", source_path)
    return mime


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
    except FileNotFoundError:
        fail("ASSET_NOT_FOUND", str(path))
    return digest.hexdigest()


def legacy_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"none", "false", "no", "disabled", "absent"}:
            return False
        if lowered in {"true", "yes", "enabled", "present"}:
            return True
    fail("INVALID_LEGACY_BOOLEAN", f"{field}={value!r}")


def _matches_type(value: Any, expected: type | tuple[type, ...]) -> bool:
    if expected is int:
        return type(value) is int
    if expected is bool:
        return type(value) is bool
    return isinstance(value, expected)


def validate_manifest(data: dict[str, Any], asset: Path | None = None) -> dict[str, Any]:
    unknown = sorted(set(data) - ALLOWED_KEYS)
    if unknown:
        fail("UNKNOWN_FIELDS", ", ".join(unknown))
    for key, expected in REQUIRED.items():
        value = data.get(key)
        if key not in data:
            fail("MISSING_FIELD", key)
        if not _matches_type(value, expected) or (expected is str and not value.strip()):
            fail("INVALID_FIELD_TYPE", f"{key} must be {expected.__name__}")
    for key, expected in OPTIONAL_TYPES.items():
        if key in data and not _matches_type(data[key], expected):
            expected_name = expected.__name__ if isinstance(expected, type) else " or ".join(item.__name__ for item in expected)
            fail("INVALID_FIELD_TYPE", f"{key} must be {expected_name}")
    if data["schema_version"] != SCHEMA_VERSION:
        fail("UNSUPPORTED_SCHEMA_VERSION", str(data["schema_version"]))
    if data["profile"] not in SUPPORTED_PROFILES:
        fail("UNSUPPORTED_PROFILE", data["profile"])
    if data["profile"] == "image":
        if data.get("visual_id") != data["asset_id"]:
            fail("IDENTITY_MISMATCH", "visual_id must equal asset_id for image profile v1")
        if data.get("remote_fonts") is not False:
            fail("REMOTE_FONTS_FORBIDDEN", "remote_fonts must be false")
    if "audience" in data and (not data["audience"] or not all(isinstance(item, str) and item.strip() for item in data["audience"])):
        fail("EMPTY_SEMANTIC_LIST", "audience")
    for key in ("claims", "boundaries"):
        if not data[key] or not all(isinstance(item, str) and item.strip() for item in data[key]):
            fail("EMPTY_SEMANTIC_LIST", key)
    if not data["public_safe"]:
        fail("PUBLIC_SAFE_REQUIRED", "public_safe must be true")
    if data["external_resources"] or data["scripts"]:
        fail("UNSAFE_RESOURCE_FLAGS", "external_resources and scripts must be false")

    source_path = safe_path(data["source_path"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", data["source_repository"]) or ".." in data["source_repository"].split("/"):
        fail("INVALID_SOURCE_REPOSITORY", data["source_repository"])
    expected_mime = MIME_BY_SUFFIX.get(PurePosixPath(source_path).suffix.lower())
    if expected_mime and data["mime_type"] != expected_mime:
        fail("MIME_PATH_MISMATCH", f"{data['mime_type']} != {expected_mime}")
    checksum = data.get("sha256")
    if checksum is not None and not re.fullmatch(r"[0-9a-f]{64}", str(checksum)):
        fail("INVALID_SHA256", str(checksum))

    if asset is not None:
        if asset.name != PurePosixPath(source_path).name:
            fail("ASSET_FILENAME_MISMATCH", f"{asset.name} != {PurePosixPath(source_path).name}")
        actual = sha256(asset)
        if checksum is not None and checksum != actual:
            fail("CHECKSUM_MISMATCH", f"{checksum} != {actual}")
        if asset.suffix.lower() == ".svg":
            try:
                validate_svg(asset)
            except SvgValidationError as exc:
                fail(exc.code, exc.message)
    return data


def normalize_legacy(
    legacy: dict[str, Any], *, project: str, contributor: str, source_class: str = "project_owned",
    license_id: str = "CC0-1.0", sequence: int = 0, section_anchor: str | None = None,
    step_key: str | None = None, asset: Path | None = None,
) -> dict[str, Any]:
    unknown = sorted(set(legacy) - LEGACY_KEYS)
    if unknown:
        fail("UNKNOWN_LEGACY_FIELDS", ", ".join(unknown))
    target = legacy.get("target_content")
    visual_id = legacy.get("visual_id")
    repository = legacy.get("repository")
    source_path = legacy.get("path")
    alt = legacy.get("alt_text")
    if not isinstance(target, dict) or not isinstance(target.get("slug"), str):
        fail("LEGACY_CONTENT_ID_MISSING", "target_content.slug")
    if not all(isinstance(value, str) and value.strip() for value in (visual_id, repository, source_path, alt)):
        fail("LEGACY_REQUIRED_FIELD_MISSING", "visual_id, repository, path, and alt_text are required")
    state = legacy.get("public_safety")
    public_safe = state if isinstance(state, bool) else isinstance(state, str) and state.strip().lower() in SAFE_LEGACY_STATES
    if public_safe is not True:
        fail("LEGACY_PUBLIC_SAFETY_UNRECOGNIZED", repr(state))
    source_path = safe_path(source_path)
    created_at = legacy.get("created_at")
    if isinstance(created_at, (dt.date, dt.datetime)):
        created_at = created_at.isoformat()
    elif created_at is not None and not isinstance(created_at, str):
        fail("INVALID_LEGACY_CREATED_AT", repr(created_at))
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "profile": "image", "asset_id": visual_id, "visual_id": visual_id,
        "content_id": target["slug"], "source_class": source_class, "project": project,
        "source_repository": repository, "source_path": source_path, "mime_type": mime_for(source_path),
        "role": ROLE_MAP.get(legacy.get("role"), legacy.get("role")), "section_anchor": section_anchor,
        "sequence": sequence, "step_key": step_key or PurePosixPath(source_path).stem, "title": legacy.get("title"),
        "alt": alt, "caption": legacy.get("caption"), "semantic_description": legacy.get("semantic_description"),
        "claims": legacy.get("claims"), "boundaries": legacy.get("boundaries"), "audience": legacy.get("audience"),
        "creation_method": legacy.get("creation_method"), "contributor": contributor, "license": license_id,
        "public_safe": True, "guide_eligible": bool(legacy.get("guide_eligible", False)),
        "external_resources": legacy_bool(legacy.get("external_resources"), "external_resources"),
        "scripts": legacy_bool(legacy.get("scripts"), "scripts"),
        "remote_fonts": legacy_bool(legacy.get("remote_fonts"), "remote_fonts"), "created_at": created_at,
    }
    if asset is not None:
        data["sha256"] = sha256(asset)
    return canonical(validate_manifest({key: value for key, value in data.items() if value is not None}, asset))
