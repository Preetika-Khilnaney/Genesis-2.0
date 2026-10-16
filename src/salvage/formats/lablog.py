"""LABLOG. OWNER: Khushi (recovery).

Needs: checksum checks per block and a damage report for bad blocks.

Plan:
 1. Find the block layout (marker, length, payload, checksum) from the samples.
 2. recovery.crc.guess_algorithm(...) on clean blocks -> pick the checksum.
 3. Describe it as a core.blocks.BlockLayout and call core.blocks.read_blocks(data, layout, start).
    It already does the CRC gate, provable single-bit CORRECTED fixes, LOST blocks with exact
    byte ranges, resync on the next valid marker, and truncation. You decode each b.payload.
 4. Override structure_score() with core.blocks.block_structure_score(data, layout, start)
    so LABLOG files with a damaged header are still recognised.
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
