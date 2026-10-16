"""Game archive (at least one). OWNER: Khushi (recovery).

Same building blocks as VAULT: index table checks, compression, obfuscation.
TODO: rename this module/decoder to the actual archive format once picked.
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import Decoder, register
from ..core.spec import FormatSpec

GAME_ARCHIVE_SPEC = FormatSpec(name="game_archive", magic=None, description="TODO")


@register
class GameArchiveDecoder(Decoder):
    name = "game_archive"
    spec = GAME_ARCHIVE_SPEC
    ready = False

    def decode(self, path: str, data: bytes) -> FileResult:
        raise NotImplementedError("TODO(Khushi): index + entries")
