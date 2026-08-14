#!/usr/bin/env python3
"""Validate public XLSX artifacts against the formula-free public profile."""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
OFFICE_DOCUMENT_REL_TYPE = f"{OFFICE_REL_NS}/officeDocument"
WORKSHEET_REL_TYPE = f"{OFFICE_REL_NS}/worksheet"
WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
WORKSHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
FORBIDDEN_PART_MARKERS = (
    "vbaproject.bin",
    "/activex/",
    "/ctrlprops/",
    "/embeddings/",
    "/externallinks/",
    "/connections.xml",
    "/customui/",
    "/customxml/",
    "/macrosheets/",
    "/webextensions/",
    "/webextensions.xml",
    "/taskpanes/",
    "/taskpanes.xml",
)
FORBIDDEN_RELATIONSHIP_TYPE_TAILS = {
    "connections",
    "control",
    "ctrlprop",
    "externallink",
    "oleobject",
    "package",
    "querytable",
    "taskpane",
    "vbaproject",
    "webextension",
}
ALLOWED_PACKAGE_EXTENSIONS = {".xml", ".rels"}
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
    ".123",
    ".csv",
    ".dbf",
    ".dif",
    ".dqy",
    ".fods",
    ".gnumeric",
    ".iqy",
    ".numbers",
    ".odc",
    ".ods",
    ".oqy",
    ".ots",
    ".prn",
    ".rqy",
    ".slk",
    ".sxc",
    ".tsv",
    ".wk1",
    ".wk2",
    ".wk3",
    ".wk4",
    ".wks",
}
INDEXED_BASE_COLORS = {
    0: "000000",
    1: "FFFFFF",
    2: "FF0000",
    3: "00FF00",
    4: "0000FF",
    5: "FFFF00",
    6: "FF00FF",
    7: "00FFFF",
    8: "000000",
    9: "FFFFFF",
    10: "FF0000",
    11: "00FF00",
    12: "0000FF",
    13: "FFFF00",
    14: "FF00FF",
    15: "00FFFF",
}
THEME_BASE_COLORS = {
    "0": "FFFFFF",
    "1": "000000",
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


def _unsupported_spreadsheet_suffix(suffix: str) -> bool:
    normalized = suffix.lower()
    return (
        normalized in UNSUPPORTED_WORKBOOK_EXTENSIONS
        or (normalized.startswith(".xl") and normalized != ".xlsx")
    )


def _unsupported_workbook_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and _unsupported_spreadsheet_suffix(path.suffix)
    )


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _local_name(tag: str) -> str:
    return _split_tag(tag)[1]


def _direct_children(root: ET.Element, namespace: str, local: str) -> list[ET.Element]:
    return [
        child
        for child in list(root)
        if _split_tag(child.tag) == (namespace, local)
    ]


def _workbook_sheet_elements(root: ET.Element) -> list[ET.Element]:
    sheets_containers = _direct_children(root, SPREADSHEET_NS, "sheets")
    if len(sheets_containers) != 1:
        return []
    return _direct_children(sheets_containers[0], SPREADSHEET_NS, "sheet")


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


def _relationship_type_tail(type_uri: str) -> str:
    return type_uri.rstrip("/").rsplit("/", 1)[-1].lower()


def _relationship_records(root: ET.Element) -> list[tuple[str, str, str, str]]:
    records: list[tuple[str, str, str, str]] = []
    for rel in _direct_children(root, PACKAGE_RELS_NS, "Relationship"):
        records.append(
            (
                rel.attrib.get("Id", "").strip(),
                rel.attrib.get("Type", "").strip(),
                rel.attrib.get("Target", "").strip(),
                rel.attrib.get("TargetMode", "").strip(),
            )
        )
    return records


def _relationship_violation(root: ET.Element) -> str | None:
    for _, type_uri, target, target_mode in _relationship_records(root):
        type_tail = _relationship_type_tail(type_uri)
        if type_tail in FORBIDDEN_RELATIONSHIP_TYPE_TAILS:
            return f"active_type:{type_tail}"
        if target_mode.lower() == "external":
            return "target_mode"
        if target.startswith(("//", "\\\\")):
            return "network_path"
        if "\\" in target or "\x00" in target:
            return "unsafe_target_syntax"
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


def _color_descriptor(element: ET.Element | None) -> tuple[str, str] | None:
    if element is None:
        return None

    rgb = element.attrib.get("rgb")
    if rgb is not None:
        value = rgb.strip().upper()
        return "rgb", value[-6:] if len(value) >= 6 else value

    theme = element.attrib.get("theme")
    if theme is not None:
        value = theme.strip()
        if value in THEME_BASE_COLORS:
            return "rgb", THEME_BASE_COLORS[value]
        return "theme", value.upper()

    indexed = element.attrib.get("indexed")
    if indexed is not None:
        value = indexed.strip()
        try:
            index = int(value)
        except ValueError:
            return "indexed", value.upper()
        if index in INDEXED_BASE_COLORS:
            return "rgb", INDEXED_BASE_COLORS[index]
        return "indexed", str(index)

    return None


def _font_color(font: ET.Element) -> tuple[str, str] | None:
    colors = _direct_children(font, SPREADSHEET_NS, "color")
    return _color_descriptor(colors[0]) if colors else None


def _fill_color(fill: ET.Element) -> tuple[str, str] | None:
    pattern_fills = _direct_children(fill, SPREADSHEET_NS, "patternFill")
    if not pattern_fills:
        return None
    pattern_fill = pattern_fills[0]
    pattern_type = pattern_fill.attrib.get("patternType", "").strip().lower()
    if pattern_type not in {"solid"}:
        return None
    colors = _direct_children(pattern_fill, SPREADSHEET_NS, "fgColor")
    return _color_descriptor(colors[0]) if colors else None


def _is_light_background_color(color: tuple[str, str] | None) -> bool:
    if color is None:
        return True
    kind, value = color
    if kind == "theme":
        return value == "0"
    if kind == "indexed":
        return value in {"1", "9"}
    if kind == "rgb":
        return value[-6:] == "FFFFFF"
    return False


def _style_profile_violation(root: ET.Element) -> str | None:
    namespace, local = _split_tag(root.tag)
    if (namespace, local) != (SPREADSHEET_NS, "styleSheet"):
        return None

    num_fmts = _direct_children(root, SPREADSHEET_NS, "numFmts")
    if any(_direct_children(container, SPREADSHEET_NS, "numFmt") for container in num_fmts):
        return "custom_number_format"

    if any(_local_name(element.tag) == "dxf" for element in root.iter()):
        return "differential_style"

    fonts_containers = _direct_children(root, SPREADSHEET_NS, "fonts")
    fills_containers = _direct_children(root, SPREADSHEET_NS, "fills")
    cell_xfs_containers = _direct_children(root, SPREADSHEET_NS, "cellXfs")
    if not fonts_containers or not fills_containers or not cell_xfs_containers:
        return None

    fonts = _direct_children(fonts_containers[0], SPREADSHEET_NS, "font")
    fills = _direct_children(fills_containers[0], SPREADSHEET_NS, "fill")
    cell_xfs = _direct_children(cell_xfs_containers[0], SPREADSHEET_NS, "xf")
    font_colors = [_font_color(font) for font in fonts]
    fill_colors = [_fill_color(fill) for fill in fills]

    for xf in cell_xfs:
        try:
            font_id = int(xf.attrib.get("fontId", "0"))
            fill_id = int(xf.attrib.get("fillId", "0"))
        except ValueError:
            continue
        if not (0 <= font_id < len(font_colors)):
            continue
        font_color = font_colors[font_id]
        fill_color = fill_colors[fill_id] if 0 <= fill_id < len(fill_colors) else None
        if font_color is not None and fill_color is not None and font_color == fill_color:
            return "font_matches_fill"
        if _is_light_background_color(fill_color) and _is_light_background_color(font_color) and font_color is not None:
            return "light_font_on_light_background"
    return None


def _hidden_sheet_state(root: ET.Element) -> str | None:
    for element in _workbook_sheet_elements(root):
        state = element.attrib.get("state", "visible").strip().lower()
        if state not in ("", "visible"):
            return state
    return None


def _zero_or_negative_dimension(value: str) -> bool:
    if not value.strip():
        return False
    try:
        return float(value) <= 0
    except ValueError:
        return False


def _hidden_worksheet_content(root: ET.Element) -> str | None:
    for element in root.iter():
        local = _local_name(element.tag)
        if local == "conditionalFormatting":
            return "conditional_formatting"
        if local in {"row", "col"}:
            hidden = element.attrib.get("hidden", "").strip().lower()
            if hidden in {"1", "true"}:
                return local
            dimension_attr = "ht" if local == "row" else "width"
            if _zero_or_negative_dimension(element.attrib.get(dimension_attr, "")):
                return local
        if local == "sheetFormatPr":
            zero_height = element.attrib.get("zeroHeight", "").strip().lower()
            if zero_height in {"1", "true"}:
                return "default_rows"
    return None


def _normalized_text(data: bytes, parsed_root: ET.Element | None) -> str:
    if parsed_root is not None:
        chunks = [
            "".join(element.itertext())
            for element in parsed_root.iter()
            if _local_name(element.tag) in TEXT_CONTAINER_NAMES
        ]
        chunks.extend(
            value
            for element in parsed_root.iter()
            for value in element.attrib.values()
        )
        chunks.append("".join(parsed_root.itertext()))
        return "\n".join(chunks).lower().replace("\x00", "")
    return data.decode("latin-1", errors="ignore").lower().replace("\x00", "")


def _private_findings(text: str, location: str) -> list[str]:
    findings: list[str] = []
    for marker in FORBIDDEN_TEXT_MARKERS:
        if marker in text:
            findings.append(f"private_identifier_marker:{marker}:{location}")
    for match in PRIVATE_ID_RE.finditer(text):
        findings.append(f"private_identifier_pattern:{match.group(0)}:{location}")
    return findings


def _has_forbidden_xml_declaration(data: bytes) -> bool:
    probe = data.lower().replace(b"\x00", b"")
    return any(marker in probe for marker in XML_DECLARATION_MARKERS)


def _expected_root_finding(part_name: str, root: ET.Element) -> str | None:
    namespace, local = _split_tag(root.tag)
    if part_name == "[content_types].xml":
        expected = (CONTENT_TYPES_NS, "Types")
    elif part_name in ("_rels/.rels", "xl/_rels/workbook.xml.rels"):
        expected = (PACKAGE_RELS_NS, "Relationships")
    elif part_name == "xl/workbook.xml":
        expected = (SPREADSHEET_NS, "workbook")
    elif part_name == "xl/styles.xml":
        expected = (SPREADSHEET_NS, "styleSheet")
    elif part_name.startswith("xl/worksheets/") and part_name.endswith(".xml"):
        expected = (SPREADSHEET_NS, "worksheet")
    else:
        return None
    if (namespace, local) != expected:
        return f"invalid_ooxml_root:{part_name}:{namespace}:{local}"
    return None


def _resolve_internal_target(source_part: str, target: str) -> str:
    normalized_target = target.replace("\\", "/")
    if normalized_target.startswith("/"):
        return normalized_target.lstrip("/").lower()
    base_dir = posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base_dir, normalized_target)).lower()


def _validate_content_types(
    root: ET.Element | None,
    package_parts: set[str],
) -> list[str]:
    if root is None:
        return []
    overrides: dict[str, str] = {}
    for element in _direct_children(root, CONTENT_TYPES_NS, "Override"):
        part_name = element.attrib.get("PartName", "").lstrip("/").lower()
        content_type = element.attrib.get("ContentType", "")
        overrides[part_name] = content_type
    findings: list[str] = []
    if overrides.get("xl/workbook.xml") != WORKBOOK_CONTENT_TYPE:
        findings.append("invalid_content_type:xl/workbook.xml")
    worksheet_parts = sorted(
        part
        for part in package_parts
        if part.startswith("xl/worksheets/") and part.endswith(".xml")
    )
    for worksheet_part in worksheet_parts:
        if overrides.get(worksheet_part) != WORKSHEET_CONTENT_TYPE:
            findings.append(f"invalid_content_type:{worksheet_part}")
    return findings


def _validate_relationship_graph(
    parsed_parts: dict[str, ET.Element],
    package_parts: set[str],
) -> list[str]:
    findings: list[str] = []
    root_rels = parsed_parts.get("_rels/.rels")
    if root_rels is not None:
        office_targets = [
            target
            for _, type_uri, target, _ in _relationship_records(root_rels)
            if type_uri == OFFICE_DOCUMENT_REL_TYPE
        ]
        if not any(
            _resolve_internal_target("", target) == "xl/workbook.xml"
            for target in office_targets
        ):
            findings.append("missing_office_document_relationship:xl/workbook.xml")

    workbook_rels = parsed_parts.get("xl/_rels/workbook.xml.rels")
    worksheet_by_id: dict[str, str] = {}
    if workbook_rels is not None:
        for rel_id, type_uri, target, target_mode in _relationship_records(workbook_rels):
            if type_uri != WORKSHEET_REL_TYPE:
                continue
            if target_mode.lower() == "external":
                continue
            resolved = _resolve_internal_target("xl/workbook.xml", target)
            worksheet_by_id[rel_id] = resolved
            if not (
                resolved.startswith("xl/worksheets/")
                and resolved.endswith(".xml")
            ):
                findings.append(f"invalid_worksheet_relationship_target:{resolved}")
            if resolved not in package_parts:
                findings.append(f"missing_relationship_target:{resolved}")
        if not worksheet_by_id:
            findings.append("missing_workbook_worksheet_relationship")

    workbook_root = parsed_parts.get("xl/workbook.xml")
    if workbook_root is not None:
        sheet_rel_ids: list[str] = []
        for element in _workbook_sheet_elements(workbook_root):
            rel_id = ""
            for key, value in element.attrib.items():
                namespace, local = _split_tag(key)
                if local == "id" and namespace == OFFICE_REL_NS:
                    rel_id = value
                    break
            if not rel_id:
                findings.append("sheet_missing_relationship_id")
            else:
                sheet_rel_ids.append(rel_id)
        if not sheet_rel_ids:
            findings.append("workbook_has_no_sheets")
        for rel_id in sheet_rel_ids:
            if rel_id not in worksheet_by_id:
                findings.append(f"sheet_relationship_not_found:{rel_id}")
    return findings


def validate_xlsx(path: Path) -> dict[str, object]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            lowered = [name.lower() for name in names]
            lowered_set = set(lowered)
            normalized_names = [_normalized_part_name(name) for name in names]

            findings.extend(
                _private_findings(
                    _normalized_text(archive.comment, None),
                    "archive_comment",
                )
            )

            if len(normalized_names) != len(set(normalized_names)):
                seen: set[str] = set()
                duplicates: set[str] = set()
                for normalized in normalized_names:
                    if normalized in seen:
                        duplicates.add(normalized)
                    seen.add(normalized)
                for duplicate in sorted(duplicates):
                    findings.append(f"duplicate_or_case_colliding_part:{duplicate}")

            for info in infos:
                if _unsafe_part_name(info.filename):
                    findings.append(f"unsafe_package_part_name:{info.filename}")
                if not info.filename.endswith("/"):
                    lower_filename = info.filename.lower()
                    extension = (
                        ".rels"
                        if lower_filename.endswith(".rels")
                        else posixpath.splitext(lower_filename)[1]
                    )
                    if extension not in ALLOWED_PACKAGE_EXTENSIONS:
                        findings.append(
                            f"non_xml_package_part_not_allowed:{info.filename}"
                        )
                metadata_text = "\n".join(
                    (
                        info.filename.lower().replace("\x00", ""),
                        _normalized_text(info.comment, None),
                        _normalized_text(info.extra, None),
                    )
                )
                findings.extend(_private_findings(metadata_text, f"metadata:{info.filename}"))

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

            parsed_parts: dict[str, ET.Element] = {}
            for name in names:
                if name in unsafe_members:
                    continue

                lower_name = name.lower()
                try:
                    data = archive.read(name)
                except (RuntimeError, zipfile.BadZipFile, OSError, KeyError) as exc:
                    findings.append(f"unreadable_package_part:{name}:{type(exc).__name__}")
                    continue

                parsed_root: ET.Element | None = None
                raw_text = _normalized_text(data, None)
                findings.extend(_private_findings(raw_text, name))

                if lower_name.endswith((".xml", ".rels")):
                    if _has_forbidden_xml_declaration(data):
                        findings.append(f"forbidden_xml_declaration:{name}")
                    else:
                        try:
                            parsed_root = ET.fromstring(data)
                            parsed_parts[lower_name] = parsed_root
                            root_finding = _expected_root_finding(lower_name, parsed_root)
                            if root_finding:
                                findings.append(root_finding)
                        except ET.ParseError:
                            findings.append(f"invalid_xml:{name}")

                if lower_name.endswith(".rels") and parsed_root is not None:
                    relationship_violation = _relationship_violation(parsed_root)
                    if relationship_violation:
                        findings.append(
                            f"external_or_active_relationship:{relationship_violation}:{name}"
                        )

                if parsed_root is not None:
                    formula_violation = _formula_profile_violation(parsed_root)
                    if formula_violation:
                        findings.append(
                            f"formula_not_allowed:{formula_violation}:{name}"
                        )
                    style_violation = _style_profile_violation(parsed_root)
                    if style_violation:
                        findings.append(
                            f"display_suppressing_style_not_allowed:{style_violation}:{name}"
                        )

                if lower_name == "xl/workbook.xml" and parsed_root is not None:
                    hidden_state = _hidden_sheet_state(parsed_root)
                    if hidden_state:
                        findings.append(f"hidden_sheet_not_allowed:{hidden_state}:{name}")

                if (
                    lower_name.startswith("xl/worksheets/")
                    and lower_name.endswith(".xml")
                    and parsed_root is not None
                ):
                    hidden_content = _hidden_worksheet_content(parsed_root)
                    if hidden_content:
                        findings.append(
                            f"hidden_worksheet_content_not_allowed:{hidden_content}:{name}"
                        )

                if lower_name.endswith((".xml", ".rels", ".txt")):
                    normalized = _normalized_text(data, parsed_root)
                    findings.extend(_private_findings(normalized, name))

            findings.extend(
                _validate_content_types(
                    parsed_parts.get("[content_types].xml"),
                    lowered_set,
                )
            )
            findings.extend(_validate_relationship_graph(parsed_parts, lowered_set))
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
