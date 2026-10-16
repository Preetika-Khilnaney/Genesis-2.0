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
