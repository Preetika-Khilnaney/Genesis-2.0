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
    if not data:
        res.warnings.append("empty file")
    elif len(data) == 1:
        res.warnings.append("1-byte file")
    return res
