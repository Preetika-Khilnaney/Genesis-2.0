"""Unknown-file description. OWNER: Manas (delivery).

Used when no decoder recognises a file (or a decoder crashed). Never guesses
records; only describes the bytes so a human can investigate.
"""
from __future__ import annotations

from ..core.fingerprint import entropy, entropy_map, printable_strings
from ..core.model import FileResult


def describe(source_file: str, data: bytes, best_confidence: float = 0.0) -> FileResult:
    res = FileResult(source_file=source_file, format="unknown", confidence=best_confidence)
    res.extra = {
        "size": len(data),
        "first_bytes_hex": data[:32].hex(" "),
        "overall_entropy": round(entropy(data), 3),
        "entropy_map": entropy_map(data),
        "strings": printable_strings(data),
    }
    if not data:
        res.warnings.append("empty file")
    return res
