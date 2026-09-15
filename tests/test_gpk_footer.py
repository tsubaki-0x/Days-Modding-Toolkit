import struct
import unittest

from sdhq_toolkit.formats.gpk.footer import parse_stack_footer


class GPKFooterTests(unittest.TestCase):
    def test_stack_footer(self):
        footer = b"STKFile0PIDX" + struct.pack("<I", 1234) + b"STKFile0PACKFILE"
        result = parse_stack_footer(footer, 10000)
        self.assertTrue(result["valid"])
        self.assertEqual(result["format"], "GPK/STACK")
        self.assertEqual(result["index_size"], 1234)
        self.assertEqual(result["index_offset"], 8734)

    def test_unknown_footer(self):
        result = parse_stack_footer(bytes(32), 10000)
        self.assertFalse(result["valid"])
        self.assertEqual(result["format"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
