"""Offline tests for the small Heaps PAK reader used by catalogue tooling."""

from pathlib import Path
import struct
import tempfile
import unittest

from tools.list_pak import read_pak_file, walk_files, read_pak_index


class PakReaderTests(unittest.TestCase):
    def test_reads_a_file_from_a_minimal_pak_archive(self):
        # The root directory contains one file, data.cdb, at position zero in
        # the content area. This keeps the fixture independent of Northgard.
        file_entry = b"\x08data.cdb\x00" + struct.pack("<iii", 0, 2, 0)
        directory = b"\x00\x01" + struct.pack("<i", 1) + file_entry
        header_size = 16 + len(directory)
        archive = b"PAK" + struct.pack("<Bii", 0, header_size, 2)
        archive += directory + b"DATA{}"

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "fixture.pak"
            path.write_bytes(archive)

            names = [name for name, _ in walk_files(read_pak_index(path))]
            self.assertEqual(names, ["data.cdb"])
            self.assertEqual(read_pak_file(path, "data.cdb"), b"{}")


if __name__ == "__main__":
    unittest.main()
