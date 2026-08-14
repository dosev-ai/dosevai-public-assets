from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookConditionalFormattingTests(unittest.TestCase):
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
        }

    def _validate(self, members: dict[str, str]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "conditional-formatting.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            return validate_xlsx(path)

    def test_conditional_formatting_is_rejected(self) -> None:
        members = self._base_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>visible value</t></is></c></row></sheetData>'
            '<conditionalFormatting sqref="A1"><cfRule type="uniqueValues" dxfId="0" priority="1"/>'
            '</conditionalFormatting></worksheet>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "hidden_worksheet_content_not_allowed:conditional_formatting" in finding
                for finding in result["findings"]
            )
        )

    def test_differential_styles_are_rejected(self) -> None:
        members = self._base_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>visible value</t></is></c></row></sheetData>'
            '</worksheet>'
        )
        members["xl/styles.xml"] = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font/></fonts><fills count="2">'
            '<fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="1"><xf fontId="0" fillId="0"/></cellXfs>'
            '<dxfs count="1"><dxf><font><color rgb="FFFFFFFF"/></font></dxf></dxfs>'
            '</styleSheet>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "display_suppressing_style_not_allowed:differential_style" in finding
                for finding in result["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
