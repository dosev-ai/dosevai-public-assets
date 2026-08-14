from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import (
    _unsupported_workbook_files,
    validate_xlsx,
)


class PublicWorkbookFinalEdgeCasesTests(unittest.TestCase):
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

    def test_fake_structural_relationship_type_uris_are_rejected(self) -> None:
        members = self._safe_members()
        members["_rels/.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="urn:fake/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="urn:fake/worksheet" '
            'Target="/xl/worksheets/sheet1.xml"/>'
            '</Relationships>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertIn(
            "missing_office_document_relationship:xl/workbook.xml",
            result["findings"],
        )
        self.assertIn("missing_workbook_worksheet_relationship", result["findings"])

    def test_custom_number_formats_are_rejected(self) -> None:
        members = self._safe_members()
        members["xl/styles.xml"] = (
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<numFmts count="1"><numFmt numFmtId="164" formatCode=";;;"/></numFmts>'
            '<fonts count="1"><font/></fonts><fills count="1"><fill/></fills>'
            '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="2"><xf/><xf numFmtId="164" applyNumberFormat="1"/></cellXfs>'
            '</styleSheet>'
        )
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" s="1" t="n"><v>123</v></c></row></sheetData>'
            '</worksheet>'
        )
        result = self._validate(members)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("display_suppressing_style_not_allowed:custom_number_format" in finding for finding in result["findings"])
        )

    def test_open_document_spreadsheet_extensions_are_explicitly_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for suffix in (".ods", ".ots", ".fods", ".sxc"):
                (root / f"unsafe{suffix}").write_bytes(b"not-a-public-xlsx")
            found = {path.suffix.lower() for path in _unsupported_workbook_files(root)}
        self.assertEqual(found, {".ods", ".ots", ".fods", ".sxc"})


if __name__ == "__main__":
    unittest.main()
