from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookAttributeMarkerTests(unittest.TestCase):
    def test_character_reference_private_id_in_sheet_name_is_rejected(self) -> None:
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
                '<sheets><sheet name="action-1886695&#50;39115-secret" sheetId="1" '
                'state="visible" r:id="rId1"/></sheets>'
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
                '<sheetData/>'
                '</worksheet>'
            ),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "attribute-bypass.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            result = validate_xlsx(path)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any("private_identifier_pattern:action-1886695239115-secret" in finding for finding in result["findings"])
        )


if __name__ == "__main__":
    unittest.main()
