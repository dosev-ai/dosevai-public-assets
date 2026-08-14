from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookColorAliasTests(unittest.TestCase):
    def test_indexed_palette_aliases_that_render_same_color_are_rejected(self) -> None:
        members = {
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
            "xl/styles.xml": (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="2"><font/><font><color indexed="0"/></font></fonts>'
                '<fills count="3"><fill><patternFill patternType="none"/></fill>'
                '<fill><patternFill patternType="gray125"/></fill>'
                '<fill><patternFill patternType="solid"><fgColor indexed="8"/></patternFill></fill>'
                '</fills><borders count="1"><border/></borders>'
                '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
                '<cellXfs count="2"><xf fontId="0" fillId="0"/>'
                '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs>'
                '</styleSheet>'
            ),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "indexed-alias.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            result = validate_xlsx(path)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:font_matches_fill"
                in finding
                for finding in result["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
