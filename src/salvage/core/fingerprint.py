"""File identification. OWNER: Preetika (core).

Asks every ready decoder how confident it is (magic bytes, structure checks) and
picks the best one above MIN_CONFIDENCE. Also provides entropy helpers used by the
unknown-file report and by discovery.
"""
from __future__ import annotations

import math
from collections import Counter

from .registry import Decoder, all_decoders

MIN_CONFIDENCE = 0.5


def identify(data: bytes) -> tuple[Decoder | None, float]:
    best, best_conf = None, 0.0
    for dec in all_decoders():
        if not dec.ready:
            continue
        try:
            conf = float(dec.sniff(data))
        except Exception:
            conf = 0.0
        if conf > best_conf:
            best, best_conf = dec, conf
    if best_conf < MIN_CONFIDENCE:
        return None, best_conf
    return best, best_conf


def entropy(chunk: bytes) -> float:
    """Shannon entropy in bits per byte (0 = constant, 8 = random/compressed/encrypted)."""
    if not chunk:
        return 0.0
    n = len(chunk)
    return -sum(c / n * math.log2(c / n) for c in Counter(chunk).values())


def entropy_map(data: bytes, window: int = 256) -> list[dict]:
    return [{"offset": i, "entropy": round(entropy(data[i:i + window]), 2)}
            for i in range(0, len(data), window)]


def printable_strings(data: bytes, min_len: int = 4, limit: int = 50) -> list[dict]:
    out, start = [], None
    for i, b in enumerate(data + b"\x00"):
        if 32 <= b < 127:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= min_len:
                out.append({"offset": start, "text": data[start:i].decode("ascii")})
                if len(out) >= limit:
                    break
            start = None
    return out
