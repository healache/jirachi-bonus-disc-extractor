#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: © 2026 healache <healache@posteo.org>
# SPDX-License-Identifier: BSD-3-Clause

"""
Extractor for the Pokemon Colosseum Bonus Disc (PC6E01, Rev.00).

The Bonus Disc distributed Jirachi to Ruby and Sapphire via a multiboot
ROM. It is stored in an embedded disk image, pokedownload.tgc, which
contains three distribution builds, but only one was actually used.

    File                  OT          TID    Description
    ------------------------------------------------------------------
    client.bin            WISHMKR     20043  Retail distribution
    client.2003_1112.bin  METEOR      30719  Unreleased (2003-11-12)
    sample0519.bin        ネガイボシ  30719  Sample build (2003-05-19)

How this works
---------------
The three builds' exact byte ranges inside PC6E01.iso were determined
once, by hand, from the layout of pokedownload.tgc and its own embedded
file table. Those ranges are hardcoded below as TARGETS, so at runtime
this script never parses the .tgc container (and never loads the ISO
into RAM) - it just seeks to each known offset and copies the bytes
out.

Because the offsets are hardcoded, they are only valid for this exact
disc image. Before extracting anything, verify_disc() checks a handful
of fixed points in the ISO (the disc header magic, the main file
table's offset and hash, and the .tgc container's own magic) to confirm
the supplied file really is a byte-for-byte match for PC6E01 Rev.00. If
any check fails, the script aborts rather than silently extracting
garbage from the wrong offsets.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import struct
import sys
import typing as t

# --- GameCube disc header (boot.bin) ----------------------------------
#
# Every GameCube disc starts with a fixed-layout header. We only care
# about two fields in it: a magic value that all real GC discs share,
# and the offset of the disc's file table (the FST).
DISC_MAGIC_OFFSET = 0x1C
DISC_MAGIC = 0xC2339F3D
FST_OFFSET_FIELD = 0x424  # Location of the "where is the FST" pointer

# --- Main file table (FST) --------------------------------------------
#
# The FST is the disc's directory listing: a flat array of 12-byte
# entries (one per file/directory). MAIN_FST_SHA256 is the hash of the
# entire 443-byte table for this specific disc revision, used below as
# a strong "is this really PC6E01 Rev.00?" check.
MAIN_FST_OFFSET = 0x000DBE00
MAIN_FST_SIZE = 0x1BB
MAIN_FST_SHA256 = "24ef3c366c733e3e80ac144aef246cb95579469c7f99e41bfae322d666870802"
FST_ENTRY_SIZE = 12

TGC_ENTRY_INDEX = 16  # pokedownload.tgc entry (zero-indexed)
TGC_OFFSET = 0x35108000  # Start of pokedownload.tgc in the ISO
TGC_MAGIC = 0xAE0F38A2  # TGC container magic


class Target(t.NamedTuple):
    offset: int
    size: int
    name: str


U32 = struct.Struct(">I")

# Byte ranges of each distribution ROM inside the ISO; found by hand
# from pokedownload.tgc's internal file table.
TARGETS = (
    Target(offset=0x352DDF2C, size=0x6BC0, name="client.bin"),
    Target(offset=0x352D8000, size=0x5F2C, name="client.2003_1112.bin"),
    Target(offset=0x3DA32D30, size=0x116C8, name="sample0519.bin"),
)


def read_u32_big_endian(iso: t.BinaryIO, offset: int) -> int:
    """
    Read a 32-bit big-endian integer at `offset`.

    GameCube data is big-endian throughout, so this is the format used
    by every field in the disc header and FST below.
    """
    iso.seek(offset)
    data = iso.read(U32.size)

    if len(data) != U32.size:
        message = f"short read at 0x{offset:X}"
        raise EOFError(message)

    return U32.unpack(data)[0]


def extract_target(iso: t.BinaryIO, target: Target, out_dir: pathlib.Path) -> int:
    """Read the target binary and write it to disc."""
    iso.seek(target.offset)
    data = iso.read(target.size)

    if len(data) != target.size:
        message = f"short read at 0x{target.offset:X} (wanted {target.size})"
        raise EOFError(message)

    return (out_dir / target.name).write_bytes(data)


def read_fst_entry(
    iso: t.BinaryIO, fst_offset: int, entry_index: int,
) -> tuple[bool, int]:
    """
    Read an FST entry's type and file offset.

    Each FST entry is 12 bytes:
      byte 0      entry type (0 = file, 1 = directory)
      bytes 1-3   name offset into the string table
      bytes 4-7   file offset (files) / parent dir index (directories)
      bytes 8-11  file length (files) / next non-child index (directories)
    """
    iso.seek(fst_offset + entry_index * FST_ENTRY_SIZE)
    entry_data = iso.read(FST_ENTRY_SIZE)

    if len(entry_data) != FST_ENTRY_SIZE:
        message = f"short read at FST entry {entry_index}"
        raise EOFError(message)

    is_dir = bool(entry_data[0])
    file_offset = U32.unpack_from(entry_data, U32.size)[0]
    return is_dir, file_offset


def verify_disc(iso: t.BinaryIO) -> None:
    """
    Confirm `iso` is byte-for-byte PC6E01 Rev.00.

    Raises `ValueError` if a check fails.

    Everything TARGETS points at is a hardcoded offset that only makes
    sense for this one disc image, so these checks exist purely to
    catch a wrong file (different game, region, or revision) early and
    loudly, rather than reading garbage bytes later on and writing them
    out as if they were valid ROMs.
    """
    if read_u32_big_endian(iso, DISC_MAGIC_OFFSET) != DISC_MAGIC:
        message = "not a GameCube ISO (bad file header magic)"
        raise ValueError(message)

    if read_u32_big_endian(iso, FST_OFFSET_FIELD) != MAIN_FST_OFFSET:
        message = "unexpected main FST offset"
        raise ValueError(message)

    iso.seek(MAIN_FST_OFFSET)
    fst_data = iso.read(MAIN_FST_SIZE)

    if len(fst_data) != MAIN_FST_SIZE:
        message = "short read of main FST"
        raise EOFError(message)

    if hashlib.sha256(fst_data).hexdigest() != MAIN_FST_SHA256:
        message = "main FST does not match expected layout"
        raise ValueError(message)

    # Confirm pokedownload.tgc is a file at the offset we expect.
    is_dir, offset = read_fst_entry(iso, MAIN_FST_OFFSET, TGC_ENTRY_INDEX)

    if is_dir or offset != TGC_OFFSET:
        message = f"FST entry {TGC_ENTRY_INDEX} not pokedownload.tgc"
        raise ValueError(message)

    if read_u32_big_endian(iso, TGC_OFFSET) != TGC_MAGIC:
        message = f"bad TGC magic (expected 0x{TGC_MAGIC:X})"
        raise ValueError(message)


def extract_all(iso: t.BinaryIO, iso_size: int, out_dir: pathlib.Path) -> int:
    """
    Copy each ROM's byte range in TARGETS from `iso` into `out_dir`.

    The .tgc container itself is never parsed - each range was
    already worked out ahead of time (see TARGETS above), so this just
    copies those ranges straight out of the ISO. Returns the total
    number of bytes extracted.
    """
    column_width = max(len(target.name) for target in TARGETS)

    total = 0
    for target in TARGETS:
        if target.offset + target.size > iso_size:
            message = (
                f"{target.name} range 0x{target.offset:X}+0x{target.size:X} "
                f"exceeds ISO (0x{iso_size:X})"
            )
            raise ValueError(message)

        read_bytes = extract_target(iso, target, out_dir)
        total += read_bytes
        print(f"  {target.name:<{column_width}}  {read_bytes / 1024:.1f} KiB")

    return total


def main() -> None:
    try:
        _, iso_file = sys.argv
    except ValueError:
        sys.exit("usage: python extract.py </path/to/PC6E01.iso>")

    try:
        iso_path = pathlib.Path(iso_file).expanduser().resolve(strict=True)
    except FileNotFoundError:
        sys.exit(f"error: {iso_file!r} not found")

    out_dir = pathlib.Path("out")
    out_dir.mkdir(exist_ok=True)

    with iso_path.open("rb") as iso:
        iso_size = iso.seek(0, os.SEEK_END)
        print(f"ISO: {iso_file}  ({iso_size / 1024**3:.2f} GiB)")

        verify_disc(iso)
        total = extract_all(iso, iso_size, out_dir)

        print(f"\nExtracted {total / 1024:.1f} KiB total")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, EOFError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nerror: extraction interrupted", file=sys.stderr)
        sys.exit(130)
