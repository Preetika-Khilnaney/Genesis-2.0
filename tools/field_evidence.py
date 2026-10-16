#!/usr/bin/env python3
"""Re-test every format hypothesis against the real samples and write the results to FIELD-LOG.md.

    python3 tools/field_evidence.py            # appends one row per hypothesis (accepted AND rejected)
    python3 tools/field_evidence.py --dry-run  # print only

Every row is reproducible: the test below runs on the named real samples with the all-samples rule
(evidence/checker.py): accepted only if it holds on every listed file, rejected on any counterexample.
Rejected rows are the alternatives we tried and the bytes ruled out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import json
import os
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from salvage.formats import cvt, documents, ebcdic, lablog, libra98, vault  # noqa: E402
from salvage.recovery.crc import crc16_ccitt  # noqa: E402

S = ROOT / "real-samples" / "samples"
EXP = ROOT / "real-samples" / "expected_outputs"
BY = "Preetika"


def f(name: str) -> bytes:
    return (S / name).read_bytes()


def exp(name: str) -> dict:
    return json.loads((EXP / f"{name}.json").read_text(encoding="utf-8"))


u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]  # noqa: E731
u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]  # noqa: E731
be16 = lambda b, o: struct.unpack_from(">H", b, o)[0]  # noqa: E731


# ---------------- LIBRA-98 helpers
def libra_records(b: bytes):
    p, out = u16(b, 12), []
    while p + 2 <= len(b) and b[p] == 0xA5 and p + 2 + b[p + 1] <= len(b):
        out.append(b[p:p + 2 + b[p + 1]])
        p += 2 + b[p + 1]
    return out, p


def libra_all(b, test):
    recs, _ = libra_records(b)
    return bool(recs) and all(test(r) for r in recs)


def libra_title_year(r: bytes):
    q = 7
    q += 1 + r[q]
    q += 1 + r[q]
    return u16(r, q)


# ---------------- LABLOG helpers
def lablog_blocks(b: bytes):
    p, out = 32, []
    while p + 6 <= len(b) and b[p] == 0xB1:
        L = u16(b, p + 2)
        if p + 6 + L > len(b):
            break
        out.append((p, L))
        p += 6 + L
    return out


def lablog_crc_ok(b, covered_fn):
    blocks = lablog_blocks(b)
    return all(crc16_ccitt(covered_fn(b, p, L)) == u16(b, p + 4 + L) for p, L in blocks)


# ---------------- VAULT helpers
def vault_entries(b: bytes):
    n, idx = u16(b, 4), u32(b, 8)
    return [struct.unpack_from("<HBBIIHH", b, idx + 16 * e) for e in range(n)]


def vault_decoded(b: bytes, rle_fn=vault.rle90):
    key, out = b[6], []
    for eid, typ, fl, noff, boff, slen, size in vault_entries(b):
        body = b[boff + 4:boff + 4 + slen]
        data, crc = body[:-4], u32(body, len(body) - 4)
        d = vault.xor(data, key) if fl & 2 else data
        try:
            d = rle_fn(d) if fl & 1 else d
        except Exception:
            d = None
        out.append((eid, typ, fl, size, d, crc))
    return out


def rle_repeat_n(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        c = data[i]
        if c == 0x90 and i + 1 < len(data):
            n = data[i + 1]
            out += bytes([0x90]) if n == 0 else bytes([out[-1]]) * n
            i += 2
        else:
            out.append(c)
            i += 1
    return bytes(out)


def wks_tiles(b: bytes) -> bool:
    p = 0
    while p + 4 <= len(b):
        op, L = struct.unpack_from("<HH", b, p)
        if op == 1:
            return p + 4 + L == len(b)
        p += 4 + L
    return False


LIBRA_OK = ["s01.dat", "s02.dat", "s03.dat"]          # complete files
LIBRA_ALL = LIBRA_OK + ["s04.dat"]
LAB = ["s05.dat", "s06.dat", "s07.dat"]
VLT = ["s08.dat", "s09.dat", "s10.dat"]
WKS = ["s11.wks", "s12.wks", "s13.wks"]
EBC_FULL = ["s20.000", "s21.000"]

H = [
    # (format, hypothesis, files, test(bytes) -> bool)
    ("LIBRA-98", "bytes 0-3 are the magic 'LB98'", LIBRA_ALL + ["s29_almost_libra.dat"], lambda b: b[:4] == b"LB98"),
    ("LIBRA-98", "u16 at 6 is the record count (= records in the file)", LIBRA_OK,
     lambda b: len(libra_records(b)[0]) == u16(b, 6)),
    ("LIBRA-98", "u32 at 8 is a unix timestamp (1990-2000)", LIBRA_ALL,
     lambda b: 1990 <= dt.datetime.fromtimestamp(u32(b, 8), dt.timezone.utc).year <= 2000),
    ("LIBRA-98", "u16 at 8 + u16 at 10 are a DOS date + DOS time = expected 'created'", ["s01.dat", "s04.dat"],
     lambda b: libra98.dos_datetime(u16(b, 8), u16(b, 10)) == exp([k for k in ("s01.dat", "s04.dat") if f(k) == b][0])["metadata"]["created"]),
    ("LIBRA-98", "u16 at 12 is the data offset (first 0xA5 record marker there)", LIBRA_ALL, lambda b: b[u16(b, 12)] == 0xA5),
    ("LIBRA-98", "record length byte = whole record size", LIBRA_OK,
     lambda b: (lambda p: b[p + b[p + 1]] == 0xA5)(u16(b, 12))),
    ("LIBRA-98", "record length byte = bytes after the length byte (records tile to the END! trailer)", LIBRA_OK,
     lambda b: b[libra_records(b)[1]:libra_records(b)[1] + 4] == b"END!"),
    ("LIBRA-98", "record checksum = XOR of the record bytes", LIBRA_OK,
     lambda b: libra_all(b, lambda r: functools.reduce(lambda x, y: x ^ y, r[:-1], 0) == r[-1])),
    ("LIBRA-98", "record checksum = sum of marker..last field (mod 256)", LIBRA_OK,
     lambda b: libra_all(b, lambda r: sum(r[:-1]) & 255 == r[-1])),
    ("LIBRA-98", "record checksum = sum of bytes after the length byte (mod 256)", LIBRA_ALL,
     lambda b: libra_all(b, lambda r: sum(r[2:-1]) & 255 == r[-1])),
    ("LIBRA-98", "year is stored as-is (u16)", LIBRA_OK, lambda b: libra_all(b, lambda r: 1400 < libra_title_year(r) < 2100)),
    ("LIBRA-98", "year is stored as year - 1500 (Dracula 397 -> 1897)", LIBRA_OK,
     lambda b: libra_all(b, lambda r: 1400 < libra_title_year(r) + 1500 < 2000)),
    ("LIBRA-98", "flags bit0 = checked_out: set exactly when a due date is present", LIBRA_OK,
     lambda b: libra_all(b, lambda r: bool(r[2] & 1) == bool(u16(r, len(r) - 3)))),
    ("LIBRA-98", "encoding flag 0 text is latin-1", ["s02.dat"],
     lambda b: "\x82" not in b.decode("latin-1")),
    ("LIBRA-98", "encoding flag 0 text is cp437 (0x82 = e-acute in 'Miserables')", ["s02.dat"],
     lambda b: "Misérables" in b.decode("cp437")),
    ("LIBRA-98", "trailer 'END!' + u16 = sum of records only", LIBRA_OK,
     lambda b: u16(b, libra_records(b)[1] + 4) == sum(b[u16(b, 12):libra_records(b)[1]]) & 0xFFFF),
    ("LIBRA-98", "trailer 'END!' + u16 = sum of every byte before the trailer (mod 65536)", LIBRA_OK,
     lambda b: u16(b, libra_records(b)[1] + 4) == sum(b[:libra_records(b)[1]]) & 0xFFFF),

    ("LABLOG", "bytes 0-3 are the magic 'LLOG'", LAB, lambda b: b[:4] == b"LLOG"),
    ("LABLOG", "u16 at 6 is the sample interval in ms", ["s05.dat"], lambda b: u16(b, 6) == 500),
    ("LABLOG", "u16 at 6 is the sample interval in 10 ms units (50 -> 500 ms)", ["s05.dat"], lambda b: u16(b, 6) * 10 == 500),
    ("LABLOG", "u32 at 24 = seconds since 1970-01-01", ["s05.dat"],
     lambda b: dt.datetime.fromtimestamp(u32(b, 24), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") == exp("s05.dat")["metadata"]["start_time_utc"]),
    ("LABLOG", "u32 at 24 = seconds since 1990-01-01", ["s05.dat"],
     lambda b: (dt.datetime(1990, 1, 1) + dt.timedelta(seconds=u32(b, 24))).strftime("%Y-%m-%dT%H:%M:%SZ") == exp("s05.dat")["metadata"]["start_time_utc"]),
    ("LABLOG", "u16 at 30 = CRC-16/CCITT-FALSE of header bytes 0..29", LAB, lambda b: crc16_ccitt(b[:30]) == u16(b, 30)),
    ("LABLOG", "block CRC covers the payload only", ["s05.dat", "s06.dat"],
     lambda b: lablog_crc_ok(b, lambda b, p, L: b[p + 4:p + 4 + L])),
    ("LABLOG", "block CRC covers marker + type + length + payload", ["s05.dat", "s06.dat"],
     lambda b: lablog_crc_ok(b, lambda b, p, L: b[p:p + 4 + L])),
    ("LABLOG", "block CRC = CRC-16/CCITT-FALSE of type + length + payload (s07 block 4 is damaged: see next row)",
     ["s05.dat", "s06.dat"], lambda b: lablog_crc_ok(b, lambda b, p, L: b[p + 1:p + 4 + L])),
    ("LABLOG", "s07 block 4 fails its CRC and exactly one flipped bit explains it (provable repair)", ["s07.dat"],
     lambda b: (lambda p, L: lablog._single_bit_fix(b[p + 1:p + 4 + L], u16(b, p + 4 + L)) is not None)(*lablog_blocks(b)[4])),
    ("LABLOG", "header u16 at 28 = number of blocks", LAB, lambda b: len(lablog_blocks(b)) == u16(b, 28)),
    ("LABLOG", "value = raw i16 * channel scale + channel offset (all 44 values of expected s05)", ["s05.dat"],
     lambda b: [r["values"] for r in exp("s05.dat")["records"]] ==
     [r.values["values"] for r in lablog.LablogDecoder().decode("s05.dat", b).records]),

    ("VAULT", "bytes 0-3 are the magic 'VLT1'", VLT, lambda b: b[:4] == b"VLT1"),
    ("VAULT", "index (u32 at 8) of 16-byte entries ends exactly at end of file", VLT, lambda b: u32(b, 8) + 16 * u16(b, 4) == len(b)),
    ("VAULT", "names XOR with a constant key", VLT,
     lambda b: all(vault.xor(b[u32(b, 12) + e[3] + 1:u32(b, 12) + e[3] + 1 + (b[u32(b, 12) + e[3]] ^ (b[6] if b[7] & 1 else 0))], 0).isascii() and
                   bytes(c ^ b[6] for c in b[u32(b, 12) + e[3] + 1:u32(b, 12) + e[3] + 4]).isalpha() for e in vault_entries(b))),
    ("VAULT", "names XOR with (key + i), length byte XOR'd too when header flag bit0 is set", VLT,
     lambda b: all(vault._plausible_name(vault.xor(b[u32(b, 12) + e[3] + 1:u32(b, 12) + e[3] + 1 + (b[u32(b, 12) + e[3]] ^ (b[6] if b[7] & 1 else 0))], b[6]).decode())
                   for e in vault_entries(b))),
    ("VAULT", "entry flags bit0 = RLE-compressed (matches expected 'compressed')", ["s08.dat"],
     lambda b: [bool(e[2] & 1) for e in vault_entries(b)] == [r["compressed"] for r in exp("s08.dat")["records"]]),
    ("VAULT", "blob CRC-32 is over the stored (encoded) bytes", ["s08.dat", "s09.dat"],
     lambda b: all(zlib.crc32(b[e[4] + 4:e[4] + e[5]]) == u32(b, e[4] + e[5]) for e in vault_entries(b))),
    ("VAULT", "blob CRC-32 is over the decoded data", ["s08.dat", "s09.dat"],
     lambda b: all(d is not None and zlib.crc32(d) == crc for _, _, _, _, d, crc in vault_decoded(b))),
    ("VAULT", "RLE90: 0x90 n = repeat the previous byte n times", ["s09.dat"],
     lambda b: all(d is not None and len(d) == size for _, _, fl, size, d, _ in vault_decoded(b, rle_repeat_n) if fl & 1)),
    ("VAULT", "RLE90: 0x90 n = repeat the previous byte n-1 more times; 0x90 0x00 = literal 0x90", VLT,
     lambda b: all(d is not None and len(d) == size for _, _, fl, size, d, _ in vault_decoded(b) if fl & 1)),
    ("VAULT", "bitmap payload = u8 width, u8 height, width*height pixels", ["s09.dat", "s10.dat"],
     lambda b: all(len(d) == 2 + d[0] * d[1] for _, typ, _, _, d, _ in vault_decoded(b) if typ == 2)),
    ("VAULT", "s10 sensor.bin fails its CRC-32 and exactly one flipped bit explains it", ["s10.dat"],
     lambda b: (lambda e: vault._single_bit_fix(b[e[4] + 4:e[4] + e[5]], e[2], b[6], u32(b, e[4] + e[5])) is not None)(vault_entries(b)[1])),

    ("WKS", "file starts with BOF (opcode 0, length 2, version 0x0404)", WKS, lambda b: b[:6] == bytes.fromhex("000002000404")),
    ("WKS", "records (u16 opcode, u16 length, body) tile the file up to EOF", ["s11.wks", "s12.wks"],
     lambda b: wks_tiles(b)),
    ("WKS", "formula body = f64 cached value, u16 length, formula bytes (matches expected s11)", ["s11.wks"],
     lambda b: struct.unpack_from("<d", b, 185 + 9)[0] == 939.53 and u16(b, 185 + 17) == 12),
    ("WKS", "unknown opcode 0x00FA in s12 is a valid record we can skip (lengths still tile)", ["s12.wks"],
     lambda b: u16(b, 115) == 0xFA and u16(b, 115 + 4 + u16(b, 117)) == 0x0F),

    ("CVT", "signature 'PRG formatted GEOS file' at offset 30", ["s18.cvt", "s19.cvt"], lambda b: b[30:53] == b"PRG formatted GEOS file"),
    ("CVT", "name is PETSCII with case swapped (expected 'Notes v2')", ["s18.cvt"], lambda b: cvt._field(b[3:19]) == "Notes v2"),
    ("CVT", "year byte = year - 1900 (91 -> 1991, 101 -> 2001)", ["s18.cvt", "s19.cvt"], lambda b: 1980 <= 1900 + b[23] <= 2010),
    ("CVT", "declared blocks = 254-byte blocks after the first", ["s18.cvt", "s19.cvt"],
     lambda b: (len(b) - 254) / 254 == b[28] | b[29] << 8),
    ("CVT", "vlir bytes-used = stored value - 1 (as on a real 1541 disk)", ["s19.cvt"],
     lambda b: cvt.petscii(b[762:762 + b[509] - 1]) == "First record, short."),
    ("CVT", "vlir bytes-used = stored value as-is ('First record, short.' keeps its '.')", ["s19.cvt"],
     lambda b: cvt.petscii(b[762:762 + b[509]]) == "First record, short."),

    ("EBCDIC-DUMP", "text is EBCDIC code page 037", EBC_FULL + ["s22.000"], lambda b: "STUDENT EXTRACT" in b.decode("cp037")),
    ("EBCDIC-DUMP", "RDW = u16 big-endian length incl. the 4-byte RDW, then 00 00", ["s20.000", "s22.000"],
     lambda b: be16(b, 0) == 33 and b[2:4] == b"\0\0"),
    ("EBCDIC-DUMP", "s21 is blocked: BDW (u16be length, 00 00) wraps RDW records", ["s21.000"],
     lambda b: be16(b, 0) == 85 and be16(b, 4) == 33 and b[8] == 0xC8),
    ("EBCDIC-DUMP", "credits are packed decimal", ["s20.000"], lambda b: ebcdic.packed(b[33 + 4 + 35:33 + 4 + 37])[1]),
    ("EBCDIC-DUMP", "credits are a u16 big-endian binary number (00 28 -> 40)", ["s20.000"], lambda b: be16(b, 33 + 4 + 35) == 40),
    ("EBCDIC-DUMP", "trailer count and credits total equal the detail records", EBC_FULL,
     lambda b: not any(d.cause.value in ("count_mismatch", "checksum_mismatch")
                       for d in ebcdic.EbcdicDecoder().decode("x", b).damage)),

    ("WPD", "u32 at 4 is the text start (48)", ["s14.wpd", "s15.wpd"], lambda b: u32(b, 4) == 48 and b[48:58] == b"MEMORANDUM"),
    ("WPD", "summary packet index at 0x1E: u16 type 1, u16 length, u32 offset (s14: text ends there)", ["s14.wpd"],
     lambda b: u16(b, 0x1E) == 1 and b[u32(b, 0x22) - 1] == 0x0A),
    ("WPD", "s15 is truncated: its index points at byte 223 but the file is 136 bytes", ["s15.wpd"], lambda b: u32(b, 0x22) == 223 > len(b)),
    ("WPD", "u16 at 12 is an encryption key (0 = not protected)", ["s14.wpd", "s15.wpd"], lambda b: u16(b, 12) == 0),

    ("BRAVO", "text, ^Z, then format runs", ["s16.bravo", "s17.bravo"], lambda b: b"\x1a" in b and b"\r" in b[:b.index(b"\x1a")]),
    ("BRAVO", "run table length counts bytes", ["s16.bravo"],
     lambda b: (lambda p: be16(b, p) == len(b) - p - 2)((b.index(b"\x1a") + 2) // 2 * 2)),
    ("BRAVO", "run table length counts 16-bit words (s16: 6 words = 12 bytes, exactly)", ["s16.bravo"],
     lambda b: (lambda p: be16(b, p) * 2 == len(b) - p - 2)((b.index(b"\x1a") + 2) // 2 * 2)),
    ("BRAVO", "run = u16be start, u16be length, u8 looks, u8 font ('Alto users' at 4, length 10)", ["s16.bravo"],
     lambda b: [(r["start"], r["length"]) for r in documents.BravoDecoder().decode("x", b).metadata["format_runs"]] == [(4, 10), (67, 15)]),

    ("WAD", "PWAD header: i32 count, i32 directory offset; 16-byte entries end at EOF", ["s23.wad"],
     lambda b: struct.unpack_from("<i", b, 8)[0] + 16 * struct.unpack_from("<i", b, 4)[0] == len(b)),
    ("PAK", "PACK header: i32 directory offset, i32 length; 64-byte entries end at EOF", ["s24.pak"],
     lambda b: sum(struct.unpack_from("<ii", b, 4)) == len(b)),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run:
        os.environ["SALVAGE_LOG"] = "1"
    from salvage.evidence.checker import evaluate
    for fmt, hyp, files, test in H:
        samples = [f(n) for n in files]
        v = evaluate(fmt, f"{hyp} [{', '.join(files)}]", samples, test, author=BY, log=not a.dry_run)
        print(f"{v.outcome:9} {v.held}/{v.total}  {fmt:12} {hyp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
