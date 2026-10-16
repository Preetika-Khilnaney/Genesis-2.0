"""Small helpers shared by the format decoders. OWNER: Preetika (core)."""
from __future__ import annotations

import datetime as _dt
import hashlib

from ..core.model import DamageCause, DamageEntry, FileResult, Record

D = DamageCause


def damage(res: FileResult, kind: DamageCause, start: int, end: int, detail: str,
           lossy: bool = True, affected: list[str] | None = None) -> DamageEntry:
    d = DamageEntry(start, max(start, end), kind, detail, affected or [], lossy=lossy)
    res.damage.append(d)
    return d


def record(index: int, offset: int | None, values: dict, verified: bool = True,
           issues: list[str] | None = None) -> Record:
    return Record(index=index, offset=offset, values=values, verified=verified, issues=list(issues or []))


def dos_date(v: int) -> str | None:
    """DOS date word -> 'YYYY-MM-DD', or None for 0 / impossible dates."""
    if not v:
        return None
    y, m, d = 1980 + (v >> 9), (v >> 5) & 0xF, v & 0x1F
    try:
        return _dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def dos_datetime(date_word: int, time_word: int) -> str | None:
    d = dos_date(date_word)
    if d is None:
        return None
    h, mi, s = time_word >> 11, (time_word >> 5) & 0x3F, (time_word & 0x1F) * 2
    if h > 23 or mi > 59 or s > 59:
        return None
    return f"{d}T{h:02d}:{mi:02d}:{s:02d}"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sum8(b: bytes) -> int:
    return sum(b) & 0xFF


def sum16(b: bytes) -> int:
    return sum(b) & 0xFFFF


def col_name(col: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (spreadsheet column letters)."""
    s, col = "", col + 1
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s
