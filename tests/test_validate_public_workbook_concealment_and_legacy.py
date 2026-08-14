from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import (
    _unsupported_workbook_files,
    validate_xlsx,
)


class PublicWorkbookConcealmentAndLegacyTests(unittest.TestCase):
    def _safe_members(self) -> dict[str, str]:
        return {
            "[Content_Types].xml": (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '</Types>'
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                '</Relationships>'
            ),
            "xl/workbook.xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Visible" sheetId="1" state="visible" r:id="rId1"/></sheets>'
                '</workbook>'
            ),
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="/xl/worksheets/sheet1.xml"/>'
                '</Relationships>'
            ),
            "xl/worksheets/sheet1.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row r="1"><c r="A1" s="1" t="inlineStr">'
                '<is><t>concealed value</t></is></c></row></sheetData>'
                '</worksheet>'
            ),
        }

    def _validate(self, members: dict[str, str]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "case.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            return validate_xlsx(path)

    def test_white_font_on_default_background_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/styles.xml"] = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font/><font><color rgb="FFFFFFFF"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
            '<xf fontId="1" fillId="0" applyFont="1"/></cellXfs>'
            '</styleSheet>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:light_font_on_light_background"
                in finding
                for finding in result["findings"]
            )
        )

    def test_matching_font_and_fill_color_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/styles.xml"] = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font/><font><color rgb="FF123456"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF123456"/></patternFill></fill>'
            '</fills><borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
            '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs>'
            '</styleSheet>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:font_matches_fill"
                in finding
                for finding in result["findings"]
            )
        )

    def test_every_xl_prefixed_non_xlsx_extension_is_rejected(self) -> None:
        suffixes = {".xlm", ".xlw", ".xlk", ".xls", ".xlsm", ".xlam", ".xll"}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for suffix in suffixes:
                (root / f"unsafe{suffix}").write_bytes(b"not-a-public-xlsx")
            found = {path.suffix.lower() for path in _unsupported_workbook_files(root)}
        self.assertEqual(found, suffixes)


if __name__ == "__main__":
    unittest.main()
