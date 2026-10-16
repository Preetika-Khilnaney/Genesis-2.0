"""Real-world legacy format (at least one of .BRAVO, .WPD, .CVT, .000, .WKS). OWNER: Bhupesh. STRETCH.

Rule: public documentation is a starting hypothesis, not the truth. Where the
sample bytes disagree with the docs, the bytes win and the disagreement is logged.
.WKS (Lotus 1-2-3) and .WPD (WordPerfect, magic FF 57 50 43) are the best documented.
TODO: rename module/decoder to the chosen format.
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FormatSpec

REALWORLD_SPEC = FormatSpec(name="realworld", magic=None, description="TODO")


@register
class RealWorldDecoder(Decoder):
    name = "realworld"
    spec = REALWORLD_SPEC
    ready = False

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        raise NotImplementedError("TODO(Bhupesh): chosen real-world format")
