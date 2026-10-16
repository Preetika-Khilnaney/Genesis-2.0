"""VAULT. OWNER: Khushi (recovery), field evidence with Bhupesh.

Needs: index table, run-length-compressed blobs, XOR-obfuscated strings.

Plan:
 1. Decode the index table (entry = offset, size, maybe name/type).
 2. Check entries: sort by offset; gaps = slack, overlaps -> DamageEntry(INDEX_OVERLAP),
    offset+size > file size -> DamageEntry(TRUNCATED / BAD_OFFSET).
 3. Blobs: recovery.rle.find_variant(...) - accept only a variant that round-trips exactly.
 4. Strings: recovery.xor.rank_single_byte_keys(...) - accept the key only if it clearly
    wins on all samples; otherwise leave strings UNVERIFIED.
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import Decoder, register
from ..core.spec import FormatSpec

VAULT_SPEC = FormatSpec(name="vault", magic=None, description="TODO")


@register
class VaultDecoder(Decoder):
    name = "vault"
    spec = VAULT_SPEC
    ready = False

    def decode(self, path: str, data: bytes) -> FileResult:
        raise NotImplementedError("TODO(Khushi): index table + RLE + XOR")
