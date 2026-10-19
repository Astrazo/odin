"""List files stored in a Heaps PAK archive without extracting its contents."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass
class PakFile:
    """One file or directory described by a PAK header."""

    name: str
    data_position: int | None = None
    data_size: int | None = None
    children: list["PakFile"] | None = None


def _read_exact(data: memoryview, offset: int, size: int) -> tuple[bytes, int]:
    end = offset + size
    if end > len(data):
        raise ValueError("PAK directory ends unexpectedly.")
    return bytes(data[offset:end]), end


def _read_i32(data: memoryview, offset: int) -> tuple[int, int]:
    raw, offset = _read_exact(data, offset, 4)
    return struct.unpack("<i", raw)[0], offset


def _read_file(data: memoryview, offset: int) -> tuple[PakFile, int]:
    name_length, offset = _read_exact(data, offset, 1)
    raw_name, offset = _read_exact(data, offset, name_length[0])
    name = raw_name.decode("utf-8")
    raw_flags, offset = _read_exact(data, offset, 1)
    flags = raw_flags[0]

    if flags & 1:
        count, offset = _read_i32(data, offset)
        if count < 0:
            raise ValueError("PAK directory has a negative child count.")
        children = []
        for _ in range(count):
            child, offset = _read_file(data, offset)
            children.append(child)
        return PakFile(name=name, children=children), offset

    if flags & 2:
        raw_position, offset = _read_exact(data, offset, 8)
        data_position = int(struct.unpack("<d", raw_position)[0])
    else:
        data_position, offset = _read_i32(data, offset)
    data_size, offset = _read_i32(data, offset)
    _, offset = _read_i32(data, offset)  # Checksum is not needed to list files.
    return PakFile(name=name, data_position=data_position, data_size=data_size), offset


def _read_pak_header(path: Path) -> tuple[PakFile, int]:
    """Read the PAK directory tree and the byte offset of its content area."""
    with path.open("rb") as archive:
        fixed_header = archive.read(12)
        if len(fixed_header) != 12 or fixed_header[:3] != b"PAK":
            raise ValueError(f"Not a Heaps PAK archive: {path}")

        _, header_size, _ = struct.unpack("<Bii", fixed_header[3:])
        if header_size < 16:
            raise ValueError(f"Invalid PAK header size: {header_size}")

        directory = archive.read(header_size - 16)
        marker = archive.read(4)

    if len(directory) != header_size - 16 or marker != b"DATA":
        raise ValueError("PAK directory is incomplete or corrupt.")

    root, offset = _read_file(memoryview(directory), 0)
    if offset != len(directory):
        raise ValueError("PAK directory has trailing unread bytes.")
    return root, header_size


def read_pak_index(path: Path) -> PakFile:
    """Read only the PAK header and return its directory tree."""
    root, _ = _read_pak_header(path)
    return root


def read_pak_file(path: Path, wanted_path: str) -> bytes:
    """Return one file stored in a PAK archive."""
    root, header_size = _read_pak_header(path)
    entries = dict(walk_files(root))
    entry = entries.get(wanted_path)
    if entry is None or entry.data_position is None or entry.data_size is None:
        raise ValueError(f"PAK file not found: {wanted_path}")
    if entry.data_position < 0 or entry.data_size < 0:
        raise ValueError(f"PAK file has an invalid position or size: {wanted_path}")

    with path.open("rb") as archive:
        archive.seek(header_size + entry.data_position)
        content = archive.read(entry.data_size)
    if len(content) != entry.data_size:
        raise ValueError(f"PAK file is incomplete: {wanted_path}")
    return content


def walk_files(entry: PakFile, parent: str = ""):
    """Yield every file path and its header metadata."""
    path = f"{parent}/{entry.name}".strip("/")
    if entry.children is None:
        yield path, entry
        return
    for child in entry.children:
        yield from walk_files(child, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--match", default="", help="Case-insensitive path substring")
    args = parser.parse_args()

    needle = args.match.lower()
    for path, entry in walk_files(read_pak_index(args.archive)):
        if needle in path.lower():
            print(f"{path}\t{entry.data_position}\t{entry.data_size}")


if __name__ == "__main__":
    main()
