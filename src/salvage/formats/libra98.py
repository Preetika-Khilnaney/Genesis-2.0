"""LIBRA-98 (THE GATE). OWNERS: Preetika (decoder) + Bhupesh (field evidence).

Steps:
 1. Open the samples with `python tools/hexview.py samples/libra98/*` and compare them.
 2. Fill in LIBRA98_SPEC below (every field, with desc + evidence).
 3. Log every hypothesis in FIELD-LOG.md, including rejected ones.
 4. Set ready = True, run `make test` and `./salvage samples out`.

The field list below is a PLACEHOLDER showing the syntax - replace it from the samples.
"""
from __future__ import annotations

from ..core.model import FieldStatus, FileResult
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

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = decode_simple(self.spec, path, data)
        # ctx.samples(data) = this file + every other LIBRA-98 file in the run. Use it for
        # cross-sample evidence, e.g.:
        #   samples = ctx.samples(data) if ctx else [data]
        #   v = checker.evaluate("libra98", "u16@7 is record count", samples, test)
        # Upgrade fields to VERIFIED only with evidence (round-trip + evidence check).
        for rec in res.records:
            for f in rec.fields.values():
                if f.note == "round-trip ok":
                    f.status = FieldStatus.VERIFIED  # TODO: also require checker verdicts
        return res
