#!/usr/bin/env python3
"""Generate, normalize, inspect, and validate governed asset manifests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asset_manifest_core import (
    ManifestError, canonical, dump_manifest, load_mapping, normalize_legacy, sha256, validate_manifest,
)


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asset", type=Path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="asset_manifest.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "inspect"):
        item = commands.add_parser(name)
        item.add_argument("manifest", type=Path)
        common(item)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("manifest", type=Path)
    normalize.add_argument("--output", type=Path, required=True)
    normalize.add_argument("--project", required=True)
    normalize.add_argument("--contributor", required=True)
    normalize.add_argument("--source-class", default="project_owned")
    normalize.add_argument("--license", dest="license_id", default="CC0-1.0")
    normalize.add_argument("--sequence", type=int, default=0)
    normalize.add_argument("--section-anchor")
    normalize.add_argument("--step-key")
    common(normalize)
    generate = commands.add_parser("generate")
    generate.add_argument("metadata", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    common(generate)
    return parser.parse_args(argv)


def write_output(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_manifest(data), encoding="utf-8")


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
