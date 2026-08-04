#!/usr/bin/env python3
"""Generate, normalize, inspect, validate, and audit governed asset manifests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asset_manifest_audit import audit_repository, format_audit_text
from asset_manifest_core import (
    ManifestError, canonical, dump_manifest, load_mapping, normalize_legacy, sha256, validate_manifest,
)


def add_asset(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument("--asset", type=Path, required=required)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="asset_manifest.py")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("manifest", type=Path)
    add_asset(validate, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("manifest", type=Path)
    add_asset(inspect, required=False)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("manifest", type=Path)
    normalize.add_argument("--output", type=Path, required=True)
    normalize.add_argument("--project", required=True)
    normalize.add_argument("--contributor", required=True)
    normalize.add_argument("--source-class", default="project_owned")
    normalize.add_argument("--license", dest="license_id")
    normalize.add_argument("--sequence", type=int, default=0)
    normalize.add_argument("--section-anchor")
    normalize.add_argument("--step-key")
    add_asset(normalize, required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("metadata", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    add_asset(generate, required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--root", type=Path, default=Path("."))
    audit.add_argument("--include", action="append", dest="include_roots")
    audit.add_argument("--format", choices=("json", "text"), default="json")
    audit.add_argument("--expected-repository")
    audit.add_argument("--output", type=Path)
    audit.add_argument("--allow-findings", action="store_true")
    audit.add_argument(
        "--allow-status",
        action="append",
        choices=("repair", "missing_manifest", "orphan_manifest", "unsupported_profile", "unsafe"),
        default=[],
    )
    return parser.parse_args(argv)


def write_output(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_manifest(data), encoding="utf-8")


def _emit_audit(args: argparse.Namespace, report: dict) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_audit_text(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command in {"validate", "inspect"}:
            data = validate_manifest(load_mapping(args.manifest), args.asset)
            result = {
                "ok": True, "asset_id": data["asset_id"], "content_id": data["content_id"],
                "profile": data["profile"], "role": data["role"], "source_path": data["source_path"],
                "mime_type": data["mime_type"], "sha256": data.get("sha256"), "public_safe": data["public_safe"],
            }
            print(json.dumps(result, indent=2 if args.command == "inspect" else None, sort_keys=True))
        elif args.command == "normalize":
            data = normalize_legacy(
                load_mapping(args.manifest), project=args.project, contributor=args.contributor,
                source_class=args.source_class, license_id=args.license_id, sequence=args.sequence,
                section_anchor=args.section_anchor, step_key=args.step_key, asset=args.asset,
            )
            write_output(args.output, data)
            print(json.dumps({"ok": True, "output": str(args.output), "asset_id": data["asset_id"]}, sort_keys=True))
        elif args.command == "audit":
            report = audit_repository(args.root, args.include_roots, args.expected_repository)
            allowed_statuses = sorted(set(args.allow_status))
            blocking_findings = [
                item for item in report["items"]
                if item["status"] != "pass" and item["status"] not in allowed_statuses
            ]
            report["allowed_statuses"] = allowed_statuses
            report["blocking_finding_count"] = len(blocking_findings)
            report["gate_ok"] = not blocking_findings
            _emit_audit(args, report)
            return 0 if args.allow_findings or report["gate_ok"] else 2
        else:
            data = load_mapping(args.metadata)
            if args.asset is not None:
                data["sha256"] = sha256(args.asset)
            data = canonical(validate_manifest(data, args.asset))
            write_output(args.output, data)
            print(json.dumps({"ok": True, "output": str(args.output), "asset_id": data["asset_id"]}, sort_keys=True))
        return 0
    except ManifestError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "message": exc.message}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
