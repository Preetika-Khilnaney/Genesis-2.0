"""Format registry. OWNER: Preetika (core). SHARED INTERFACE.

Every format module defines one Decoder subclass and decorates it with @register.
The CLI never imports formats directly; it asks the registry.

    @register
    class LablogDecoder(Decoder):
        name = "lablog"
        spec = LABLOG_SPEC              # optional, used for FORMAT-SPEC.md
        def sniff(self, data: bytes) -> float: ...   # 0.0 = not mine, 1.0 = certain
        def decode(self, path: str, data: bytes) -> FileResult: ...
"""
from __future__ import annotations

from .model import FileResult
from .spec import FormatSpec

_REGISTRY: dict[str, "Decoder"] = {}


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

    def decode(self, path: str, data: bytes) -> FileResult:
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
