from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.validate_public_workbook_artifacts import (
    _unsupported_workbook_files,
    _xlsx_files,
    main,
    validate_xlsx,
)


class PublicWorkbookValidationTests(unittest.TestCase):
    def _safe_members(self) -> dict[str, str | bytes]:
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
                '<sheets><sheet name="Sheet1" sheetId="1" state="visible" r:id="rId1"/></sheets>'
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

    def test_xlsx_discovery_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            upper = root / "unsafe.XLSX"
            upper.write_bytes(b"placeholder")
            self.assertEqual(_xlsx_files(root), [upper])

    def test_macro_enabled_extension_fails_gate(self) -> None:
        safe_source = self._write_zip(self._safe_members())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copyfile(safe_source, root / "safe.xlsx")
            macro = root / "unsafe.xlsm"
            macro.write_bytes(b"placeholder")
            self.assertEqual(_unsupported_workbook_files(root), [macro])
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--root", str(root), "--format", "json"]), 2)

    def test_missing_core_part_is_rejected(self) -> None:
        members = self._safe_members()
        del members["xl/workbook.xml"]
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertIn("missing_required_part:xl/workbook.xml", result["findings"])

    def test_invalid_ooxml_root_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/workbook.xml"] = '<foo xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("invalid_ooxml_root:xl/workbook.xml" in item for item in result["findings"]))

    def test_missing_workbook_relationship_target_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="/xl/worksheets/missing.xml"/>'
            '</Relationships>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing_relationship_target" in item for item in result["findings"]))

    def test_duplicate_case_colliding_package_parts_are_rejected(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        path = temp_dir / "test.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in self._safe_members().items():
                archive.writestr(name, content)
            archive.writestr("xl/sharedStrings.xml", "<sst/>")
            archive.writestr("XL/SHAREDSTRINGS.XML", "<sst/>")
        result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("duplicate_or_case_colliding_part" in item for item in result["findings"])
        )

    def test_unsafe_package_path_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/../private.xml"] = "<private/>"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("unsafe_package_part_name" in item for item in result["findings"]))

    def test_vba_payload_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/vbaProject.bin"] = b"not-real-vba"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("forbidden_part" in item for item in result["findings"]))

    def test_macro_sheet_part_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/macrosheets/sheet1.xml"] = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("forbidden_part" in item for item in result["findings"]))

    def test_active_relationship_type_is_rejected_even_with_disguised_target(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="/xl/worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" '
            'Target="payload.bin"/>'
            '</Relationships>'
        )
        members["xl/payload.bin"] = b"payload"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("active_type:oleobject" in item for item in result["findings"])
        )

    def test_external_relationship_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="https://example.com" TargetMode="External"/>'
            '</Relationships>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("external_or_active_relationship" in item for item in result["findings"]))

    def test_absolute_uri_relationship_without_target_mode_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="https://example.com/payload"/>'
            '</Relationships>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("absolute_uri" in item for item in result["findings"])
        )

    def test_malformed_relationship_xml_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/_rels/workbook.xml.rels"] = "<Relationships><Relationship"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("invalid_xml" in item for item in result["findings"]))

    def test_doctype_xml_is_rejected_before_parse(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = (
            '<!DOCTYPE sst [<!ENTITY x "unsafe">]>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>&x;</t></si>'
            '</sst>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("forbidden_xml_declaration" in item for item in result["findings"]))

    def test_even_benign_formula_is_rejected_by_formula_free_profile(self) -> None:
        members = self._safe_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row></sheetData>'
            '</worksheet>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("formula_not_allowed:f" in item for item in result["findings"]))

    def test_xlm_call_formula_is_rejected_by_formula_free_profile(self) -> None:
        members = self._safe_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><f>CALL("kernel32","WinExec","JJ","calc",1)</f>'
            '<v>0</v></c></row></sheetData>'
            '</worksheet>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("formula_not_allowed:f" in item for item in result["findings"]))

    def test_defined_name_is_rejected_by_formula_free_profile(self) -> None:
        members = self._safe_members()
        members["xl/workbook.xml"] = (
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" state="visible" r:id="rId1"/></sheets>'
            '<definedNames><definedName name="NamedRange">Sheet1!$A$1</definedName></definedNames>'
            '</workbook>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("formula_not_allowed:definedName" in item for item in result["findings"])
        )

    def test_dde_formula_is_rejected_by_formula_free_profile(self) -> None:
        members = self._safe_members()
        members["xl/worksheets/sheet1.xml"] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><f>cmd|\'/C calc\'!A0</f>'
            '<v>0</v></c></row></sheetData>'
            '</worksheet>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("formula_not_allowed:f" in item for item in result["findings"]))

    def test_hidden_sheet_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/workbook.xml"] = (
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Hidden" sheetId="1" state="veryHidden" r:id="rId1"/></sheets>'
            '</workbook>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("hidden_sheet_not_allowed:veryhidden" in item for item in result["findings"])
        )

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

    def test_private_marker_in_non_xml_part_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/media/image1.svg"] = b"metadata:cortex://private-doc"
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_marker" in item for item in result["findings"]))

    def test_private_marker_in_archive_metadata_is_rejected(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        path = temp_dir / "test.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.comment = b"cortex://private-doc"
            for name, content in self._safe_members().items():
                archive.writestr(name, content)
        result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("archive_comment" in item for item in result["findings"]))

    def test_private_governance_id_pattern_is_not_timestamp_prefix_specific(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>action-1886695239115-239115-secret</t></si>'
            '</sst>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_pattern" in item for item in result["findings"]))

    def test_rich_text_private_identifier_marker_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><r><t>cortex:</t></r><r><t>//private-doc</t></r></si>'
            '</sst>'
        )
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_marker" in item for item in result["findings"]))

    def test_utf16_private_identifier_marker_is_rejected(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = (
            '<?xml version="1.0" encoding="utf-16"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>cortex://private-doc</t></si>'
            '</sst>'
        ).encode("utf-16")
        result = validate_xlsx(self._write_zip(members))
        self.assertFalse(result["ok"])
        self.assertTrue(any("private_identifier_marker" in item for item in result["findings"]))

    def test_oversized_zip_member_is_rejected_before_read(self) -> None:
        members = self._safe_members()
        members["xl/sharedStrings.xml"] = b"x" * 513
        path = self._write_zip(members)
        with patch(
            "scripts.validate_public_workbook_artifacts.MAX_MEMBER_UNCOMPRESSED_BYTES",
            512,
        ):
            result = validate_xlsx(path)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("member_uncompressed_size_limit" in item for item in result["findings"])
        )


if __name__ == "__main__":
    unittest.main()
