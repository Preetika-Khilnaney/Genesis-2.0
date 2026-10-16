"""Damage ranges for index-table formats. OWNER: Khushi (recovery).

core.index.read_index reports an entry whose blob lies wholly outside the file as an empty
range at the end of the file (start == end). An empty range names no bytes. The bytes we
KNOW are bad are the entry's own: its pointer is what is wrong. anchor_empty_ranges() moves
such a range onto the entry's bytes in the table, keeping cause and detail.
"""
from __future__ import annotations

import re

from ..core.model import DamageEntry

_ENTRY = re.compile(r"entry (\d+)$")


def anchor_empty_ranges(damage: list[DamageEntry], table_start: int, entry_size: int) -> list[DamageEntry]:
    out = []
    for d in damage:
        idx = next((int(m.group(1)) for a in d.affected if (m := _ENTRY.match(a))), None)
        if d.start == d.end and idx is not None:
            s = table_start + idx * entry_size
            d = DamageEntry(s, s + entry_size, d.cause,
                            f"{d.detail} (range = the entry's own bytes in the table; its blob is outside the file)",
                            d.affected)
        out.append(d)
    return out
