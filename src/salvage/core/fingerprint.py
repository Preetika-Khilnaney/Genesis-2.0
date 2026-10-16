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
import re
from collections import Counter
from dataclasses import dataclass, field

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

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
    if len(chunk) == 1:
        return 0.0
    if _HAS_NUMPY:
        arr = np.frombuffer(chunk, dtype=np.uint8)
        counts = np.bincount(arr, minlength=256)
        nz = counts[counts > 0]
        n = len(chunk)
        probs = nz / n
        val = -float(np.sum(probs * np.log2(probs)))
        return 0.0 if abs(val) < 1e-9 else val
    n = len(chunk)
    return -sum(c / n * math.log2(c / n) for c in Counter(chunk).values())


def entropy_map(data: bytes, window: int = 256, max_blocks: int = 1024) -> list[dict]:
    """Return per-block Shannon entropy. Safe against huge files by capping blocks."""
    if not data:
        return []
    if len(data) <= window:
        return [{"offset": 0, "entropy": round(entropy(data), 2)}]

    total_blocks = (len(data) + window - 1) // window
    step = window
    if total_blocks > max_blocks:
        step = (len(data) // max_blocks // window) * window
        step = max(step, window)

    out = []
    for i in range(0, len(data), step):
        chunk = data[i:i + window]
        out.append({"offset": i, "entropy": round(entropy(chunk), 2)})
        if len(out) >= max_blocks:
            break
    return out


def printable_strings(data: bytes, min_len: int = 4, limit: int = 50) -> list[dict]:
    """Extract readable ASCII and UTF-16LE strings (min_len chars, capped at limit).

    Memory-safe for huge files by bounding scanning window to first 1 MB.
    """
    if not data or len(data) < min_len:
        return []

    # Safeguard against huge files
    scan_data = data[:1024 * 1024] if len(data) > 1024 * 1024 else data
    out: list[dict] = []

    # 1. ASCII strings
    ascii_pat = re.compile(rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}")
    for m in ascii_pat.finditer(scan_data):
        out.append({
            "offset": m.start(),
            "encoding": "ascii",
            "text": m.group().decode("ascii", errors="ignore"),
        })
        if len(out) >= limit // 2:
            break

    # 2. UTF-16LE strings (runs of [ASCII byte, 0x00])
    utf16_pat = re.compile(rb"(?:[\x20-\x7e]\x00){" + str(min_len).encode() + rb",}")
    for m in utf16_pat.finditer(scan_data):
        out.append({
            "offset": m.start(),
            "encoding": "utf-16le",
            "text": m.group().decode("utf-16le", errors="ignore"),
        })
        if len(out) >= limit:
            break

    out.sort(key=lambda x: x["offset"])
    return out[:limit]
