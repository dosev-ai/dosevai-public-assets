"""Fail-closed validation for self-contained SVG assets."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

XINCLUDE = "http://www.w3.org/2001/XInclude"
FORBIDDEN_ELEMENTS = {"script", "foreignObject", "image", "animate", "animateMotion", "animateTransform", "set"}
RAW_PATTERNS = {
    "SVG_DTD_FORBIDDEN": re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.I),
    "SVG_PROCESSING_INSTRUCTION_FORBIDDEN": re.compile(r"<\?(?!xml\s)[^>]*\?>", re.I),
    "SVG_JAVASCRIPT_FORBIDDEN": re.compile(r"javascript\s*:", re.I),
    "SVG_CSS_IMPORT_FORBIDDEN": re.compile(r"@import\b", re.I),
    "SVG_EXTERNAL_CSS_URL_FORBIDDEN": re.compile(r"url\(\s*['\"]?(?:https?:|//|data:|javascript:)", re.I),
}


class SvgValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def reject(code: str, message: str) -> None:
    raise SvgValidationError(code, message)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def validate_svg(path: Path) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        reject("INVALID_SVG_FILE", str(exc))

    for code, pattern in RAW_PATTERNS.items():
        if pattern.search(raw):
            reject(code, pattern.pattern)

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        reject("INVALID_SVG_XML", str(exc))

    if local_name(root.tag) != "svg":
        reject("INVALID_SVG_ROOT", root.tag)
    if root.attrib.get("role") != "img":
        reject("SVG_ROLE_REQUIRED", 'root role must be "img"')

    labelled = root.attrib.get("aria-labelledby", "").split()
    if len(labelled) < 2:
        reject("SVG_ARIA_LABELLEDBY_REQUIRED", "title and desc ids required")
    ids = {node.attrib.get("id") for node in root.iter() if node.attrib.get("id")}
    if not set(labelled).issubset(ids):
        reject("SVG_ARIA_TARGET_MISSING", "aria-labelledby ids not found")

    titles = [n for n in root.iter() if local_name(n.tag) == "title" and (n.text or "").strip()]
    descs = [n for n in root.iter() if local_name(n.tag) == "desc" and (n.text or "").strip()]
    if not titles or not descs:
        reject("SVG_ACCESSIBLE_TEXT_REQUIRED", "non-empty title and desc required")

    for node in root.iter():
        name = local_name(node.tag)
        if namespace(node.tag) == XINCLUDE and name == "include":
            reject("SVG_XINCLUDE_FORBIDDEN", "XInclude is not allowed")
        if name in FORBIDDEN_ELEMENTS:
            reject("SVG_ACTIVE_OR_FOREIGN_CONTENT", name)
        for attr, value in node.attrib.items():
            attr_name = local_name(attr).lower()
            text = str(value).strip().lower()
            if attr_name.startswith("on"):
                reject("SVG_EVENT_HANDLER_FORBIDDEN", attr_name)
            if attr_name == "base" and attr.startswith("{http://www.w3.org/XML/1998/namespace}"):
                reject("SVG_XML_BASE_FORBIDDEN", str(value))
            if attr_name in {"href", "src"} and (
                text.startswith(("http:", "https:", "javascript:", "data:", "//"))
            ):
                reject("SVG_EXTERNAL_REFERENCE_FORBIDDEN", str(value))
