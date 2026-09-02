#!/usr/bin/env python3
"""Prepare governed SVG packages for one definitive external-review candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "scripts" / "asset_manifest.py"
SVG_NS = "http://www.w3.org/2000/svg"
DEFAULT_FONT_FAMILY = "DejaVu Sans"
DEFAULT_WIDTHS = (("full", 1600), ("card", 800), ("mobile", 480))


def manifest_for(svg: Path) -> Path:
    return svg.with_name(f"{svg.stem}.manifest.yaml")


def run_packager(svg: Path, manifest: Path) -> None:
    if not manifest.is_file():
        raise FileNotFoundError(f"adjacent manifest missing: {manifest}")
    generate = [
        sys.executable,
        str(PACKAGER),
        "generate",
        str(manifest),
        "--output",
        str(manifest),
        "--asset",
        str(svg),
    ]
    validate = [
        sys.executable,
        str(PACKAGER),
        "validate",
        str(manifest),
        "--asset",
        str(svg),
    ]
    subprocess.run(generate, cwd=ROOT, check=True)
    subprocess.run(validate, cwd=ROOT, check=True)


def fallback_svg_bytes(svg: Path, font_family: str) -> bytes:
    try:
        root = ET.fromstring(svg.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, ET.ParseError) as exc:
        raise ValueError(f"cannot prepare fallback-font SVG: {exc}") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise ValueError("SVG namespace/root required")
    style = ET.Element(f"{{{SVG_NS}}}style", {"id": "preflight-fallback-font"})
    escaped = font_family.replace("\\", "\\\\").replace('"', '\\"')
    style.text = f'text, tspan {{ font-family: "{escaped}", sans-serif !important; }}'
    root.append(style)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def preview_root(svg: Path, output_dir: Path) -> Path:
    """Return a collision-safe preview directory for one source SVG."""
    try:
        relative = svg.relative_to(ROOT)
        return output_dir / relative.parent
    except ValueError:
        parent_key = hashlib.sha256(str(svg.parent).encode("utf-8")).hexdigest()[:12]
        return output_dir / "external" / parent_key


def render_previews(svg: Path, output_dir: Path, font_family: str) -> list[dict[str, object]]:
    target_dir = preview_root(svg, output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    prepared = fallback_svg_bytes(svg, font_family)
    previews: list[dict[str, object]] = []
    for label, width in DEFAULT_WIDTHS:
        output = target_dir / f"{svg.stem}-fallback-{label}.png"
        cairosvg.svg2png(bytestring=prepared, write_to=str(output), output_width=width)
        with Image.open(output) as image:
            image.load()
            actual_width, actual_height = image.size
        if actual_width != width or actual_height <= 0:
            raise ValueError(f"unexpected preview dimensions for {label}: {actual_width}x{actual_height}")
        previews.append({
            "label": label,
            "path": str(output),
            "width": actual_width,
            "height": actual_height,
        })
    return previews


def preflight(svg: Path, output_dir: Path, font_family: str) -> dict[str, object]:
    svg = svg.resolve()
    if svg.suffix.lower() != ".svg":
        raise ValueError(f"SVG required: {svg}")
    manifest = manifest_for(svg)
    run_packager(svg, manifest)
    previews = render_previews(svg, output_dir, font_family)
    return {
        "asset": str(svg),
        "manifest": str(manifest),
        "font_profile": font_family,
        "previews": previews,
        "inspection_required": True,
        "inspection_scope": [
            "headline and lead copy",
            "every bounded label and card/panel title",
            "lane/body summaries and checkpoint text",
            "footer, review question, and edge-adjacent text",
            "the full artifact again after any representative text-fit repair",
        ],
        "package_refreshed_from_exact_bytes": True,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh each adjacent governed manifest from exact SVG bytes, validate the package, "
            "and render standardized fallback-font previews for a whole-artifact inspection pass."
        )
    )
    parser.add_argument("svg", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, default=Path(".preflight/svg"))
    parser.add_argument("--font-family", default=DEFAULT_FONT_FAMILY)
    parser.add_argument("--report", type=Path, default=Path(".preflight/svg/report.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        results = [preflight(svg, args.output_dir, args.font_family) for svg in args.svg]
        preview_paths = [item["path"] for result in results for item in result["previews"]]
        if len(preview_paths) != len(set(preview_paths)):
            raise ValueError("preview path collision detected")
        report = {
            "ok": True,
            "schema_version": 1,
            "results": results,
            "next_gate": "inspect every generated preview as one same-class sweep before external review",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
