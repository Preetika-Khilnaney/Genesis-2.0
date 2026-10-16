"""WAD and PAK: 1990s shooter game archives. OWNER: Khushi (recovery).

Public formats, checked against real-samples s23 (WAD) and s24 (PAK); evidence in FIELD-LOG.md.

  WAD (Doom):  "IWAD"/"PWAD", i32 lump count, i32 directory offset;
               directory entries (16 bytes): i32 offset, i32 size, name[8] (NUL-terminated; bytes
               after the NUL are junk and ignored: s23 "SEGS\\0\\x7fAB").
               Zero-size lumps (F_START, MAP01...) are markers and are listed too.
  PAK (Quake): "PACK", i32 directory offset, i32 directory length;
               directory entries (64 bytes): name[56] NUL-terminated, i32 offset, i32 size.

Records: name, offset, size, sha256 of the lump/file bytes. An entry is verified when it lies
inside the file and does not start inside the header or directory.
"""
from __future__ import annotations

import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, record, sha256

WAD_SPEC = FormatSpec(
    name="WAD", magic=b"PWAD",
    description="Doom WAD: 12-byte header, lumps, directory of 16-byte entries.",
    checksum="none (entries are checked against the file bounds)",
    header=[FieldSpec("ident", "bytes", 4, "IWAD or PWAD", "s23 PWAD"),
            FieldSpec("lump_count", "i32", desc="directory entries", evidence="s23: 7 entries end exactly at EOF"),
            FieldSpec("dir_offset", "i32", desc="directory offset", evidence="s23")],
    record=[FieldSpec("offset", "i32", desc="lump offset", evidence="s23"),
            FieldSpec("size", "i32", desc="lump size", evidence="s23"),
            FieldSpec("name", "bytes", 8, "NUL-terminated name", "s23")],
)
PAK_SPEC = FormatSpec(
    name="PAK", magic=b"PACK",
    description="Quake PAK: 12-byte header, files, directory of 64-byte entries.",
    checksum="none (entries are checked against the file bounds)",
    header=[FieldSpec("ident", "bytes", 4, "PACK", "s24"),
            FieldSpec("dir_offset", "i32", desc="directory offset", evidence="s24"),
            FieldSpec("dir_length", "i32", desc="directory bytes (64 per entry)", evidence="s24: 256 = 4 entries")],
    record=[FieldSpec("name", "bytes", 56, "NUL-terminated path", "s24"),
            FieldSpec("offset", "i32", desc="file offset", evidence="s24"),
            FieldSpec("size", "i32", desc="file size", evidence="s24")],
)


def _name(raw: bytes) -> str:
    return raw.split(b"\0")[0].decode("latin-1")


def _entries(res: FileResult, b: bytes, entries: list[tuple[int, str, int, int]], dir_start: int, dir_end: int):
    for i, (eo, name, off, size) in enumerate(entries):
        issues = []
        vals = {"name": name, "offset": off, "size": size, "sha256": None}
        if off < 0 or size < 0 or off + size > len(b):
            issues.append("oob_pointer")
            damage(res, D.OOB_POINTER, eo, eo, f"entry {name!r}: offset {off} + size {size} is outside the "
                   f"file ({len(b)} bytes)", affected=[name])
        elif size and (off < 12 or (dir_start < off + size and off < dir_end)):
            issues.append("oob_pointer")
            damage(res, D.OOB_POINTER, eo, eo, f"entry {name!r}: data overlaps the header or directory",
                   affected=[name])
        else:
            vals["sha256"] = sha256(b[off:off + size])
        if not name or not name.isprintable():
            issues.append("invalid_value")
        res.records.append(record(i, eo, vals, verified=not issues, issues=issues))


@register
class WadDecoder(Decoder):
    name = "WAD"
    spec = WAD_SPEC
    ready = True

    def sniff(self, data: bytes) -> float:
        return 1.0 if data[:4] in (b"IWAD", b"PWAD") else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 12:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), "file ends inside the 12-byte header")
            return res
        ident, n, do = struct.unpack_from("<4sii", b)
        res.metadata = {"ident": ident.decode("latin-1"), "lump_count": n, "directory_offset": do}
        if do < 12 or do > len(b) or n < 0:
            damage(res, D.INDEX_MISSING, 4, 12, f"directory at {do} ({n} entries) is outside the file")
            res.status = "failed"
            return res
        have = min(n, (len(b) - do) // 16)
        if have < n:
            damage(res, D.TRUNCATED, do + 16 * have, len(b), f"directory cut off: {have} of {n} entries")
        ents = []
        for i in range(have):
            eo = do + 16 * i
            off, size, nm = struct.unpack_from("<ii8s", b, eo)
            ents.append((eo, _name(nm), off, size))
        _entries(res, b, ents, do, do + 16 * n)
        return res


@register
class PakDecoder(Decoder):
    name = "PAK"
    spec = PAK_SPEC
    ready = True

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 12:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), "file ends inside the 12-byte header")
            return res
        _, do, dl = struct.unpack_from("<4sii", b)
        res.metadata = {"directory_offset": do, "directory_length": dl, "entry_count": max(0, dl) // 64}
        if do < 12 or do > len(b) or dl < 0:
            damage(res, D.INDEX_MISSING, 4, 12, f"directory at {do} (+{dl} bytes) is outside the file")
            res.status = "failed"
            return res
        if dl % 64:
            damage(res, D.BAD_LENGTH, 8, 12, f"directory length {dl} is not a multiple of 64", lossy=False)
        n = dl // 64
        have = min(n, (len(b) - do) // 64)
        if have < n:
            damage(res, D.TRUNCATED, do + 64 * have, len(b), f"directory cut off: {have} of {n} entries")
        ents = []
        for i in range(have):
            eo = do + 64 * i
            nm, off, size = struct.unpack_from("<56sii", b, eo)
            ents.append((eo, _name(nm), off, size))
        _entries(res, b, ents, do, do + dl)
        return res
