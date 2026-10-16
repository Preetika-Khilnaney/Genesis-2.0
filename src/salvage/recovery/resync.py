"""Resynchronisation after damage. OWNER: Khushi (recovery).

After a block fails its checksum or runs out of bounds, skip forward to the next
place where a valid block can start, and record everything skipped as damage.
"""
from __future__ import annotations

from typing import Callable

from ..core.model import DamageCause, DamageEntry


def next_marker(data: bytes, marker: bytes, start: int) -> int | None:
    i = data.find(marker, start)
    return None if i < 0 else i


def resync(data: bytes, start: int, marker: bytes,
           is_valid_block: Callable[[bytes, int], bool] | None = None) -> int | None:
    """Offset of the next marker at or after `start` that also passes `is_valid_block`
    (e.g. its checksum verifies). None if there is no further valid block."""
    pos = start
    while True:
        i = next_marker(data, marker, pos)
        if i is None:
            return None
        if is_valid_block is None or is_valid_block(data, i):
            return i
        pos = i + 1


def skipped(start: int, end: int, cause: DamageCause, detail: str = "", affected: list[str] | None = None) -> DamageEntry:
    return DamageEntry(start=start, end=end, cause=cause, detail=detail, affected=affected or [])
