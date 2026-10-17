"""Checksum gate. OWNER: Khushi (recovery).

Rule: data from a checksummed block is VERIFIED only if its checksum passes.
A single flipped bit may be CORRECTED only when exactly one bit flip makes the
checksum pass (the fix is then provable); otherwise the block is LOST.

TODO(Khushi): confirm LABLOG's checksum algorithm from the samples (use
`tools/hexview.py`, and CRC RevEng if it is not a standard one) and add it to ALGORITHMS.
"""
from __future__ import annotations

import zlib
from typing import Callable


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def sum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def xor8(data: bytes) -> int:
    v = 0
    for b in data:
        v ^= b
    return v


ALGORITHMS: dict[str, Callable[[bytes], int]] = {
    "crc32": crc32,
    "crc16_ccitt": crc16_ccitt,
    "sum8": sum8,
    "sum16": sum16,
    "xor8": xor8,
}


def check(algorithm: str, payload: bytes, stored: int) -> bool:
    return ALGORITHMS[algorithm](payload) == stored


def guess_algorithm(blocks: list[tuple[bytes, int]]) -> list[str]:
    """Which known algorithms match ALL (payload, stored_checksum) pairs from clean samples.
    Log the result in FIELD-LOG.md, including algorithms that failed."""
    return [name for name, fn in ALGORITHMS.items() if all(fn(p) == s for p, s in blocks)]


def single_bit_fix(algorithm: str, payload: bytes, stored: int, max_len: int = 4096,
                   stored_bits: int = 0) -> tuple[bytes, int] | None:
    """Return (fixed_payload, bit_index) if exactly ONE single-bit flip makes the checksum pass.
    Only valid for CRCs whose Hamming distance covers the block length; sums/xor are not safe.
    Returns None when no fix, or more than one fix, exists.

    With stored_bits > 0 (the stored checksum's width in bits) the stored checksum's own bits
    are candidates too: the seal itself can be the damaged part. Such a fix comes back as
    (payload unchanged, len(payload) * 8 + k), k = the bit of the stored value that was wrong.
    It counts toward "exactly one", so a payload fix and a checksum fix together are ambiguous."""
    if algorithm not in ("crc32", "crc16_ccitt") or len(payload) > max_len:
        return None
    fn = ALGORITHMS[algorithm]
    found = None
    buf = bytearray(payload)
    for bit in range(len(buf) * 8):
        buf[bit // 8] ^= 1 << (bit % 8)
        if fn(bytes(buf)) == stored:
            if found is not None:
                return None  # ambiguous: not provable
            found = (bytes(buf), bit)
        buf[bit // 8] ^= 1 << (bit % 8)
    if stored_bits:
        diff = fn(bytes(payload)) ^ stored
        if diff and diff & (diff - 1) == 0 and diff < (1 << stored_bits):   # exactly one bit differs
            if found is not None:
                return None
            found = (bytes(payload), len(payload) * 8 + diff.bit_length() - 1)
    return found
