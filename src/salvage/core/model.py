"""Shared data model. OWNER: Preetika (core). SHARED INTERFACE - change only as a team.

Every decoder returns a FileResult. Every field carries one of the four statuses.
Never put a guessed value in a field: if it cannot be verified, mark it UNVERIFIED;
if it cannot be read at all, mark it LOST with value None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FieldStatus(str, Enum):
    VERIFIED = "verified"      # decoded and backed by evidence (checksum / round-trip / evidence check)
    CORRECTED = "corrected"    # repaired with a provable fix (e.g. single-bit CRC correction); say how in `note`
    UNVERIFIED = "unverified"  # decoded but not proven
    LOST = "lost"              # no value; never filled with a guess


class DamageCause(str, Enum):
    TRUNCATED = "truncated"
    CRC_FAIL = "crc_fail"
    BAD_OFFSET = "bad_offset"
    BAD_LENGTH = "bad_length"
    BAD_KEY = "bad_key"
    INDEX_OVERLAP = "index_overlap"
    UNKNOWN = "unknown"


@dataclass
class Field:
    name: str
    value: Any
    status: FieldStatus
    offset: int | None = None   # byte offset in the file
    length: int | None = None   # bytes consumed
    note: str | None = None     # why this status (e.g. "CRC ok", "single-bit fix at bit 13")

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "status": self.status.value,
            "offset": self.offset,
            "length": self.length,
            "note": self.note,
        }


@dataclass
class Record:
    index: int
    offset: int | None = None
    fields: dict[str, Field] = field(default_factory=dict)

    def add(self, f: Field) -> None:
        self.fields[f.name] = f

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "offset": self.offset,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }


@dataclass
class DamageEntry:
    start: int                 # first damaged byte (inclusive)
    end: int                   # last damaged byte (exclusive)
    cause: DamageCause
    detail: str = ""
    affected: list[str] = field(default_factory=list)  # record indexes / field names lost

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "cause": self.cause.value,
            "detail": self.detail,
            "affected": self.affected,
        }


@dataclass
class FileResult:
    source_file: str
    format: str                      # registry name, or "unknown"
    confidence: float = 0.0          # fingerprint confidence 0..1
    header: dict[str, Field] = field(default_factory=dict)
    records: list[Record] = field(default_factory=list)
    damage: list[DamageEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None         # set when decoding crashed; the run still exits 0
    extra: dict[str, Any] = field(default_factory=dict)  # format-specific (e.g. unknown-file entropy map)

    def status_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in FieldStatus}
        for f in self.header.values():
            counts[f.status.value] += 1
        for r in self.records:
            for f in r.fields.values():
                counts[f.status.value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "format": self.format,
            "confidence": round(self.confidence, 3),
            "header": {k: v.to_dict() for k, v in self.header.items()},
            "records": [r.to_dict() for r in self.records],
            "damage": [d.to_dict() for d in self.damage],
            "warnings": self.warnings,
            "error": self.error,
            "extra": self.extra,
        }
