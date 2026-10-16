"""VAULT. OWNER: Khushi (recovery), field evidence with Bhupesh.

Needs: index table, run-length-compressed blobs, XOR-obfuscated strings.

Plan:
 1. `python3 tools/survey.py real-samples/vault/` (samples/vault/ until then) for the magic, entry count and constants.
 2. Describe one index entry as FieldSpecs and call core.index.read_index(data, start, count, entry).
    It already reports blobs past the end (TRUNCATED / BAD_OFFSET), offsets into the header,
    overlaps (INDEX_OVERLAP) and gaps. Use e.blob for each good entry.
    Override structure_score() with core.index.index_structure_score(...).
 3. Blobs: recovery.rle.find_variant(...) - accept only a variant that round-trips exactly.
 4. Strings: recovery.xor.rank_single_byte_keys(...) - accept the key only if it clearly
    wins on all samples; otherwise leave strings UNVERIFIED.
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FormatSpec

VAULT_SPEC = FormatSpec(name="vault", magic=None, description="TODO")


@register
class VaultDecoder(Decoder):
    name = "vault"
    spec = VAULT_SPEC
    ready = False

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        raise NotImplementedError("TODO(Khushi): index table + RLE + XOR")
