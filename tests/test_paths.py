import tempfile
import unittest
from pathlib import Path

from sdhq_toolkit.utils.paths import safe_member_path


class SafePathTests(unittest.TestCase):
    def test_safe_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(safe_member_path(root, "Script/english/a.ORS"), root / "Script/english/a.ORS")

    def test_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_member_path(Path(directory), "../outside.bin")


if __name__ == "__main__":
    unittest.main()

