import struct
import tempfile
import unittest
from pathlib import Path

from sdhq_toolkit.formats.crio import PREFIX, encode_offset, encode_size, parse_container
from sdhq_toolkit.core.summer_days_crio import SummerDaysCRioService


class Cancel:
    def check(self):
        pass


def progress(*_):
    pass


def make_one_payload_crio(path: Path, payload=b"OggSDEMO"):
    # root_count lives immediately after the 18-byte fixed prefix.
    name = b"A"
    record_size = 1 + len(name) + 3 + 2 + 4 + 4 + 2
    header_end = 20 + record_size
    record = bytearray()
    record += bytes([len(name)]) + name
    record += b"\x08\xC0\x00"
    record += struct.pack("<H", 0)  # existing class reference/no declaration
    record += struct.pack("<I", encode_offset(header_end))
    record += struct.pack("<I", encode_size(len(payload)))
    record += struct.pack("<H", 0)
    path.write_bytes(PREFIX + struct.pack("<H", 1) + record + payload)


class CRioBackendTests(unittest.TestCase):
    def test_modified_payload_roundtrip_through_visible_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reference = root / "TITLE"
            make_one_payload_crio(reference)
            parsed = parse_container(reference)
            self.assertEqual(len(parsed.objects), 1)
            self.assertEqual(parsed.objects[0].internal_path, "A")

            service = SummerDaysCRioService(reference, root / "workspace", root / "output")
            extracted = service.extract(cancel=Cancel(), progress=progress)
            editable = Path(extracted["workspace"]) / "A"
            self.assertTrue(editable.is_file())
            editable.write_bytes(b"OggSALTERADO")

            validation = service.validate(cancel=Cancel(), progress=progress)
            self.assertEqual(validation["changed"], 1)
            self.assertEqual(validation["files"][0]["path"], "A")

            result = service.repack(cancel=Cancel(), progress=progress)
            output = Path(result["output"])
            self.assertTrue(output.is_file())
            rebuilt = parse_container(output)
            self.assertEqual(rebuilt.objects[0].payload_size, len(b"OggSALTERADO"))
            self.assertNotEqual(output.read_bytes(), reference.read_bytes())

    def test_new_visible_file_is_reported_but_not_added(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reference = root / "TITLE"
            make_one_payload_crio(reference)
            service = SummerDaysCRioService(reference, root / "workspace", root / "output")
            service.extract(cancel=Cancel(), progress=progress)
            (service.edit_root / "NOVO.bin").write_bytes(b"x")
            report = service.validate(cancel=Cancel(), progress=progress)
            self.assertIn("NOVO.bin", report["extras"])
            self.assertTrue(any(row["state"] == "novo — não incluído" for row in report["files"]))


if __name__ == "__main__":
    unittest.main()
