"""Unknown-file description. OWNER: Manas (delivery).

Used when no decoder recognises a file (or a decoder crashed). Never guesses
records; only describes the bytes so a human can investigate.
"""
from __future__ import annotations

from ..core.fingerprint import entropy, entropy_map, printable_strings
from ..core.model import FileResult


def describe(source_file: str, data: bytes, best_confidence: float = 0.0) -> FileResult:
    res = FileResult(source_file=source_file, format="unknown", confidence=best_confidence)
    overall_ent = round(entropy(data), 3)
    if not data:
        hint = "empty"
    elif overall_ent >= 7.2:
        hint = "compressed_or_encrypted"
    elif overall_ent < 1.0:
        hint = "sparse_or_padding"
    else:
        hint = "uncompressed_or_structured"

    res.extra = {
        "size": len(data),
        "first_bytes_hex": data[:64].hex(" "),
        "overall_entropy": overall_ent,
        "entropy_hint": hint,
        "is_compressed_or_encrypted": bool(overall_ent >= 7.2),
        "entropy_map": entropy_map(data),
        "strings": printable_strings(data),
    }
    res.metadata = {
        "size": len(data),
        "entropy": overall_ent,
        "entropy_hint": hint,
        "looks_like": looks_like(data),
        "first_bytes_hex": data[:32].hex(" "),
        "strings": [s["text"] for s in res.extra["strings"][:10]],
    }
    if not data:
        res.warnings.append("empty file")
    elif len(data) == 1:
        res.warnings.append("1-byte file")
    return res


SIGNATURES = [(b"\x89PNG\r\n\x1a\n", "png image"), (b"GIF8", "gif image"), (b"\xff\xd8\xff", "jpeg image"),
              (b"PK\x03\x04", "zip archive"), (b"%PDF", "pdf document"), (b"MZ", "dos/windows executable"),
              (b"\x7fELF", "elf executable")]


def looks_like(data: bytes) -> str:
    """A best-effort description of an unrecognised file. Never used to decode anything."""
    if not data:
        return "empty file"
    if len(data) < 4:
        return f"{len(data)}-byte file: too small to identify"
    for sig, what in SIGNATURES:
        if data.startswith(sig):
            return what + " (not a format this tool decodes)"
    if all(32 <= c < 127 or c in (9, 10, 13) for c in data):
        return "plain text"
    if entropy(data) >= 7.0 or (len(data) >= 64 and entropy(data) > 6.5):
        return "random or compressed data"
    return "unknown binary"
