"""Real-world format: Lotus 1-2-3 worksheet (.WKS). OWNER: Bhupesh. STRETCH.

A .WKS file is a stream of records: u16 type, u16 length, then `length` bytes (little-endian).
BOF (0) comes first and EOF (1) last. There is no checksum.

Rule: public documentation is a starting hypothesis, not the truth. Every claim below is backed
by a checker verdict in FIELD-LOG.md (format "wks"). Where the bytes disagree with the docs,
the bytes win and the disagreement is logged.

What may be VERIFIED: structure only (type, length, format byte, column, row, label prefix),
and only when the layout is accepted on all sibling samples (at least 3), this file fits it,
the record's checks pass, and the record re-encodes to the exact original bytes.
Cell values (integers, floats, label text) stay UNVERIFIED: with no checksum a flipped bit
inside a value would still round-trip, so we never claim it is right.
"""
from __future__ import annotations

import math
import struct

from ..core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from ..core.reader import ByteReader, OutOfBounds
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FormatSpec
from ..evidence.checker import evaluate

BOF, EOF, RANGE, INTEGER, NUMBER, LABEL = 0, 1, 6, 13, 14, 15
CELL_TYPES = (INTEGER, NUMBER, LABEL)
EXPECTED_LEN = {BOF: 2, EOF: 0, RANGE: 8, INTEGER: 7, NUMBER: 13}
STRUCTURAL = {"type", "length", "version", "format", "column", "row", "prefix"}
RANGE_FIELDS = ("first_col", "first_row", "last_col", "last_row")
U, V, L = FieldStatus.UNVERIFIED, FieldStatus.VERIFIED, FieldStatus.LOST

REALWORLD_SPEC = FormatSpec(
    name="realworld",
    magic=bytes.fromhex("000002000404"),  # BOF record: type 0, length 2, version 0x0404
    endian="little",
    description=("Lotus 1-2-3 worksheet (.WKS): a stream of records, each u16 type, u16 length, "
                 "then `length` bytes. BOF first, EOF last, no checksum."),
    notes=[
        "Record 0 = BOF (type 0, length 2, u16 version). Last record = EOF (type 1, length 0).",
        "RANGE (type 6, length 8): u16 first_col, first_row, last_col, last_row.",
        "Cells: u8 format (0xFF in every sample), u16 column, u16 row, then a value.",
        "INTEGER (13, length 7): i16 value. NUMBER (14, length 13): f64 value.",
        "LABEL (15): prefix byte 0x27, then NUL-terminated text.",
        "Evidence: FIELD-LOG.md, format 'wks'. Values stay unverified (no checksum).",
    ],
)


def _layout_ok(data: bytes) -> bool:
    """Records tile the file exactly, BOF (len 2) first, EOF (len 0) last."""
    n, pos, recs = len(data), 0, []
    while pos < n:
        if pos + 4 > n:
            return False
        t, ln = struct.unpack_from("<HH", data, pos)
        if pos + 4 + ln > n:
            return False
        recs.append((t, ln))
        pos += 4 + ln
    return bool(recs) and recs[0] == (BOF, 2) and recs[-1] == (EOF, 0)


def _parse(rtype: int, body: bytes, base: int):
    """Decode one record body. Returns (fields, unread_byte_count). May raise OutOfBounds."""
    b = ByteReader(body, "little")
    out: list[Field] = []

    def add(name: str, tname: str, length: int | None = None):
        s = b.pos
        v = b.read(tname, length)
        if isinstance(v, bytes):
            v = v.hex()
        out.append(Field(name, v, U, offset=base + s, length=b.pos - s))
        return v

    if rtype == BOF:
        add("version", "u16")
    elif rtype == RANGE:
        for n in RANGE_FIELDS:
            add(n, "u16")
    elif rtype in CELL_TYPES:
        add("format", "u8")
        add("column", "u16")
        add("row", "u16")
        if rtype == INTEGER:
            add("value", "i16")
        elif rtype == NUMBER:
            add("value", "f64")
            if not math.isfinite(out[-1].value):
                out[-1].value, out[-1].status = None, L
                out[-1].note = "bytes are not a finite number; value not recoverable"
        else:
            add("prefix", "u8")
            add("text", "cstr")
    elif rtype == EOF:
        pass
    else:
        add("raw", "bytes", len(body))
    return out, b.remaining()


def _encode(rtype: int, v: dict) -> bytes:
    if rtype == BOF:
        body = struct.pack("<H", v["version"])
    elif rtype == RANGE:
        body = struct.pack("<4H", *(v[n] for n in RANGE_FIELDS))
    elif rtype in CELL_TYPES:
        body = struct.pack("<BHH", v["format"], v["column"], v["row"])
        if rtype == INTEGER:
            body += struct.pack("<h", v["value"])
        elif rtype == NUMBER:
            body += struct.pack("<d", v["value"])
        else:
            body += bytes([v["prefix"]]) + v["text"].encode("latin-1") + b"\0"
    elif rtype == EOF:
        body = b""
    else:
        body = bytes.fromhex(v["raw"])
    return struct.pack("<HH", rtype, len(body)) + body


def _round_trips(rtype: int, vals: dict, raw: bytes) -> bool:
    try:
        return _encode(rtype, vals) == raw
    except Exception:
        return False


def _record_ok(rtype: int, length: int, vals: dict) -> bool:
    """Per-record checks, each backed by an accepted checker verdict on the samples."""
    if rtype not in EXPECTED_LEN and rtype != LABEL:
        return False  # unknown record type: never verified
    if rtype in EXPECTED_LEN and length != EXPECTED_LEN[rtype]:
        return False
    if rtype in CELL_TYPES and vals.get("format") != 0xFF:
        return False
    if rtype == LABEL:
        t = vals.get("text")
        if vals.get("prefix") != 0x27 or not isinstance(t, str) or t == "" or not t.isprintable():
            return False
    return True


@register
class RealWorldDecoder(Decoder):
    name = "realworld"
    spec = REALWORLD_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        return 1.0 if _layout_ok(data) else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        samples = ctx.samples(data) if ctx else [data]
        verdict = evaluate("realworld", "records tile the file, BOF first, EOF last",
                           samples, _layout_ok, "Bhupesh", log=False)
        fits = _layout_ok(data)
        verifiable = verdict.accepted and fits
        if not verdict.accepted:
            res.warnings.append(f"layout not proven ({verdict.held}/{verdict.total} samples fit, "
                                "need all and at least 3); every field stays unverified")
        elif not fits:
            res.warnings.append("this file does not fit the proven layout; its fields stay unverified")

        r = ByteReader(data, "little")
        index, cells, range_info = 0, [], None
        while r.remaining() > 0:
            start = r.pos
            try:
                rtype = r.read("u16")
                length = r.read("u16")
                body = r.take(length)
            except OutOfBounds:
                res.damage.append(DamageEntry(start, len(data), DamageCause.TRUNCATED,
                                              f"file ends inside record {index}", [f"record {index}"]))
                break
            rec = Record(index=index, offset=start)
            rec.add(Field("type", rtype, U, offset=start, length=2))
            rec.add(Field("length", length, U, offset=start + 2, length=2))
            parsed = True
            try:
                fields, unread = _parse(rtype, body, start + 4)
                if unread:
                    raise ValueError(f"{unread} unread bytes")
                for f in fields:
                    rec.add(f)
            except (OutOfBounds, ValueError) as e:
                parsed = False
                res.damage.append(DamageEntry(start, start + 4 + length, DamageCause.BAD_LENGTH,
                                              f"record {index} (type {rtype}) body does not match its type: {e}",
                                              [f"record {index}"]))
                rec.add(Field("raw", body.hex(), U, offset=start + 4, length=length,
                              note="body could not be parsed"))
            vals = {k: f.value for k, f in rec.fields.items()}
            rec_ok = (parsed and verifiable and _record_ok(rtype, length, vals)
                      and _round_trips(rtype, vals, data[start:r.pos]))
            for f in rec.fields.values():
                if f.status is L:
                    continue
                if rec_ok and f.name in STRUCTURAL:
                    f.status, f.note = V, "layout proven on all samples; checks pass; round-trip ok"
                elif f.name in ("value", "text"):
                    f.note = "no checksum in this format; value cannot be independently verified"
                else:
                    f.note = "not verified: layout, checks or round-trip not established"
            if rtype not in EXPECTED_LEN and rtype != LABEL and parsed:
                res.warnings.append(f"record {index}: unknown type {rtype}, kept as raw bytes")
            if parsed and rtype in CELL_TYPES:
                cells.append((vals["column"], vals["row"]))
            if parsed and rtype == RANGE:
                range_info = (rec, vals, rec_ok)
            res.records.append(rec)
            index += 1

        if range_info and cells:
            rec, v, rec_ok = range_info
            agree = (v["last_col"], v["last_row"]) == (max(c for c, _ in cells), max(w for _, w in cells))
            if not agree:
                res.warnings.append("RANGE last column/row disagree with the cells actually present")
            for n in ("last_col", "last_row"):
                f = rec.fields[n]
                if rec_ok and agree:
                    f.status, f.note = V, "equals the highest cell column/row; layout proven"
                else:
                    f.note = "not verified: disagrees with the cells or the record is unverified"
        return res
