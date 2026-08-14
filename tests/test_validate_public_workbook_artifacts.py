from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookValidationTests(unittest.TestCase):
    def _safe_members(self) -> dict[str, str | bytes]:
        return {
            "[Content_Types].xml": (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
            ),
            "xl/workbook.xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
            ),
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
            ),
            "xl/worksheets/sheet1.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData/>'
                '</worksheet>'
            ),
        }

    def _write_zip(self, members: dict[str, str | bytes]) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        path = temp_dir / "test.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return path

    def test_safe_xlsx_passes(self) -> None:
        path = self._write_zip(self._safe_members())
        self.assertTrue(validate_xlsx(path)["ok"])

    def test_missing_core_part_is_rejected(self) -> None:
        members = self._safe_members()
        del members["xl/workbook.xml"]
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertIn("missing_required_part:xl/workbook.xml", result["findings"])

    def test_vba_payload_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/vbaProject.bin"] = b"not-real-vba"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("forbidden_part" in item for item in result["findings"]))

    def test_external_relationship_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="x" Target="https://example.com" TargetMode="External"/>'
            '</Relationships>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("external_relationship" in item for item in result["findings"]))

    def test_malformed_relationship_xml_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = "<Relationships><Relationship"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("invalid_xml" in item for item in result["findings"]))

    def test_network_capable_formula_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><f>WEBSERVICE("https://example.com")</f>'
            '<v>0</v></c></row></sheetData>'
            '</worksheet>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("network_capable_formula:webservice" in item for item in result["findings"]))

    def test_private_identifier_marker_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>cortex://private-doc</t></si>'
            '</sst>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_marker" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
