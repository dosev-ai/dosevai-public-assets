from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.validate_public_workbook_artifacts import validate_xlsx


class PublicWorkbookValidationTests(unittest.TestCase):
    def _write_zip(self, members: dict[str, str | bytes]) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        path = temp_dir / "test.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return path

    def test_safe_xlsx_passes(self) -> None:
        path = self._write_zip({
            "[Content_Types].xml": "<Types/>",
            "xl/workbook.xml": "<workbook/>",
            "xl/_rels/workbook.xml.rels": "<Relationships/>",
        })
        self.assertTrue(validate_xlsx(path)["ok"])

    def test_vba_payload_is_rejected(self) -> None:
        path = self._write_zip({
            "[Content_Types].xml": "<Types/>",
            "xl/vbaProject.bin": b"not-real-vba",
        })
        result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("forbidden_part" in item for item in result["findings"]))

    def test_external_relationship_is_rejected(self) -> None:
        path = self._write_zip({
            "[Content_Types].xml": "<Types/>",
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="x" Target="https://example.com" TargetMode="External"/>'
                '</Relationships>'
            ),
        })
        result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("external_relationship" in item for item in result["findings"]))

    def test_private_identifier_marker_is_rejected(self) -> None:
        path = self._write_zip({
            "[Content_Types].xml": "<Types/>",
            "xl/sharedStrings.xml": "<sst><si><t>cortex://private-doc</t></si></sst>",
        })
        result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_marker" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
