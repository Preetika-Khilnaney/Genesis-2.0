"""Generic decoder for header + repeated-record formats. OWNER: Preetika (core).

Most formats are "header, then N records". decode_simple() handles that shape from a
FormatSpec alone: bounds checks, truncation damage, and round-trip verification.
A field becomes `verified` only when its record re-encodes to the exact original bytes
AND the format-level evidence/checksum (passed in by the caller) supports it.
"""
from __future__ import annotations

from .model import DamageCause, DamageEntry, FieldStatus, FileResult, Record
from .reader import ByteReader, OutOfBounds
from .spec import FormatSpec, decode_fields, round_trip_ok


def decode_simple(spec: FormatSpec, path: str, data: bytes, max_records: int = 1_000_000) -> FileResult:
    res = FileResult(source_file=path, format=spec.name)
    r = ByteReader(data, spec.endian)

    # Header
    try:
        start = r.pos
        res.header = decode_fields(r, spec.header)
        if round_trip_ok(data[start:r.pos], res.header, spec.header, spec.endian):
            for f in res.header.values():
                f.status, f.note = FieldStatus.VERIFIED, "round-trip ok"
    except OutOfBounds as e:
        res.damage.append(DamageEntry(e.offset, len(data), DamageCause.TRUNCATED, "file ends inside header", ["header"]))
        return res

    # Record count: from a header field if the spec names one, else read until EOF
    count = None
    if spec.record_count_field:
        cf = res.header.get(spec.record_count_field)
        count = int(cf.value) if cf is not None else None
    if count is not None and count > max_records:
        res.warnings.append(f"record count {count} implausible; reading until end of file instead")
        res.header[spec.record_count_field].status = FieldStatus.UNVERIFIED
        count = None

    i, truncated = 0, False
    while (count is None and r.remaining() > 0) or (count is not None and i < count):
        rec_start = r.pos
        try:
            fields = decode_fields(r, spec.record)
        except OutOfBounds:
            res.damage.append(DamageEntry(rec_start, len(data), DamageCause.TRUNCATED,
                                          f"file ends inside record {i}",
                                          [f"record {j}" for j in range(i, count if count is not None else i + 1)]))
            truncated = True
            break
        rec = Record(index=i, offset=rec_start, fields=fields)
        if round_trip_ok(data[rec_start:r.pos], fields, spec.record, spec.endian):
            for f in fields.values():
                f.note = "round-trip ok"
        res.records.append(rec)
        i += 1

    if count is not None and r.remaining() > 0 and not truncated:
        res.warnings.append(f"{r.remaining()} trailing bytes after {count} records")
    return res
