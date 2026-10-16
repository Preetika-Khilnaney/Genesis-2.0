"""LABLOG. OWNER: Khushi (recovery).

Needs: checksum checks per block and a damage report for bad blocks.

Plan:
 1. Find the block layout (marker, length, payload, checksum) from the samples.
 2. recovery.crc.guess_algorithm(...) on clean blocks -> pick the checksum.
 3. For each block: CRC ok -> fields VERIFIED; single_bit_fix -> CORRECTED (note the bit);
    else -> DamageEntry(CRC_FAIL) + recovery.resync to the next valid marker.
 4. Truncated last block -> DamageEntry(TRUNCATED).
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FormatSpec

LABLOG_SPEC = FormatSpec(
    name="lablog",
    magic=None,  # TODO
    description="TODO",
    checksum="TODO: algorithm, coverage, where it is stored",
    header=[],
    record=[],
)


@register
class LablogDecoder(Decoder):
    name = "lablog"
    spec = LABLOG_SPEC
    ready = False

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        raise NotImplementedError("TODO(Khushi): block loop with CRC gate + resync")
