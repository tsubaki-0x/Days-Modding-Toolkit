import unittest

from sdhq_toolkit.utils.windows_resources import normalize_ciphercode


class CipherCodeTests(unittest.TestCase):
    def test_twenty_byte_resource_discards_prefix(self):
        resource = b"HEAD" + bytes(range(16))
        self.assertEqual(normalize_ciphercode(resource), bytes(range(16)))

    def test_other_size_is_preserved(self):
        self.assertEqual(normalize_ciphercode(b"12345678"), b"12345678")


if __name__ == "__main__":
    unittest.main()
