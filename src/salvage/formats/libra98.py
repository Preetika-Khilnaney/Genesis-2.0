"""LIBRA-98 (THE GATE). OWNERS: Preetika (decoder) + Bhupesh (field evidence).

Steps:
 1. Run `python3 tools/survey.py real-samples/libra98/` (samples/libra98/ until then) for magic, record count, header/record
    sizes and record columns, then confirm each in `python3 tools/hexview.py <file>`.
 2. Fill in LIBRA98_SPEC below (every field, with desc + evidence).
 3. Log every hypothesis in FIELD-LOG.md, including rejected ones.
 4. Fill CHECKS below (one per record field), then set ready = True.
 5. Run `make test`, `make run` and `make run-real`. Pattern to copy: PracticeRec in tools/rehearse.py.

STAND-IN LAYOUT: the spec below was worked out from samples/libra98/ (our demo data, invented
layout). Redo it from real-samples/libra98/ when the real samples arrive; CHECKS, the gate call
and the tests are the parts that carry over. Every field's evidence is in FIELD-LOG.md
(format "libra98 (stand-in)").
"""
from __future__ import annotations

from ..core.gate import gate_records
from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.simple import decode_simple
from ..core.spec import FieldSpec, FormatSpec

LIBRA98_SPEC = FormatSpec(
    name="libra98",
    magic=b"LIBRA-98",
    endian="little",
    description=("Header of 20 bytes, then record_count fixed-size records of 30 bytes. No checksum, so "
                 "values are verified by the layout fitting the file exactly, an exact round trip and "
                 "per-field checks (ids count up by 1, readable names, real dates, scores 0-100). "
                 "STAND-IN layout from our own samples; redo from the real samples."),
    header=[
        FieldSpec("magic", "bytes", 8, desc="file signature 'LIBRA-98'",
                  evidence="FIELD-LOG: same in all samples"),
        FieldSpec("version", "u8", desc="format version, 1 in every sample",
                  evidence="FIELD-LOG: constant 1; kept out of the magic so other versions still match"),
        FieldSpec("record_count", "u16", desc="number of records",
                  evidence="FIELD-LOG: 20 + count * 30 == file size in every undamaged sample"),
        FieldSpec("created", "unix32", desc="file creation time (UTC)",
                  evidence="FIELD-LOG: plausible 1998 timestamp in every sample"),
        FieldSpec("decoy_15", "u16", desc="unknown: equals record_count * 30 + 7, but is NOT the file size, "
                  "the bytes after it, or the record area length", evidence="FIELD-LOG: 3 length meanings rejected"),
        FieldSpec("reserved", "bytes", 3, desc="zero padding", evidence="FIELD-LOG: zero in every sample"),
    ],
    record=[
        FieldSpec("id", "u32", desc="record id, counts up by 1 from 1000",
                  evidence="FIELD-LOG: counts up by 1 in every undamaged sample"),
        FieldSpec("name", "str", 20, desc="name, NUL-padded",
                  evidence="FIELD-LOG: printable text + NUL padding in every undamaged sample"),
        FieldSpec("enrolled", "dos_date", desc="enrolment date (DOS date)",
                  evidence="FIELD-LOG: valid 1985-2010 DOS date in every undamaged sample"),
        FieldSpec("grade", "u8", desc="score 0-100", evidence="FIELD-LOG: 0-100 in every sample"),
        FieldSpec("flags", "u8", desc="flag bits, values 0-3 seen", evidence="FIELD-LOG: 0-3 in every sample"),
        FieldSpec("pad", "bytes", 2, desc="zero padding", evidence="FIELD-LOG: zero in every sample"),
    ],
    record_count_field="record_count",
    notes=["decoy_15 looks like a length field but every length meaning was rejected; it stays unverified."],
)


def _date_ok(v) -> bool:
    try:
        y, m, d = map(int, v.split("-"))
        return 1985 <= y <= 2010 and 1 <= m <= 12 and 1 <= d <= 31
    except Exception:
        return False


@register
class Libra98Decoder(Decoder):
    name = "libra98"
    spec = LIBRA98_SPEC
    ready = True

    # One check per record field: (value, previous record's values or None) -> bool.
    # They catch damage: LIBRA-98 has no checksum. Each one is backed by a FIELD-LOG row.
    CHECKS = {
        "id": lambda v, prev: prev is None or v == prev["id"] + 1,
        "name": lambda v, prev: v.isprintable() and v.strip() != "",
        "enrolled": lambda v, prev: _date_ok(v),
        "grade": lambda v, prev: 0 <= v <= 100,
        "flags": lambda v, prev: 0 <= v <= 3,
        "pad": lambda v, prev: v == "0000",
    }
    UNKNOWN_HEADER = ("decoy_15",)   # looks like a length, is not (FIELD-LOG)

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = decode_simple(self.spec, path, data)
        # gate_records decides VERIFIED vs UNVERIFIED: layout proven on all samples, file fits
        # (or record is before the damage), exact round trip, every check passes.
        gate_records(res, data, self.spec, ctx.samples(data) if ctx else [data],
                     self.CHECKS, unknown_header=self.UNKNOWN_HEADER)
        return res
