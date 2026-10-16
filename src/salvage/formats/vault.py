"""VAULT: school-office archive (notes and scans in one container). OWNER: Khushi (recovery).

Layout, worked out from real-samples s08-s10 and expected_outputs/s08 (evidence in FIELD-LOG.md):

  Header (16 bytes, little-endian)
    0 4 magic "VLT1"   4 2 entry count   6 1 XOR key   7 1 flags (bit0: name lengths XOR'd too)
    8 4 index offset   12 4 name-table offset
  Index (entry count x 16 bytes)
    u16 id, u8 type (1 text, 2 bitmap, 3 binary), u8 flags (bit0 RLE90, bit1 XOR),
    u32 name offset (into the name table), u32 blob offset, u16 stored length, u16 decoded size
  Name table: u8 length + name, each byte XOR (key + i)
  Blob at blob offset: "BL", u16 id, then stored-length bytes = data + u32 CRC-32 of the DECODED data
    data: XOR (key + i) if flag bit1, then RLE90 (0x90 n: repeat previous byte n-1 more times;
    0x90 0x00 = a literal 0x90) if flag bit0
  Bitmap payload: u8 width, u8 height, width*height pixels.

Verification: an entry is verified when its CRC-32 matches the decoded data and the decoded size
matches the index. If XOR and RLE could apply in either order, the CRC decides which is right.
"""
from __future__ import annotations

import struct
import zlib

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, record, sha256

MAGIC = b"VLT1"
TYPES = {1: "text", 2: "bitmap", 3: "binary"}

VAULT_SPEC = FormatSpec(
    name="VAULT",
    magic=MAGIC,
    description="Archive: header, index table, XOR-obscured name table, and blobs (optionally XOR'd "
                "and RLE90-compressed), each with a CRC-32 of its decoded data.",
    checksum="CRC-32 (zlib) of the decoded payload, little-endian, after the blob data",
    header=[
        FieldSpec("magic", "bytes", 4, "'VLT1'", "all samples"),
        FieldSpec("entry_count", "u16", desc="index entries", evidence="expected s08"),
        FieldSpec("xor_key", "u8", desc="XOR key; byte i uses key+i", evidence="names decode; expected s08 = 32"),
        FieldSpec("flags", "u8", desc="bit0: name lengths XOR'd with the key", evidence="s09 (flag 1) name lengths"),
        FieldSpec("index_offset", "u32", desc="index table offset", evidence="index ends exactly at EOF"),
        FieldSpec("names_offset", "u32", desc="name table offset", evidence="names decode"),
    ],
    record=[
        FieldSpec("id", "u16", desc="entry id (repeated after 'BL' in the blob)", evidence="expected s08"),
        FieldSpec("type", "u8", desc="1 text, 2 bitmap, 3 binary", evidence="expected s08 types"),
        FieldSpec("flags", "u8", desc="bit0 RLE90-compressed, bit1 XOR'd", evidence="expected 'compressed'"),
        FieldSpec("name_offset", "u32", desc="offset in the name table", evidence="names decode"),
        FieldSpec("blob_offset", "u32", desc="offset of 'BL' blob", evidence="'BL'+id found there"),
        FieldSpec("stored_length", "u16", desc="data + 4-byte CRC", evidence="tiles blobs exactly"),
        FieldSpec("size", "u16", desc="decoded size", evidence="expected s08 sizes"),
    ],
)


def xor(data: bytes, key: int) -> bytes:
    return bytes(c ^ ((key + i) & 0xFF) for i, c in enumerate(data))


class RLEError(ValueError):
    pass


def rle90(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        c = data[i]
        if c != 0x90:
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(data):
            raise RLEError("data ends after an 0x90 escape")
        n = data[i + 1]
        i += 2
        if n == 0:
            out.append(0x90)
        elif not out:
            raise RLEError("repeat escape before any byte")
        else:
            out += bytes([out[-1]]) * (n - 1)
    return bytes(out)


def _decode_blob(data: bytes, flags: int, key: int, crc: int) -> tuple[bytes | None, str]:
    """Undo XOR/RLE per the flags. Returns (payload or None, how). The CRC picks the order."""
    rle, xr = bool(flags & 1), bool(flags & 2)
    candidates = []
    if rle and xr:
        candidates = [("xor then rle90", lambda d: rle90(xor(d, key))), ("rle90 then xor", lambda d: xor(rle90(d), key))]
    elif rle:
        candidates = [("rle90", rle90)]
    elif xr:
        candidates = [("xor", lambda d: xor(d, key))]
    else:
        candidates = [("stored", lambda d: d)]
    first = None
    for how, f in candidates:
        try:
            out = f(data)
        except RLEError:
            continue
        if zlib.crc32(out) == crc:
            return out, how
        first = first or (out, how)
    return (first[0], first[1]) if first else (None, "undecodable")


NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")


def _plausible_name(name: str) -> bool:
    """A file name: 1-64 ordinary file-name characters with one extension dot. The name table has no
    checksum, so a damaged name can only be caught by its shape."""
    return (0 < len(name) <= 64 and "\ufffd" not in name and all(c in NAME_CHARS for c in name)
            and name.count(".") == 1 and not name.startswith(".") and not name.endswith("."))


def _single_bit_fix(stored: bytes, flags: int, key: int, crc: int, limit: int = 4096) -> tuple[bytes, int, str] | None:
    """Exactly one flipped bit in the stored data that makes the CRC-32 match -> (payload, bit, how).
    CRC-32 pins a single-bit error down uniquely, so a unique hit is a proven repair."""
    if len(stored) > limit:
        return None
    hits = []
    for bit in range(len(stored) * 8):
        c = bytearray(stored)
        c[bit // 8] ^= 1 << (bit % 8)
        out, how = _decode_blob(bytes(c), flags, key, crc)
        if out is not None and zlib.crc32(out) == crc:
            hits.append((out, bit, how))
            if len(hits) > 1:
                return None
    return hits[0] if hits else None


@register
class VaultDecoder(Decoder):
    name = "VAULT"
    spec = VAULT_SPEC
    ready = True

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 16:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), f"file is {len(b)} bytes; the VAULT header needs 16")
            return res
        n, key, hflags = struct.unpack_from("<HBB", b, 4)
        idx, names = struct.unpack_from("<II", b, 8)
        res.metadata = {"entry_count": n, "xor_key": key, "flags": hflags}
        if idx + 16 * n > len(b):
            if idx >= len(b):
                damage(res, D.INDEX_MISSING, 8, 12, f"index offset {idx} is past the end of the file")
                res.status = "failed"
                return res
            damage(res, D.TRUNCATED, idx, len(b), f"index table cut off: {(len(b) - idx) // 16} of {n} entries")
        names_ok = names < len(b)
        if not names_ok:
            damage(res, D.OOB_POINTER, 12, 16, f"name table offset {names} is past the end of the file")
        for e in range(n):
            o = idx + 16 * e
            if o + 16 > len(b):
                break
            eid, typ, efl, noff, boff, slen, size = struct.unpack_from("<HBBIIHH", b, o)
            issues: list[str] = []
            name = None
            if names_ok and names + noff < len(b):
                L = b[names + noff] ^ (key if hflags & 1 else 0)
                raw = b[names + noff + 1:names + noff + 1 + L]
                if len(raw) == L:
                    try:
                        name = xor(raw, key).decode("utf-8")
                    except UnicodeDecodeError:
                        name = xor(raw, key).decode("utf-8", "replace")
                    if not _plausible_name(name):
                        issues.append("invalid_value")    # names have no checksum: check what we can
                else:
                    issues.append("oob_pointer")
            else:
                issues.append("oob_pointer")
            vals = {"id": eid, "name": name, "type": TYPES.get(typ, "binary"), "size": size,
                    "sha256": None, "compressed": bool(efl & 1)}
            if typ not in TYPES:
                issues.append("invalid_value")
            if boff + 4 + slen > len(b) or slen < 4:
                issues.append("oob_pointer" if boff >= len(b) else "truncated")
                damage(res, D.OOB_POINTER if boff >= len(b) else D.TRUNCATED, o if boff >= len(b) else boff,
                       o + 16 if boff >= len(b) else len(b),
                       f"entry {eid}: blob at {boff} (+{slen + 4} bytes) does not fit in the file",
                       affected=[f"entry {eid}"])
                res.records.append(record(e, o, vals, verified=False, issues=issues))
                continue
            if b[boff:boff + 2] != b"BL" or struct.unpack_from("<H", b, boff + 2)[0] != eid:
                issues.append("oob_pointer")
                damage(res, D.OOB_POINTER, o, o + 16, f"entry {eid}: no 'BL'+id blob header at {boff}",
                       affected=[f"entry {eid}"])
            body = b[boff + 4:boff + 4 + slen]
            repaired = False
            stored, crc = body[:-4], struct.unpack_from("<I", body, len(body) - 4)[0]
            out, how = _decode_blob(stored, efl, key, crc)
            if out is None:
                issues.append("invalid_value")
                damage(res, D.INVALID_VALUE, boff, boff + 4 + slen, f"entry {eid}: RLE90 data is malformed",
                       affected=[f"entry {eid}"])
            else:
                if zlib.crc32(out) != crc:
                    fix = _single_bit_fix(stored, efl, key, crc)
                    if fix is not None:
                        out, bit, how = fix
                        damage(res, D.CRC_MISMATCH, boff, boff + 4 + slen,
                               f"entry {eid} ({name}): CRC-32 mismatch repaired: exactly one flipped bit "
                               f"(data byte {bit // 8}, bit {bit % 8}) explains it", lossy=False)
                        issues.append("crc_mismatch")
                        repaired = True
                    else:
                        repaired = False
                        issues.append("crc_mismatch")
                        damage(res, D.CRC_MISMATCH, boff, boff + 4 + slen,
                               f"entry {eid} ({name}): CRC-32 {crc:#010x} != computed {zlib.crc32(out):#010x}",
                               affected=[f"entry {eid}"])
                else:
                    repaired = False
                vals["sha256"] = sha256(out)
                if len(out) != size:
                    issues.append("bad_length")
                    damage(res, D.BAD_LENGTH, o + 14, o + 16, f"entry {eid}: decoded {len(out)} bytes, index says {size}")
                if typ == 1:
                    vals["text"] = out.decode("utf-8", "replace")
                elif typ == 2 and len(out) >= 2:
                    vals["width"], vals["height"] = out[0], out[1]
                    if 2 + out[0] * out[1] != len(out):
                        issues.append("bad_length")
            hard = [i for i in issues if not (i == "crc_mismatch" and out is not None and repaired)]
            res.records.append(record(e, o, vals, verified=not hard, issues=issues))
        # Names, types and flags are not covered by any checksum. If some entry failed its CRC and
        # could not be repaired, the damage is not a single isolated bit, so nothing unprotected in
        # this archive can be trusted: the other entries are kept but marked unverified.
        if any(d.cause == D.CRC_MISMATCH and d.lossy for d in res.damage):
            for r in res.records:
                if r.verified:
                    r.verified = False
                    r.issues.append("crc_mismatch")
            res.warnings.append("another entry failed its CRC: names and index fields (no checksum) are unverified")
        return res
