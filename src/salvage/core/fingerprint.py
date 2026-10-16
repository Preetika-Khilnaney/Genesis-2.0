"""File identification. OWNER: Preetika (core).

Three steps, strongest evidence first:
 1. sniff()            exact magic / format checks        -> method "magic"
 2. near_magic()       magic with 1-2 damaged bytes       -> method "near_magic" (+ damage entry)
 3. structure_score()  header damaged, but the structure  -> method "structure" (+ warning)
                       explains the whole file exactly
A fallback only applies when exactly ONE decoder matches; ties stay unknown.
Also provides entropy helpers used by the unknown-file report and by discovery.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .registry import Decoder, all_decoders

MIN_CONFIDENCE = 0.5
NEAR_MAGIC_CONFIDENCE = 0.8
STRUCTURE_CONFIDENCE = 0.6


@dataclass
class Identification:
    decoder: Decoder | None
    confidence: float
    method: str = "none"                                 # magic | near_magic | structure | none
    damaged_magic: list[int] = field(default_factory=list)  # byte offsets, for near_magic


def _ready() -> list[Decoder]:
    return [d for d in all_decoders() if d.ready]


def identify_detailed(data: bytes) -> Identification:
    # 1. Exact sniff
    best, best_conf = None, 0.0
    for dec in _ready():
        try:
            conf = float(dec.sniff(data))
        except Exception:
            conf = 0.0
        if conf > best_conf:
            best, best_conf = dec, conf
    if best_conf >= MIN_CONFIDENCE:
        return Identification(best, best_conf, "magic")

    # 2. Magic with a few damaged bytes
    near = []
    for dec in _ready():
        try:
            diffs = dec.near_magic(data)
        except Exception:
            diffs = None
        if diffs:
            near.append((dec, diffs))
    if len(near) == 1:
        dec, diffs = near[0]
        return Identification(dec, NEAR_MAGIC_CONFIDENCE, "near_magic", diffs)

    # 3. Structure explains the whole file
    fits = []
    for dec in _ready():
        try:
            score = float(dec.structure_score(data))
        except Exception:
            score = 0.0
        if score >= 1.0:
            fits.append(dec)
    if len(fits) == 1:
        return Identification(fits[0], STRUCTURE_CONFIDENCE, "structure")

    return Identification(None, best_conf, "none")


def identify(data: bytes) -> tuple[Decoder | None, float]:
    """Backwards-compatible wrapper: (decoder or None, confidence)."""
    ident = identify_detailed(data)
    return ident.decoder, ident.confidence


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
