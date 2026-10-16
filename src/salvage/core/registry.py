"""Format registry. OWNER: Preetika (core). SHARED INTERFACE.

Every format module defines one Decoder subclass and decorates it with @register.
The CLI never imports formats directly; it asks the registry.

    @register
    class LablogDecoder(Decoder):
        name = "lablog"
        spec = LABLOG_SPEC              # optional, used for FORMAT-SPEC.md
        def sniff(self, data: bytes) -> float: ...   # 0.0 = not mine, 1.0 = certain
        def decode(self, path: str, data: bytes, ctx: DecodeContext) -> FileResult: ...

The CLI runs in two passes: it fingerprints every file first, groups them by format,
then decodes each file with a DecodeContext holding the OTHER files of the same
format. That is what lets a decoder run the evidence check across all samples:

    def decode(self, path, data, ctx):
        samples = ctx.samples(data)      # this file + its siblings, as bytes
        v = checker.evaluate("lablog", "u16@4 is block length", samples, test)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import FileResult
from .spec import FormatSpec

_REGISTRY: dict[str, "Decoder"] = {}


@dataclass
class DecodeContext:
    """What a decoder knows beyond the file it is decoding."""
    format: str
    siblings: list[tuple[str, bytes]] = field(default_factory=list)  # (path, data) of OTHER files of this format

    def samples(self, data: bytes) -> list[bytes]:
        """This file plus every sibling: the set the evidence check runs over."""
        return [data] + [d for _, d in self.siblings]

    @property
    def sample_count(self) -> int:
        return 1 + len(self.siblings)


class Decoder:
    name: str = "base"
    spec: FormatSpec | None = None
    ready: bool = False   # set True once the decoder is implemented; unready decoders are never chosen

    def sniff(self, data: bytes) -> float:
        """Default sniff: magic bytes from the spec."""
        if self.spec and self.spec.magic:
            o = self.spec.magic_offset
            return 1.0 if data[o:o + len(self.spec.magic)] == self.spec.magic else 0.0
        return 0.0

    # --- Fallbacks for files whose header is damaged (used only when sniff() fails) ---

    def near_magic(self, data: bytes, max_diff: int = 2) -> list[int] | None:
        """Offsets of damaged magic bytes, if the magic is present with at most `max_diff`
        bytes wrong (e.g. a bit flip). None if the magic is absent or too short to judge.
        Magic shorter than 4 bytes is never matched approximately (too many false hits)."""
        if not (self.spec and self.spec.magic) or len(self.spec.magic) < 4:
            return None
        o, magic = self.spec.magic_offset, self.spec.magic
        got = data[o:o + len(magic)]
        if len(got) < len(magic):
            return None
        diffs = [o + i for i, (a, b) in enumerate(zip(got, magic)) if a != b]
        allowed = min(max_diff, len(magic) // 4)
        return diffs if 0 < len(diffs) <= allowed else None

    def structure_score(self, data: bytes) -> float:
        """0..1: how cleanly the spec's structure explains the whole file, ignoring the magic.
        Default needs a header record-count field so the count can be cross-checked against
        the file size; without one, any file of the right length would match. Formats with
        other structure (blocks, index tables) can override this."""
        spec = self.spec
        if not (spec and spec.record and spec.record_count_field):
            return 0.0
        from .simple import decode_simple  # local import: simple does not depend on registry
        try:
            res = decode_simple(spec, "", data)
        except Exception:
            return 0.0
        if res.damage or res.warnings or not res.records:
            return 0.0
        return 1.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        raise NotImplementedError(f"{self.name} decoder not implemented yet")


def register(cls: type[Decoder]) -> type[Decoder]:
    inst = cls()
    if inst.name in _REGISTRY:
        raise ValueError(f"duplicate decoder name {inst.name!r}")
    _REGISTRY[inst.name] = inst
    return cls


def all_decoders() -> list[Decoder]:
    return list(_REGISTRY.values())


def get(name: str) -> Decoder:
    return _REGISTRY[name]
