from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_public_workbook_artifacts import _unsupported_workbook_files


class PublicWorkbookExtensionRejectionTests(unittest.TestCase):
    def test_legacy_and_native_addins_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = []
            for suffix in (".xla", ".xll", ".xlam"):
                path = root / f"unsafe{suffix}"
                path.write_bytes(b"placeholder")
                expected.append(path)

            self.assertEqual(_unsupported_workbook_files(root), sorted(expected))


if __name__ == "__main__":
    unittest.main()
