"""LIBRA-98: municipal library circulation records (~1998). OWNER: Preetika (decoder) + Bhupesh (evidence).

Layout, worked out from real-samples s01-s04 and expected_outputs (every claim is in FIELD-LOG.md):

  Header (16 bytes, little-endian)
    0   4  magic "LB98"
    4   1  version (2 in every sample)
    5   1  encoding flag: 0 = cp437 (DOS), 1 = cp1252     (s02 'Mis\\x82rables' = cp437 e-acute)
    6   2  declared record count
    8   2  created date (DOS date)          10  2  created time (DOS time)
    12  2  data offset (16, or 40 when an extra header block follows: s03 'LIBSYS/98 REL 2.1')
    14  2  branch id
  Record (from data offset, repeated)
    0   1  marker 0xA5
    1   1  length L = number of bytes that follow
    2   1  flags: bit0 checked_out, bit1 deleted, bit2 reference_only
    3   4  id
    7   .  title  (u8 length + text)        .  author (u8 length + text)
    .   2  year - 1500                       .  2  price in cents
    .   1  copies                            .  10 ISBN (ASCII)
    .   2  due date (DOS date, 0 = none)    .  1  checksum = sum of bytes 2..L (mod 256)
  Trailer
    "END!" + u16 sum of every byte before the trailer (mod 65536)

Verification: a record is verified when its own checksum matches and its fields consume exactly
L bytes. The trailer sum covers the header too. Damage is reported, never patched over.
"""
from __future__ import annotations

import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, dos_date, dos_datetime, record, sum8, sum16

MAGIC = b"LB98"
MARKER = 0xA5
TRAILER = b"END!"
ENCODINGS = {0: "cp437", 1: "cp1252"}
FLAG_BITS = (("checked_out", 0x01), ("deleted", 0x02), ("reference_only", 0x04))

LIBRA98_SPEC = FormatSpec(
    name="LIBRA-98",
    magic=MAGIC,
    endian="little",
    description=("Library circulation file: 16-byte header, then variable-length records each with "
                 "its own sum-8 checksum, then an 'END!' trailer with a sum-16 over the whole file."),
    checksum="per record: sum of bytes after the length field (mod 256); trailer: sum16 of all bytes before it",
    header=[
        FieldSpec("magic", "bytes", 4, "'LB98'", "same in all samples"),
        FieldSpec("version", "u8", desc="format version", evidence="2 in all samples"),
        FieldSpec("encoding", "u8", desc="0 = cp437, 1 = cp1252", evidence="s02 text decodes only as cp437; s03 flag 1"),
        FieldSpec("declared_record_count", "u16", desc="records declared", evidence="matches record count in s01-s03"),
        FieldSpec("created_date", "dos_date", desc="creation date", evidence="matches expected s01, s04"),
        FieldSpec("created_time", "dos_time", desc="creation time", evidence="matches expected s01, s04"),
        FieldSpec("data_offset", "u16", desc="first record offset", evidence="16, or 40 with an extra header (s03)"),
        FieldSpec("branch_id", "u16", desc="library branch", evidence="matches expected s01, s04"),
    ],
    record=[
        FieldSpec("marker", "u8", desc="0xA5", evidence="every record"),
        FieldSpec("length", "u8", desc="bytes after this field", evidence="tiles records exactly"),
        FieldSpec("flags", "u8", desc="bit0 checked_out, bit1 deleted, bit2 reference_only",
                  evidence="bit0 set exactly when a due date exists; bit1/bit2 order from the contract field order"),
        FieldSpec("id", "u32", desc="record id", evidence="matches expected"),
        FieldSpec("title", "pstr8", desc="title", evidence="matches expected"),
        FieldSpec("author", "pstr8", desc="author", evidence="matches expected"),
        FieldSpec("year", "u16", desc="publication year - 1500", evidence="397 -> 1897 (Dracula)"),
        FieldSpec("price_cents", "u16", desc="price in cents", evidence="matches expected"),
        FieldSpec("copies", "u8", desc="copies held", evidence="matches expected"),
        FieldSpec("isbn", "str", 10, desc="ISBN-10", evidence="matches expected"),
        FieldSpec("due_date", "dos_date", desc="due date, 0 = none", evidence="0x2593 -> 1998-12-19"),
        FieldSpec("checksum", "u8", desc="sum of bytes after length", evidence="holds on all 22 complete records"),
    ],
    record_count_field="declared_record_count",
    notes=["Trailer 'END!' + u16 sum of all preceding bytes (holds on s01-s03; s04 is truncated)."],
)


def _parse_body(body: bytes, enc: str) -> dict | None:
    """Fields of one record body (bytes after the length byte, checksum excluded)."""
    try:
        flags = body[0]
        rid = struct.unpack_from("<I", body, 1)[0]
        q = 5
        tl = body[q]; title = body[q + 1:q + 1 + tl]; q += 1 + tl
        al = body[q]; author = body[q + 1:q + 1 + al]; q += 1 + al
        if len(title) != tl or len(author) != al:
            return None
        year, price = struct.unpack_from("<HH", body, q); q += 4
        copies = body[q]; q += 1
        isbn = body[q:q + 10]; q += 10
        due = struct.unpack_from("<H", body, q)[0]; q += 2
        if q != len(body) or len(isbn) != 10:
            return None
    except (IndexError, struct.error):
        return None
    v = {"id": rid, "title": title.decode(enc, "replace"), "author": author.decode(enc, "replace"),
         "year": 1500 + year, "price_cents": price, "copies": copies,
         "isbn": isbn.decode("ascii", "replace")}
    for name, bit in FLAG_BITS:
        v[name] = bool(flags & bit)
    v["due_date"] = dos_date(due)
    v["_flags"], v["_due_raw"] = flags, due
    v["_non_ascii"] = any(c >= 0x80 for c in title + author)
    return v


ORDER = ("id", "title", "author", "year", "price_cents", "copies", "isbn",
         "checked_out", "deleted", "reference_only", "due_date")


def _valid_record_at(b: bytes, p: int, enc: str) -> bool:
    if p + 2 > len(b) or b[p] != MARKER:
        return False
    L = b[p + 1]
    if L < 2 or p + 2 + L > len(b):
        return False
    return sum8(b[p + 2:p + 1 + L]) == b[p + 1 + L] and _parse_body(b[p + 2:p + 1 + L], enc) is not None


@register
class Libra98Decoder(Decoder):
    name = "LIBRA-98"
    spec = LIBRA98_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        """Damaged magic: records with valid checksums from offset 16 still identify the file."""
        p, ok = 16, 0
        while ok < 3 and _valid_record_at(data, p, "cp437"):
            p += 2 + data[p + 1]
            ok += 1
        return 1.0 if ok >= 2 else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 16:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), f"file is {len(b)} bytes; the LIBRA-98 header needs 16")
            if len(b) >= 6:
                res.metadata = {"version": b[4], "encoding": ENCODINGS.get(b[5], "cp437")}
            return res
        ver, encf, count, ddate, dtime, off, branch = struct.unpack_from("<BBHHHHH", b, 4)
        enc = ENCODINGS.get(encf, "cp437")
        if encf not in ENCODINGS:
            res.warnings.append(f"unknown encoding flag {encf}; text decoded as cp437")
        res.metadata = {"version": ver, "encoding": enc, "created": dos_datetime(ddate, dtime),
                        "branch_id": branch, "declared_record_count": count, "data_offset": off}
        if off < 16 or off > len(b):
            damage(res, D.OOB_POINTER, 12, 14, f"data offset {off} is outside the file; assuming 16")
            off = 16
        elif off > 16:
            res.extra["header_extension"] = b[16:off].split(b"\0")[0].decode(enc, "replace")

        p, truncated, idx = off, False, 0
        non_ascii: dict[int, bool] = {}
        trailer_at = None
        while p < len(b):
            if b[p:p + 4] == TRAILER:
                trailer_at = p
                break
            if b[p] != MARKER:
                nxt = next((q for q in range(p + 1, len(b)) if _valid_record_at(b, q, enc)
                            or b[q:q + 4] == TRAILER), None)
                stop = nxt if nxt is not None else len(b)
                damage(res, D.UNPARSED_BYTES, p, stop, f"{stop - p} bytes at offset {p} are not a valid record")
                if nxt is None:
                    break
                p = nxt
                continue
            if p + 2 > len(b):
                truncated = True
                damage(res, D.TRUNCATED, p, len(b), f"file ends inside record {idx} header")
                break
            L = b[p + 1]
            end = p + 2 + L
            if end > len(b):
                truncated = True
                body = b[p + 2:]
                partial = {"id": struct.unpack_from("<I", body, 1)[0]} if len(body) >= 5 else {}
                damage(res, D.TRUNCATED, p, len(b),
                       f"file ends inside record {idx}: {len(b) - p} of {L + 2} bytes present",
                       affected=[f"record {idx}"])
                if partial:
                    vals = {k: partial.get(k) for k in ORDER}
                    res.records.append(record(idx, p, vals, verified=False, issues=["truncated"]))
                break
            body, chk = b[p + 2:end - 1], b[end - 1]
            v = _parse_body(body, enc)
            issues = []
            if v is None:
                issues.append("bad_length")
                damage(res, D.BAD_LENGTH, p, end, f"record {idx}: fields do not fit its length {L}",
                       affected=[f"record {idx}"])
            elif sum8(body) != chk:
                issues.append("checksum_mismatch")
                damage(res, D.CHECKSUM_MISMATCH, p, end,
                       f"record {idx} (id {v['id']}): checksum {chk:#04x} != computed {sum8(body):#04x}",
                       affected=[f"record {idx}"])
            if v is not None:
                if v["checked_out"] != bool(v["_due_raw"]):
                    res.warnings.append(f"record {idx} (id {v['id']}): checked_out flag and due date disagree")
                if v["_flags"] & ~0x07:
                    issues.append("invalid_value")
                    damage(res, D.INVALID_VALUE, p + 2, p + 3, f"record {idx}: unknown flag bits {v['_flags']:#04x}",
                           lossy=False)
                vals = {k: v[k] for k in ORDER}
                non_ascii[idx] = v["_non_ascii"]
                res.records.append(record(idx, p, vals, verified=not issues, issues=issues))
            p, idx = end, idx + 1

        if trailer_at is not None:
            if trailer_at + 6 > len(b):
                damage(res, D.TRUNCATED, trailer_at, len(b), "file ends inside the END! trailer", lossy=False)
            else:
                stored = struct.unpack_from("<H", b, trailer_at + 4)[0]
                if stored != sum16(b[:trailer_at]):
                    damage(res, D.CHECKSUM_MISMATCH, trailer_at, trailer_at + 6,
                           f"file checksum {stored:#06x} != computed {sum16(b[:trailer_at]):#06x}; "
                           "the header (not covered by record checksums) may be damaged", lossy=False)
                if trailer_at + 6 < len(b):
                    damage(res, D.UNPARSED_BYTES, trailer_at + 6, len(b),
                           f"{len(b) - trailer_at - 6} bytes after the trailer", lossy=False)
        elif not truncated:
            damage(res, D.TRUNCATED, len(b), len(b), "END! trailer missing", lossy=False)

        # The encoding flag lives in the header, which only the trailer sum protects. If that sum
        # fails or is missing, text with non-ASCII bytes may be decoded with the wrong code page.
        # A failed trailer sum is explained by a record that failed its own checksum; if no record
        # failed, the damage must be in the header (unprotected), so its encoding flag is suspect.
        trailer_bad = trailer_at is not None and trailer_at + 6 <= len(b) and \
            struct.unpack_from("<H", b, trailer_at + 4)[0] != sum16(b[:trailer_at])
        record_bad = any(i in ("checksum_mismatch", "bad_length") for r in res.records for i in r.issues)
        header_trusted = encf in ENCODINGS and not (trailer_bad and not record_bad)
        if not header_trusted:
            for r in res.records:
                if r.verified and non_ascii.get(r.index):
                    r.verified = False
                    r.issues.append("checksum_mismatch")
        complete = sum(1 for r in res.records if "truncated" not in r.issues)
        if not truncated and complete != count:
            damage(res, D.COUNT_MISMATCH, 6, 8, f"header declares {count} records, file holds {complete}",
                   lossy=complete < count)
        return res
