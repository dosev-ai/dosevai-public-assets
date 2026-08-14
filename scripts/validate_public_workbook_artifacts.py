#!/usr/bin/env python3
"""Validate public XLSX artifacts for active content and external workbook dependencies."""
from __future__ import annotations

import argparse
import json
import sys
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


def _xlsx_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.xlsx") if path.is_file())


def _has_external_relationship(xml_bytes: bytes) -> bool:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return False
    for rel in root.iter():
        if rel.attrib.get("TargetMode", "").lower() == "external":
            return True
    return False


def validate_xlsx(path: Path) -> dict[str, object]:
    findings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            lowered = [name.lower() for name in names]
            for name in lowered:
                for marker in FORBIDDEN_PART_MARKERS:
                    if marker in f"/{name}":
                        findings.append(f"forbidden_part:{name}")
            for name in names:
                if name.lower().endswith(".rels"):
                    if _has_external_relationship(archive.read(name)):
                        findings.append(f"external_relationship:{name}")
                if name.lower().endswith((".xml", ".rels", ".txt")):
                    data = archive.read(name).decode("utf-8", errors="ignore").lower()
                    for marker in FORBIDDEN_TEXT_MARKERS:
                        if marker in data:
                            findings.append(f"private_identifier_marker:{marker}:{name}")
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
