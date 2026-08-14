from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookStructureVisibilityTests(unittest.TestCase):
    def _safe_members(self, worksheet_xml: str | None = None) -> dict[str, str]:
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
            "xl/worksheets/sheet1.xml": worksheet_xml
            or (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData/>'
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

    def test_nested_relationship_cannot_satisfy_package_graph(self) -> None:
        members = self._safe_members()
        members["_rels/.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Container><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Container>'
            '</Relationships>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertIn(
            "missing_office_document_relationship:xl/workbook.xml",
            result["findings"],
        )

    def test_foreign_namespace_relationship_cannot_satisfy_package_graph(self) -> None:
        members = self._safe_members()
        members["_rels/.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships" '
            'xmlns:fake="urn:fake">'
            '<fake:Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertIn(
            "missing_office_document_relationship:xl/workbook.xml",
            result["findings"],
        )

    def test_zero_height_row_is_rejected_as_hidden_content(self) -> None:
        worksheet = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1" ht="0" customHeight="1"><c r="A1" t="inlineStr">'
            '<is><t>hidden value</t></is></c></row></sheetData>'
            '</worksheet>'
        )
        result = self._validate(self._safe_members(worksheet))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("hidden_worksheet_content_not_allowed:row" in finding for finding in result["findings"])
        )

    def test_zero_width_column_is_rejected_as_hidden_content(self) -> None:
        worksheet = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cols><col min="1" max="1" width="0" customWidth="1"/></cols>'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>hidden value</t></is></c></row></sheetData>'
            '</worksheet>'
        )
        result = self._validate(self._safe_members(worksheet))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("hidden_worksheet_content_not_allowed:col" in finding for finding in result["findings"])
        )


if __name__ == "__main__":
    unittest.main()
