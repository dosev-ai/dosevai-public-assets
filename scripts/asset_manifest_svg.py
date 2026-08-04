"""Fail-closed validation for self-contained SVG assets."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
XINCLUDE = "http://www.w3.org/2001/XInclude"
FORBIDDEN_ELEMENTS = {"script", "foreignObject", "image", "animate", "animateMotion", "animateTransform", "set"}
RAW_PATTERNS = {
    "SVG_DTD_FORBIDDEN": re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.I),
    "SVG_PROCESSING_INSTRUCTION_FORBIDDEN": re.compile(r"<\?(?!xml\s)[^>]*\?>", re.I),
    "SVG_JAVASCRIPT_FORBIDDEN": re.compile(r"javascript\s*:", re.I),
    "SVG_CSS_IMPORT_FORBIDDEN": re.compile(r"@import\b", re.I),
    "SVG_EXTERNAL_CSS_URL_FORBIDDEN": re.compile(r"url\(\s*['\"]?\s*(?:https?:|//|data:|javascript:)", re.I),
}
CSS_URL_PATTERN = re.compile(r"url\(\s*(?:(['\"])(.*?)\1|([^)]*?))\s*\)", re.I | re.S)
CSS_ESCAPE_PATTERN = re.compile(r"\\([0-9a-fA-F]{1,6})(?:[ \t\r\n\f])?|\\(.)", re.S)


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


def decode_css_escapes(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            codepoint = int(match.group(1), 16)
            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                return "\ufffd"
            return chr(codepoint)
        return match.group(2) or ""
    return CSS_ESCAPE_PATTERN.sub(replace, text)


def reject_non_fragment_css_urls(text: str) -> None:
    text = decode_css_escapes(text)
    for match in CSS_URL_PATTERN.finditer(text):
        target = (match.group(2) if match.group(1) else match.group(3) or "").strip()
        if not target.startswith("#"):
            reject("SVG_EXTERNAL_CSS_URL_FORBIDDEN", target)


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
    if namespace(root.tag) != SVG_NS:
        reject("SVG_NAMESPACE_REQUIRED", namespace(root.tag) or "missing")
    for node in root.iter():
        node_namespace = namespace(node.tag)
        if node_namespace == XINCLUDE:
            reject("SVG_XINCLUDE_FORBIDDEN", "XInclude namespace is not allowed")
        if node_namespace != SVG_NS:
            reject("SVG_FOREIGN_NAMESPACE_FORBIDDEN", node_namespace or "missing")
    if root.attrib.get("role") != "img":
        reject("SVG_ROLE_REQUIRED", 'root role must be "img"')

    labelled = root.attrib.get("aria-labelledby", "").split()
    if len(labelled) < 2:
        reject("SVG_ARIA_LABELLEDBY_REQUIRED", "title and desc ids required")
    if len(labelled) != len(set(labelled)):
        reject("SVG_ARIA_LABELLEDBY_DUPLICATE", "aria-labelledby ids must be unique")

    id_nodes: dict[str, ET.Element] = {}
    for node in root.iter():
        node_id = node.attrib.get("id")
        if not node_id:
            continue
        if node_id in id_nodes:
            reject("SVG_DUPLICATE_ID_FORBIDDEN", node_id)
        id_nodes[node_id] = node
    if not set(labelled).issubset(id_nodes):
        reject("SVG_ARIA_TARGET_MISSING", "aria-labelledby ids not found")

    titles = [
        node for node in root.iter()
        if namespace(node.tag) == SVG_NS and local_name(node.tag) == "title" and (node.text or "").strip()
    ]
    descs = [
        node for node in root.iter()
        if namespace(node.tag) == SVG_NS and local_name(node.tag) == "desc" and (node.text or "").strip()
    ]
    if not titles or not descs:
        reject("SVG_ACCESSIBLE_TEXT_REQUIRED", "non-empty title and desc required")
    title_ids = {node.attrib.get("id") for node in titles if node.attrib.get("id")}
    desc_ids = {node.attrib.get("id") for node in descs if node.attrib.get("id")}
    if not title_ids or not desc_ids:
        reject("SVG_ACCESSIBLE_TEXT_ID_REQUIRED", "title and desc require ids")
    if not any(node_id in title_ids for node_id in labelled) or not any(node_id in desc_ids for node_id in labelled):
        reject("SVG_ARIA_TITLE_DESC_BINDING_REQUIRED", "aria-labelledby must reference SVG title and desc")
    allowed_label_ids = title_ids | desc_ids
    if any(node_id not in allowed_label_ids for node_id in labelled):
        reject("SVG_ARIA_TARGET_INVALID", "aria-labelledby may reference only SVG title and desc")

    for node in root.iter():
        name = local_name(node.tag)
        if name in FORBIDDEN_ELEMENTS:
            reject("SVG_ACTIVE_OR_FOREIGN_CONTENT", name)
        for attr, value in node.attrib.items():
            attr_name = local_name(attr).lower()
            text = decode_css_escapes(str(value).strip().lower())
            for code, pattern in RAW_PATTERNS.items():
                if code != "SVG_DTD_FORBIDDEN" and pattern.search(text):
                    reject(code, str(value))
            reject_non_fragment_css_urls(text)
            if attr_name.startswith("on"):
                reject("SVG_EVENT_HANDLER_FORBIDDEN", attr_name)
            if attr_name == "base" and attr.startswith("{http://www.w3.org/XML/1998/namespace}"):
                reject("SVG_XML_BASE_FORBIDDEN", str(value))
            if attr_name in {"href", "src"} and not text.startswith("#"):
                reject("SVG_EXTERNAL_REFERENCE_FORBIDDEN", str(value))
        text_content = decode_css_escapes((node.text or "") + (node.tail or ""))
        for code, pattern in RAW_PATTERNS.items():
            if code not in {"SVG_DTD_FORBIDDEN", "SVG_PROCESSING_INSTRUCTION_FORBIDDEN"} and pattern.search(text_content):
                reject(code, text_content.strip())
        reject_non_fragment_css_urls(text_content)
