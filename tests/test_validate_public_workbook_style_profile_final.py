from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookStyleProfileFinalTests(unittest.TestCase):
    def _base_members(self) -> dict[str, str]:
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

    def _validate(self, styles_xml: str) -> dict[str, object]:
        members = self._base_members()
        members["xl/styles.xml"] = styles_xml
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "style-edge.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            return validate_xlsx(path)

    def test_automatic_default_font_on_black_fill_is_rejected(self) -> None:
        styles = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font/></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor indexed="8"/></patternFill></fill>'
            '</fills><borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
            '<xf fontId="0" fillId="2" applyFill="1"/></cellXfs>'
            '</styleSheet>'
        )
        result = self._validate(styles)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:font_matches_fill" in finding
                for finding in result["findings"]
            )
        )

    def test_tinted_style_color_is_rejected(self) -> None:
        styles = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font/><font><color rgb="FFFFFFFF"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor theme="1" tint="1"/></patternFill></fill>'
            '</fills><borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
            '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs>'
            '</styleSheet>'
        )
        result = self._validate(styles)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:tinted_color" in finding
                for finding in result["findings"]
            )
        )

    def test_gradient_fill_is_rejected(self) -> None:
        styles = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font/><font><color indexed="0"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><gradientFill><stop position="0"><color indexed="0"/></stop>'
            '<stop position="1"><color indexed="8"/></stop></gradientFill></fill>'
            '</fills><borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
            '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs>'
            '</styleSheet>'
        )
        result = self._validate(styles)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:gradient_fill" in finding
                for finding in result["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
