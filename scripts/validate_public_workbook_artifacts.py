#!/usr/bin/env python3
"""Validate public XLSX artifacts against the formula-free public profile."""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

FORBIDDEN_PART_MARKERS = (
    "vbaproject.bin",
    "/activex/",
    "/ctrlprops/",
    "/embeddings/",
    "/externallinks/",
    "/connections.xml",
    "/customui/",
    "/macrosheets/",
    "/webextensions/",
    "/webextensions.xml",
    "/taskpanes/",
    "/taskpanes.xml",
)
FORBIDDEN_TEXT_MARKERS = ("cortex://",)
PRIVATE_ID_RE = re.compile(
    r"\b(?:action|project|fact)-\d{10,}[A-Za-z0-9-]*\b",
    re.IGNORECASE,
)
EXTERNAL_TARGET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
REQUIRED_PARTS = (
    "[content_types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
)
UNSUPPORTED_WORKBOOK_EXTENSIONS = {
    ".xls",
    ".xlsb",
    ".xlsm",
    ".xlam",
    ".xlt",
    ".xltm",
    ".xltx",
}
XML_DECLARATION_MARKERS = (b"<!doctype", b"<!entity")
TEXT_CONTAINER_NAMES = {"si", "is", "text", "definedName", "f", "t"}
MAX_ARCHIVE_ENTRIES = 2048
MAX_MEMBER_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


def _xlsx_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".xlsx"
    )


def _unsupported_workbook_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in UNSUPPORTED_WORKBOOK_EXTENSIONS
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalized_part_name(name: str) -> str:
    return name.replace("\\", "/").lower()


def _unsafe_part_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    return (
        "\x00" in name
        or "\\" in name
        or normalized.startswith("/")
        or any(part == ".." for part in parts)
    )


def _external_relationship_reason(root: ET.Element) -> str | None:
    for rel in root.iter():
        if _local_name(rel.tag) != "Relationship":
            continue
        target_mode = rel.attrib.get("TargetMode", "").strip().lower()
        target = rel.attrib.get("Target", "").strip()
        if target_mode == "external":
            return "target_mode"
        if target.startswith(("//", "\\\\")):
            return "network_path"
        if EXTERNAL_TARGET_RE.match(target):
            return "absolute_uri"
    return None


def _formula_profile_violation(root: ET.Element) -> str | None:
    for element in root.iter():
        local = _local_name(element.tag)
        text = "".join(element.itertext()).strip()
        if local == "f" or "formula" in local.lower():
            return local
        if local == "definedName" and text:
            return "definedName"
    return None


def _hidden_sheet_state(root: ET.Element) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) != "sheet":
            continue
        state = element.attrib.get("state", "visible").strip().lower()
        if state not in ("", "visible"):
            return state
    return None


def _normalized_text(data: bytes, parsed_root: ET.Element | None) -> str:
    if parsed_root is not None:
        chunks = [
            "".join(element.itertext())
            for element in parsed_root.iter()
            if _local_name(element.tag) in TEXT_CONTAINER_NAMES
        ]
        chunks.append("".join(parsed_root.itertext()))
        return "\n".join(chunks).lower().replace("\x00", "")
    return data.decode("utf-8", errors="ignore").lower().replace("\x00", "")


def _has_forbidden_xml_declaration(data: bytes) -> bool:
    probe = data.lower().replace(b"\x00", b"")
    return any(marker in probe for marker in XML_DECLARATION_MARKERS)


def validate_xlsx(path: Path) -> dict[str, object]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            lowered = [name.lower() for name in names]
            lowered_set = set(lowered)
            normalized_names = [_normalized_part_name(name) for name in names]

            if len(normalized_names) != len(set(normalized_names)):
                seen: set[str] = set()
                duplicates: set[str] = set()
                for normalized in normalized_names:
                    if normalized in seen:
                        duplicates.add(normalized)
                    seen.add(normalized)
                for duplicate in sorted(duplicates):
                    findings.append(f"duplicate_or_case_colliding_part:{duplicate}")

            for name in names:
                if _unsafe_part_name(name):
                    findings.append(f"unsafe_package_part_name:{name}")

            if len(infos) > MAX_ARCHIVE_ENTRIES:
                findings.append(f"too_many_archive_entries:{len(infos)}")

            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                findings.append(f"archive_uncompressed_size_limit:{total_uncompressed}")

            unsafe_members: set[str] = set()
            for info in infos:
                if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                    findings.append(
                        f"member_uncompressed_size_limit:{info.filename}:{info.file_size}"
                    )
                    unsafe_members.add(info.filename)
                if info.file_size and info.compress_size:
                    ratio = info.file_size / info.compress_size
                    if ratio > MAX_COMPRESSION_RATIO:
                        findings.append(
                            f"member_compression_ratio_limit:{info.filename}:{ratio:.1f}"
                        )
                        unsafe_members.add(info.filename)

            for required in REQUIRED_PARTS:
                if required not in lowered_set:
                    findings.append(f"missing_required_part:{required}")
            if not any(
                name.startswith("xl/worksheets/") and name.endswith(".xml")
                for name in lowered
            ):
                findings.append("missing_required_part:xl/worksheets/*.xml")

            for name in lowered:
                for marker in FORBIDDEN_PART_MARKERS:
                    if marker in f"/{name}":
                        findings.append(f"forbidden_part:{name}")

            if (
                len(infos) > MAX_ARCHIVE_ENTRIES
                or total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES
            ):
                return {
                    "path": path.as_posix(),
                    "ok": False,
                    "findings": sorted(set(findings)),
                }

            for name in names:
                if name in unsafe_members:
                    continue

                lower_name = name.lower()
                data = archive.read(name)
                parsed_root: ET.Element | None = None

                if lower_name.endswith((".xml", ".rels")):
                    if _has_forbidden_xml_declaration(data):
                        findings.append(f"forbidden_xml_declaration:{name}")
                    else:
                        try:
                            parsed_root = ET.fromstring(data)
                        except ET.ParseError:
                            findings.append(f"invalid_xml:{name}")

                if lower_name.endswith(".rels") and parsed_root is not None:
                    external_reason = _external_relationship_reason(parsed_root)
                    if external_reason:
                        findings.append(f"external_relationship:{external_reason}:{name}")

                if parsed_root is not None:
                    formula_violation = _formula_profile_violation(parsed_root)
                    if formula_violation:
                        findings.append(
                            f"formula_not_allowed:{formula_violation}:{name}"
                        )

                if lower_name == "xl/workbook.xml" and parsed_root is not None:
                    hidden_state = _hidden_sheet_state(parsed_root)
                    if hidden_state:
                        findings.append(f"hidden_sheet_not_allowed:{hidden_state}:{name}")

                if lower_name.endswith((".xml", ".rels", ".txt")):
                    text = _normalized_text(data, parsed_root)
                    for marker in FORBIDDEN_TEXT_MARKERS:
                        if marker in text:
                            findings.append(
                                f"private_identifier_marker:{marker}:{name}"
                            )
                    private_id = PRIVATE_ID_RE.search(text)
                    if private_id:
                        findings.append(
                            f"private_identifier_pattern:{private_id.group(0)}:{name}"
                        )
    except zipfile.BadZipFile:
        findings.append("invalid_xlsx_zip")

    return {
        "path": path.as_posix(),
        "ok": not findings,
        "findings": sorted(set(findings)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("artifacts"))
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)

    files = _xlsx_files(args.root)
    unsupported = _unsupported_workbook_files(args.root)
    results = [validate_xlsx(path) for path in files]
    results.extend(
        {
            "path": path.as_posix(),
            "ok": False,
            "findings": [f"unsupported_workbook_extension:{path.suffix.lower()}"],
        }
        for path in unsupported
    )
    ok = bool(files) and not unsupported and all(bool(item["ok"]) for item in results)
    payload = {
        "ok": ok,
        "xlsx_count": len(files),
        "unsupported_workbook_count": len(unsupported),
        "results": results,
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "public workbook validation: "
            f"{'PASS' if ok else 'FAIL'} ({len(files)} xlsx, {len(unsupported)} unsupported)"
        )
        for item in results:
            status = "PASS" if item["ok"] else "FAIL"
            print(f"- {status} {item['path']}")
            for finding in item["findings"]:
                print(f"  - {finding}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
