"""LIBRA-98 (THE GATE). OWNERS: Preetika (decoder) + Bhupesh (field evidence).

Steps:
 1. Run `python3 tools/survey.py real-samples/libra98/` (samples/libra98/ until then) for magic, record count, header/record
    sizes and record columns, then confirm each in `python3 tools/hexview.py <file>`.
 2. Fill in LIBRA98_SPEC below (every field, with desc + evidence).
 3. Log every hypothesis in FIELD-LOG.md, including rejected ones.
 4. Fill CHECKS below (one per record field), then set ready = True.
 5. Run `make test`, `make run` and `make run-real`. Pattern to copy: PracticeRec in tools/rehearse.py.

The field list below is a PLACEHOLDER showing the syntax - replace it from the samples.
"""
from __future__ import annotations

from ..core.gate import gate_records
from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.simple import decode_simple
from ..core.spec import FieldSpec, FormatSpec

LIBRA98_SPEC = FormatSpec(
    name="libra98",
    magic=None,          # TODO: e.g. b"LIBRA98" once confirmed from the samples
    endian="little",     # TODO: confirm
    description="TODO: one-paragraph description of LIBRA-98 once decoded.",
    header=[
        # FieldSpec("magic", "bytes", 7, desc="file signature", evidence="FIELD-LOG #1"),
        # FieldSpec("record_count", "u16", desc="number of records", evidence="FIELD-LOG #2"),
    ],
    record=[
        # FieldSpec("id", "u32", desc="record id"),
        # FieldSpec("name", "str", 32, desc="NUL-padded name"),
        # FieldSpec("date", "dos_date", desc="enrolment date"),
    ],
    record_count_field=None,  # TODO: "record_count" if the header carries it
)


@register
class Libra98Decoder(Decoder):
    name = "libra98"
    spec = LIBRA98_SPEC
    ready = False  # TODO: True once the spec is filled and tests pass

    # One check per record field: (value, previous record's values or None) -> bool.
    # These are what catch damage, because LIBRA-98 may have no checksum. Write one for every
    # field you can justify from the samples, and log each in FIELD-LOG. Examples:
    #   "id":   lambda v, prev: prev is None or v == prev["id"] + 1,
    #   "name": lambda v, prev: v.isprintable() and v.strip() != "",
    #   "date": lambda v, prev: "1980" <= v[:4] <= "2030",
    CHECKS: dict = {}
    UNKNOWN_HEADER: tuple = ()   # header fields whose meaning is not proven (e.g. a decoy "length")

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = decode_simple(self.spec, path, data)
        # gate_records decides VERIFIED vs UNVERIFIED: layout proven on all samples, file fits
        # (or record is before the damage), exact round trip, every check passes.
        gate_records(res, data, self.spec, ctx.samples(data) if ctx else [data],
                     self.CHECKS, unknown_header=self.UNKNOWN_HEADER)
        return res
