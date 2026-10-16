"""Candidate field interpretations. OWNER: Bhupesh (evidence).

Each test takes one sample's bytes and a field location, and says whether a given
meaning is consistent with that sample. The checker runs a test over ALL samples.
This is how we tell a real length field from one that only looks like a length.

TODO(Bhupesh): add tests as the samples demand (offset-to-next-record, enum sets, ...).
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone

_CODES = {1: "B", 2: "H", 4: "I"}


def read_uint(data: bytes, offset: int, size: int, endian: str = "<") -> int | None:
    if offset + size > len(data):
        return None
    return struct.unpack(endian + _CODES[size], data[offset:offset + size])[0]


def is_constant(samples: list[bytes], offset: int, size: int) -> bool:
    vals = {s[offset:offset + size] for s in samples if len(s) >= offset + size}
    return len(vals) == 1


def is_length_of_rest(data: bytes, offset: int, size: int, endian: str = "<", adjust: int = 0) -> bool:
    """Value == number of bytes after the field (+ adjust)."""
    v = read_uint(data, offset, size, endian)
    return v is not None and v == len(data) - (offset + size) + adjust


def is_file_size(data: bytes, offset: int, size: int, endian: str = "<") -> bool:
    v = read_uint(data, offset, size, endian)
    return v is not None and v == len(data)


def is_record_count(data: bytes, offset: int, size: int, header_len: int, record_len: int, endian: str = "<") -> bool:
    """Value * record_len fills the body exactly."""
    v = read_uint(data, offset, size, endian)
    return v is not None and header_len + v * record_len == len(data)


def is_plausible_unix32(data: bytes, offset: int, endian: str = "<", lo: int = 1970, hi: int = 2038) -> bool:
    v = read_uint(data, offset, 4, endian)
    if v is None:
        return False
    return lo <= datetime.fromtimestamp(v, tz=timezone.utc).year <= hi


def is_plausible_dos_date(data: bytes, offset: int, endian: str = "<") -> bool:
    v = read_uint(data, offset, 2, endian)
    if v is None:
        return False
    y, m, d = 1980 + (v >> 9), (v >> 5) & 0xF, v & 0x1F
    return 1 <= m <= 12 and 1 <= d <= 31 and y <= 2107
