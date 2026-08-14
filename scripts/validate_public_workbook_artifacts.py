#!/usr/bin/env python3
"""Validate public XLSX artifacts for active content and external dependencies."""
from __future__ import annotations

import argparse
import json
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
)
FORBIDDEN_TEXT_MARKERS = (
    "cortex://",
    "action-17",
    "project-17",
    "fact-17",
)
REQUIRED_PARTS = (
    "[content_types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
)
NETWORK_FORMULA_MARKERS = (
    "WEBSERVICE(",
    "HYPERLINK(",
    "IMAGE(",
    "RTD(",
    "STOCKHISTORY(",
)
FORMULA_ELEMENT_NAMES = {"f", "definedName"}
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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _has_external_relationship(root: ET.Element) -> bool:
    return any(
        rel.attrib.get("TargetMode", "").lower() == "external"
        for rel in root.iter()
    )


def _network_formula(root: ET.Element) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) not in FORMULA_ELEMENT_NAMES:
            continue
        formula = "".join(element.itertext()).upper()
        for marker in NETWORK_FORMULA_MARKERS:
            if marker in formula:
                return marker.rstrip("(").lower()
    return None


def _normalized_text(data: bytes, parsed_root: ET.Element | None) -> str:
    if parsed_root is not None:
        return ET.tostring(parsed_root, encoding="unicode").lower().replace("\x00", "")
    return data.decode("utf-8", errors="ignore").lower().replace("\x00", "")


def validate_xlsx(path: Path) -> dict[str, object]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            lowered = [name.lower() for name in names]
            lowered_set = set(lowered)

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
                    try:
                        parsed_root = ET.fromstring(data)
                    except ET.ParseError:
                        findings.append(f"invalid_xml:{name}")

                if lower_name.endswith(".rels") and parsed_root is not None:
                    if _has_external_relationship(parsed_root):
                        findings.append(f"external_relationship:{name}")

                if (
                    lower_name == "xl/workbook.xml"
                    or (
                        lower_name.startswith("xl/worksheets/")
                        and lower_name.endswith(".xml")
                    )
                ) and parsed_root is not None:
                    network_function = _network_formula(parsed_root)
                    if network_function:
                        findings.append(
                            f"network_capable_formula:{network_function}:{name}"
                        )

                if lower_name.endswith((".xml", ".rels", ".txt")):
                    text = _normalized_text(data, parsed_root)
                    for marker in FORBIDDEN_TEXT_MARKERS:
                        if marker in text:
                            findings.append(
                                f"private_identifier_marker:{marker}:{name}"
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
    results = [validate_xlsx(path) for path in files]
    ok = bool(files) and all(bool(item["ok"]) for item in results)
    payload = {"ok": ok, "xlsx_count": len(files), "results": results}
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"public workbook validation: {'PASS' if ok else 'FAIL'} ({len(files)} xlsx)")
        for item in results:
            status = "PASS" if item["ok"] else "FAIL"
            print(f"- {status} {item['path']}")
            for finding in item["findings"]:
                print(f"  - {finding}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
