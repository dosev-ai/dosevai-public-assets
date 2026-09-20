"""Core governed asset-manifest schema, normalization, and validation."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import mimetypes
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, UnidentifiedImageError
import yaml
from yaml.constructor import ConstructorError

from asset_manifest_audio import AudioValidationError, validate_mp3_audio
from asset_manifest_svg import SvgValidationError, validate_svg

SCHEMA_VERSION = 1
SUPPORTED_PROFILES = {"image", "document_pdf", "audio", "presentation_pptx"}
SAFE_LEGACY_STATES = {"approved-for-publication", "approved-for-review", "reviewed-public-safe", "public-safe"}

ORDERED_KEYS = [
    "schema_version", "profile", "asset_id", "visual_id", "content_id", "source_class", "project",
    "source_repository", "source_path", "mime_type", "sha256", "role", "section_anchor", "sequence",
    "step_key", "title", "subtitle", "alt", "caption", "semantic_description", "claims", "boundaries",
    "audience", "creation_method", "contributor", "license", "public_safe", "guide_eligible",
    "external_resources", "scripts", "remote_fonts", "page_count", "source_format", "render_inspected",
    "render_evidence", "private_notes_removed", "embedded_object_policy", "annotation_policy",
    "duration_ms", "codec", "container", "source_projection_contract", "source_projection_path",
    "source_content_hash", "coverage_mode", "provider_profile", "provider", "provider_route", "model",
    "voice", "instructions", "assembly_plan_hash", "rights_policy", "safety_policy",
    "audio_generation_identity", "disclosure", "production_date", "slide_count", "template_contract",
    "speaker_notes_policy", "derived_pdf_manifest_path", "derived_pdf_asset_id", "derived_pdf_sha256",
    "filename_policy", "update_policy", "created_at",
]
ALLOWED_KEYS = set(ORDERED_KEYS)
LEGACY_KEYS = {
    "visual_id", "repository", "path", "role", "target_content", "title", "alt_text", "caption",
    "semantic_description", "claims", "boundaries", "audience", "creation_method", "rights",
    "public_safety", "external_resources", "scripts", "remote_fonts", "guide_eligible", "created_at",
}
PDF_LEGACY_KEYS = {
    "schema_version", "asset_id", "title", "subtitle", "asset_type", "source_format", "pages", "sha256",
    "license", "filename_policy", "update_policy", "alt_text", "caption", "semantic_description", "claims",
    "boundaries", "creation_method", "public_safety_state",
}
AUDIO_LEGACY_KEYS = {
    "slug", "source_hash", "url", "model", "voice", "format", "duration_seconds", "generated_at", "disclosure",
}
REQUIRED = {
    "schema_version": int, "profile": str, "asset_id": str, "content_id": str, "source_class": str,
    "project": str, "source_repository": str, "source_path": str, "mime_type": str, "role": str,
    "alt": str, "caption": str, "semantic_description": str, "claims": list, "boundaries": list,
    "creation_method": str, "contributor": str, "license": str, "public_safe": bool,
    "guide_eligible": bool, "external_resources": bool, "scripts": bool,
}
PDF_REQUIRED = {
    "sha256": str, "page_count": int, "source_format": str, "render_inspected": bool, "render_evidence": str,
    "private_notes_removed": bool, "embedded_object_policy": str, "annotation_policy": str,
}
AUDIO_REQUIRED = {
    "sha256": str, "duration_ms": int, "codec": str, "container": str, "source_projection_contract": str,
    "source_projection_path": str, "source_content_hash": str, "coverage_mode": str, "provider_profile": str,
    "provider": str, "provider_route": str, "model": str, "voice": str, "assembly_plan_hash": str,
    "rights_policy": str, "safety_policy": str, "audio_generation_identity": str, "disclosure": str,
    "production_date": str,
}
PPTX_REQUIRED = {
    "sha256": str, "slide_count": int, "template_contract": str, "speaker_notes_policy": str,
    "source_format": str, "render_inspected": bool, "render_evidence": str, "private_notes_removed": bool,
}
AUDIO_GENERATION_FIELDS = (
    "content_id", "source_content_hash", "source_projection_contract", "coverage_mode", "provider_profile",
    "provider", "provider_route", "model", "voice", "instructions", "assembly_plan_hash", "codec", "container",
    "rights_policy", "safety_policy",
)
AUDIO_COVERAGE_MODES = {"prose_only", "full_text"}
PPTX_SPEAKER_NOTES_POLICIES = {"forbid", "reviewed_public"}
AUDIO_TRIM_CHARS = "".join(chr(code) for code in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20))
ROLE_MAP = {"cover": "explanatory_cover", "inline": "explanatory_inline", "gallery": "gallery_item"}
MIME_BY_SUFFIX = {
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".pdf": "application/pdf", ".mp3": "audio/mpeg",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
PIL_FORMAT_BY_MIME = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
OPTIONAL_TYPES = {
    "visual_id": str, "sha256": str, "role": str, "section_anchor": (str, type(None)), "sequence": int,
    "step_key": str, "title": str, "subtitle": str, "audience": list, "remote_fonts": bool,
    "page_count": int, "source_format": str, "render_inspected": bool, "render_evidence": str,
    "private_notes_removed": bool, "embedded_object_policy": str, "annotation_policy": str,
    "duration_ms": int, "codec": str, "container": str, "source_projection_contract": str,
    "source_projection_path": str, "source_content_hash": str, "coverage_mode": str, "provider_profile": str,
    "provider": str, "provider_route": str, "model": str, "voice": str, "instructions": str,
    "assembly_plan_hash": str, "rights_policy": str, "safety_policy": str, "audio_generation_identity": str,
    "disclosure": str, "production_date": str, "slide_count": int, "template_contract": str,
    "speaker_notes_policy": str, "derived_pdf_manifest_path": str, "derived_pdf_asset_id": str,
    "derived_pdf_sha256": str, "filename_policy": str, "update_policy": str, "created_at": str,
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError("while constructing a mapping", node.start_mark, f"non-string key: {key!r}", key_node.start_mark)
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


def _validate_required_fields(data: dict[str, Any], required: dict[str, type]) -> None:
    for key, expected in required.items():
        value = data.get(key)
        if key not in data:
            fail("MISSING_FIELD", key)
        if not _matches_type(value, expected) or (expected is str and not value.strip()):
            fail("INVALID_FIELD_TYPE", f"{key} must be {expected.__name__}")


def validate_raster_image(path: Path, mime_type: str) -> None:
    expected_format = PIL_FORMAT_BY_MIME.get(mime_type)
    if expected_format is None:
        fail("UNSUPPORTED_IMAGE_MIME", mime_type)
    try:
        with Image.open(path) as image:
            detected_format = image.format
            image.verify()
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            detected_format = image.format or detected_format
    except FileNotFoundError:
        fail("ASSET_NOT_FOUND", str(path))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        fail("IMAGE_DECODE_FAILED", f"{path.name}: {exc}")
    if detected_format != expected_format:
        fail("IMAGE_SIGNATURE_MISMATCH", f"{path.name}: {detected_format} != {expected_format}")
    if width <= 0 or height <= 0:
        fail("IMAGE_DIMENSIONS_INVALID", f"{path.name}: {width}x{height}")


def _validate_pdf_contract(data: dict[str, Any]) -> None:
    _validate_required_fields(data, PDF_REQUIRED)
    if data["page_count"] <= 0:
        fail("PDF_PAGE_COUNT_INVALID", str(data["page_count"]))
    if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", data["source_format"]):
        fail("PDF_SOURCE_FORMAT_INVALID", data["source_format"])
    if data["render_inspected"] is not True:
        fail("PDF_RENDER_INSPECTION_REQUIRED", "render_inspected must be true")
    if data["private_notes_removed"] is not True:
        fail("PDF_PRIVATE_NOTES_REMOVAL_REQUIRED", "private_notes_removed must be true")
    if data["embedded_object_policy"] != "forbid":
        fail("PDF_EMBEDDED_OBJECT_POLICY_INVALID", data["embedded_object_policy"])
    if data["annotation_policy"] != "forbid":
        fail("PDF_ANNOTATION_POLICY_INVALID", data["annotation_policy"])


def canonicalize_audio_instructions(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized.strip(AUDIO_TRIM_CHARS)


def compute_audio_generation_identity(data: dict[str, Any]) -> str:
    values = ["audio-generation-identity-v1"]
    for key in AUDIO_GENERATION_FIELDS:
        value = data[key]
        values.append(unicodedata.normalize("NFC", value))
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_iso_date(value: str, code: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(code, value)
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        fail(code, value)


def _validate_audio_contract(data: dict[str, Any]) -> None:
    _validate_required_fields(data, AUDIO_REQUIRED)
    if "instructions" not in data:
        fail("MISSING_FIELD", "instructions")
    if not isinstance(data["instructions"], str):
        fail("INVALID_FIELD_TYPE", "instructions must be str")
    canonical_instructions = canonicalize_audio_instructions(data["instructions"])
    if data["instructions"] != canonical_instructions:
        fail("AUDIO_INSTRUCTIONS_NOT_CANONICAL", "instructions must equal audio-instructions-v1 output")
    if data["duration_ms"] <= 0:
        fail("AUDIO_DURATION_INVALID", str(data["duration_ms"]))
    if data["codec"] != "mp3" or data["container"] != "mp3":
        fail("AUDIO_ENVELOPE_INVALID", f"{data['codec']}/{data['container']}")
    if data["source_projection_contract"] != "dosevai-narration-v1":
        fail("AUDIO_SOURCE_PROJECTION_UNSUPPORTED", data["source_projection_contract"])
    projection_path = safe_path(data["source_projection_path"])
    source_path = safe_path(data["source_path"])
    if projection_path == source_path:
        fail("AUDIO_SOURCE_PROJECTION_INVALID", "source projection must be a distinct adjacent file")
    if PurePosixPath(projection_path).parent != PurePosixPath(source_path).parent:
        fail("AUDIO_SOURCE_PROJECTION_NOT_ADJACENT", projection_path)
    if not re.fullmatch(r"[0-9a-f]{64}", data["source_content_hash"]):
        fail("AUDIO_SOURCE_HASH_INVALID", data["source_content_hash"])
    if data["coverage_mode"] not in AUDIO_COVERAGE_MODES:
        fail("AUDIO_COVERAGE_MODE_INVALID", data["coverage_mode"])
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", data["assembly_plan_hash"]):
        fail("AUDIO_ASSEMBLY_PLAN_HASH_INVALID", data["assembly_plan_hash"])
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", data["audio_generation_identity"]):
        fail("AUDIO_GENERATION_IDENTITY_INVALID", data["audio_generation_identity"])
    expected_identity = compute_audio_generation_identity(data)
    if data["audio_generation_identity"] != expected_identity:
        fail("AUDIO_GENERATION_IDENTITY_MISMATCH", f"{data['audio_generation_identity']} != {expected_identity}")
    _validate_iso_date(data["production_date"], "AUDIO_PRODUCTION_DATE_INVALID")


def _validate_pptx_contract(data: dict[str, Any]) -> None:
    _validate_required_fields(data, PPTX_REQUIRED)
    if data["slide_count"] <= 0:
        fail("PPTX_SLIDE_COUNT_INVALID", str(data["slide_count"]))
    if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", data["source_format"]):
        fail("PPTX_SOURCE_FORMAT_INVALID", data["source_format"])
    if data["render_inspected"] is not True:
        fail("PPTX_RENDER_INSPECTION_REQUIRED", "render_inspected must be true")
    if data["private_notes_removed"] is not True:
        fail("PPTX_PRIVATE_NOTES_REMOVAL_REQUIRED", "private_notes_removed must be true")
    if data["speaker_notes_policy"] not in PPTX_SPEAKER_NOTES_POLICIES:
        fail("PPTX_SPEAKER_NOTES_POLICY_INVALID", data["speaker_notes_policy"])
    derived_keys = ("derived_pdf_manifest_path", "derived_pdf_asset_id", "derived_pdf_sha256")
    present = [key in data for key in derived_keys]
    if any(present) and not all(present):
        fail("PPTX_DERIVED_PDF_FIELDS_INCOMPLETE", ", ".join(derived_keys))
    if all(present):
        safe_path(data["derived_pdf_manifest_path"])
        if not data["derived_pdf_manifest_path"].endswith(".manifest.yaml"):
            fail("PPTX_DERIVED_PDF_MANIFEST_INVALID", data["derived_pdf_manifest_path"])
        if not data["derived_pdf_asset_id"].strip():
            fail("PPTX_DERIVED_PDF_ASSET_ID_INVALID", data["derived_pdf_asset_id"])
        if not re.fullmatch(r"[0-9a-f]{64}", data["derived_pdf_sha256"]):
            fail("PPTX_DERIVED_PDF_SHA256_INVALID", data["derived_pdf_sha256"])


def _legacy_audio_production_date(value: Any) -> str:
    if not isinstance(value, str):
        fail("AUDIO_LEGACY_GENERATED_AT_INVALID", repr(value))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _validate_iso_date(value, "AUDIO_LEGACY_GENERATED_AT_INVALID")
        return value
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(candidate)
    except ValueError:
        fail("AUDIO_LEGACY_GENERATED_AT_INVALID", value)
    if parsed.tzinfo is None:
        fail("AUDIO_LEGACY_GENERATED_AT_INVALID", value)
    return parsed.astimezone(dt.timezone.utc).date().isoformat()


def map_audio_legacy(legacy: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(legacy) - AUDIO_LEGACY_KEYS)
    if unknown:
        fail("UNKNOWN_LEGACY_FIELDS", ", ".join(unknown))
    for key in ("slug", "source_hash", "model", "voice", "format", "generated_at", "disclosure"):
        if not isinstance(legacy.get(key), str) or not legacy[key].strip():
            fail("AUDIO_LEGACY_REQUIRED_FIELD_MISSING", key)
    if not re.fullmatch(r"[0-9a-f]{64}", legacy["source_hash"]):
        fail("AUDIO_SOURCE_HASH_INVALID", legacy["source_hash"])
    if legacy["format"] != "mp3":
        fail("AUDIO_LEGACY_FORMAT_UNSUPPORTED", legacy["format"])
    seconds = legacy.get("duration_seconds")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float, str)):
        fail("AUDIO_LEGACY_DURATION_INVALID", repr(seconds))
    try:
        millis = Decimal(str(seconds)) * Decimal(1000)
    except InvalidOperation:
        fail("AUDIO_LEGACY_DURATION_INVALID", repr(seconds))
    if millis <= 0 or millis != millis.to_integral_value():
        fail("AUDIO_LEGACY_DURATION_INVALID", repr(seconds))
    return {
        "content_id": legacy["slug"],
        "source_content_hash": legacy["source_hash"],
        "model": legacy["model"],
        "voice": legacy["voice"],
        "codec": "mp3",
        "container": "mp3",
        "duration_ms": int(millis),
        "disclosure": legacy["disclosure"],
        "production_date": _legacy_audio_production_date(legacy["generated_at"]),
    }


def validate_manifest(data: dict[str, Any], asset: Path | None = None) -> dict[str, Any]:
    unknown = sorted(set(data) - ALLOWED_KEYS)
    if unknown:
        fail("UNKNOWN_FIELDS", ", ".join(unknown))
    _validate_required_fields(data, REQUIRED)
    for key, expected in OPTIONAL_TYPES.items():
        if key in data and not _matches_type(data[key], expected):
            expected_name = expected.__name__ if isinstance(expected, type) else " or ".join(item.__name__ for item in expected)
            fail("INVALID_FIELD_TYPE", f"{key} must be {expected_name}")
    if data["schema_version"] != SCHEMA_VERSION:
        fail("UNSUPPORTED_SCHEMA_VERSION", str(data["schema_version"]))
    if data["profile"] not in SUPPORTED_PROFILES:
        fail("UNSUPPORTED_PROFILE", data["profile"])
    audio_only = (set(AUDIO_REQUIRED) - {"sha256"}) | {"instructions"}
    pptx_only = {"slide_count", "template_contract", "speaker_notes_policy", "derived_pdf_manifest_path", "derived_pdf_asset_id", "derived_pdf_sha256"}
    pdf_only = {"page_count", "embedded_object_policy", "annotation_policy", "filename_policy", "update_policy"}
    document_shared = {"source_format", "render_inspected", "render_evidence", "private_notes_removed"}
    if data["profile"] == "image":
        forbidden = audio_only | pptx_only | pdf_only | document_shared
        if any(key in data for key in forbidden):
            fail("IMAGE_PROFILE_FIELDS_FORBIDDEN", ", ".join(sorted(forbidden & set(data))))
        if data.get("visual_id") != data["asset_id"]:
            fail("IDENTITY_MISMATCH", "visual_id must equal asset_id for image profile v1")
        if data.get("remote_fonts") is not False:
            fail("REMOTE_FONTS_FORBIDDEN", "remote_fonts must be false")
    elif data["profile"] == "document_pdf":
        _validate_pdf_contract(data)
        forbidden = {"visual_id", "remote_fonts"} | audio_only | pptx_only
        if any(key in data for key in forbidden):
            fail("PDF_PROFILE_FIELDS_FORBIDDEN", ", ".join(sorted(forbidden & set(data))))
    elif data["profile"] == "audio":
        _validate_audio_contract(data)
        forbidden = {"visual_id", "remote_fonts"} | pptx_only | pdf_only | document_shared
        if any(key in data for key in forbidden):
            fail("AUDIO_PROFILE_FIELDS_FORBIDDEN", ", ".join(sorted(forbidden & set(data))))
    elif data["profile"] == "presentation_pptx":
        _validate_pptx_contract(data)
        forbidden = {"visual_id", "remote_fonts"} | audio_only | pdf_only
        if any(key in data for key in forbidden):
            fail("PPTX_PROFILE_FIELDS_FORBIDDEN", ", ".join(sorted(forbidden & set(data))))
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
    suffix = PurePosixPath(source_path).suffix.lower()
    expected_mime = MIME_BY_SUFFIX.get(suffix)
    if data["profile"] == "image" and expected_mime not in {"image/svg+xml", *PIL_FORMAT_BY_MIME}:
        fail("UNSUPPORTED_IMAGE_FORMAT", suffix or "missing suffix")
    if data["profile"] == "document_pdf" and suffix != ".pdf":
        fail("UNSUPPORTED_PDF_FORMAT", suffix or "missing suffix")
    if data["profile"] == "audio" and suffix != ".mp3":
        fail("UNSUPPORTED_AUDIO_FORMAT", suffix or "missing suffix")
    if data["profile"] == "presentation_pptx" and suffix != ".pptx":
        fail("UNSUPPORTED_PPTX_FORMAT", suffix or "missing suffix")
    if data["mime_type"] != expected_mime:
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
        if data["profile"] == "image":
            if asset.suffix.lower() == ".svg":
                try:
                    validate_svg(asset)
                except SvgValidationError as exc:
                    fail(exc.code, exc.message)
            else:
                validate_raster_image(asset, data["mime_type"])
        elif data["profile"] == "audio":
            try:
                validate_mp3_audio(asset)
            except AudioValidationError as exc:
                fail(exc.code, exc.message)
        # document_pdf and presentation_pptx intentionally stop at envelope validation here.
        # The owner/reviewer is responsible for document-content and structure review.
    return data


def normalize_legacy(
    legacy: dict[str, Any], *, project: str, contributor: str, source_class: str = "project_owned",
    license_id: str | None = None, sequence: int = 0, section_anchor: str | None = None,
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
    if not isinstance(license_id, str) or not license_id.strip():
        fail("LEGACY_LICENSE_MAPPING_REQUIRED", f"explicit license required for legacy rights: {legacy.get('rights')!r}")
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
        "public_safe": True, "guide_eligible": legacy_bool(legacy.get("guide_eligible"), "guide_eligible"),
        "external_resources": legacy_bool(legacy.get("external_resources"), "external_resources"),
        "scripts": legacy_bool(legacy.get("scripts"), "scripts"),
        "remote_fonts": legacy_bool(legacy.get("remote_fonts"), "remote_fonts"), "created_at": created_at,
    }
    if asset is not None:
        data["sha256"] = sha256(asset)
    return canonical(validate_manifest({key: value for key, value in data.items() if value is not None}, asset))


def normalize_pdf_legacy(
    legacy: dict[str, Any], *, project: str, contributor: str, content_id: str,
    source_repository: str, source_path: str, render_evidence: str, source_class: str = "project_owned",
    license_id: str | None = None, role: str = "document_companion", guide_eligible: bool = False,
    render_inspected: bool = False, private_notes_removed: bool = False, asset: Path | None = None,
) -> dict[str, Any]:
    unknown = sorted(set(legacy) - PDF_LEGACY_KEYS)
    if unknown:
        fail("UNKNOWN_LEGACY_FIELDS", ", ".join(unknown))
    required_values = {
        "asset_id": legacy.get("asset_id"), "content_id": content_id, "source_repository": source_repository,
        "source_path": source_path, "alt_text": legacy.get("alt_text"), "caption": legacy.get("caption"),
        "semantic_description": legacy.get("semantic_description"), "source_format": legacy.get("source_format"),
        "creation_method": legacy.get("creation_method"), "contributor": contributor, "render_evidence": render_evidence,
    }
    missing = [key for key, value in required_values.items() if not isinstance(value, str) or not value.strip()]
    if missing:
        fail("LEGACY_REQUIRED_FIELD_MISSING", ", ".join(missing))
    state = legacy.get("public_safety_state")
    if not isinstance(state, str) or state.strip().lower() not in SAFE_LEGACY_STATES:
        fail("LEGACY_PUBLIC_SAFETY_UNRECOGNIZED", repr(state))
    effective_license = license_id or legacy.get("license")
    if not isinstance(effective_license, str) or not effective_license.strip():
        fail("LEGACY_LICENSE_MAPPING_REQUIRED", repr(legacy.get("license")))
    pages = legacy.get("pages")
    if type(pages) is not int or pages <= 0:
        fail("PDF_PAGE_COUNT_INVALID", repr(pages))
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "profile": "document_pdf", "asset_id": legacy["asset_id"],
        "content_id": content_id, "source_class": source_class, "project": project,
        "source_repository": source_repository, "source_path": safe_path(source_path),
        "mime_type": mime_for(source_path), "role": role, "title": legacy.get("title"),
        "subtitle": legacy.get("subtitle"), "alt": legacy["alt_text"], "caption": legacy["caption"],
        "semantic_description": legacy["semantic_description"], "claims": legacy.get("claims"),
        "boundaries": legacy.get("boundaries"), "creation_method": legacy["creation_method"],
        "contributor": contributor, "license": effective_license, "public_safe": True,
        "guide_eligible": guide_eligible, "external_resources": False, "scripts": False,
        "page_count": pages, "source_format": legacy["source_format"], "render_inspected": render_inspected,
        "render_evidence": render_evidence, "private_notes_removed": private_notes_removed,
        "embedded_object_policy": "forbid", "annotation_policy": "forbid",
        "filename_policy": legacy.get("filename_policy"), "update_policy": legacy.get("update_policy"),
    }
    if asset is not None:
        data["sha256"] = sha256(asset)
    return canonical(validate_manifest({key: value for key, value in data.items() if value is not None}, asset))
