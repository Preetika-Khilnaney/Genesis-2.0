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
    # The organisers' damage vocabulary (OUTPUT-CONTRACT.md). New code uses only these.
    TRUNCATED = "truncated"
    CRC_MISMATCH = "crc_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    BAD_LENGTH = "bad_length"
    UNPARSED_BYTES = "unparsed_bytes"
    COUNT_MISMATCH = "count_mismatch"
    INVALID_VALUE = "invalid_value"
    OOB_POINTER = "oob_pointer"
    INDEX_MISSING = "index_missing"
    HEADER_CHECKSUM = "header_checksum"
    ENCRYPTED = "encrypted"
    UNKNOWN_RECORD = "unknown_record"
    # Older internal names, still produced by the generic helpers; output/contract.py maps them.
    CRC_FAIL = "crc_fail"              # -> crc_mismatch
    BAD_OFFSET = "bad_offset"          # -> oob_pointer
    BAD_KEY = "bad_key"                # -> encrypted
    INDEX_OVERLAP = "index_overlap"    # -> oob_pointer
    BAD_MAGIC = "bad_magic"            # -> invalid_value
    UNKNOWN = "unknown"                # -> unparsed_bytes


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
    # Contract output. `values` is the record exactly as OUTPUT-CONTRACT.md wants it; if None,
    # it is built from `fields`. `verified` False adds "verified": false; `issues` lists damage
    # kinds that touched this record. `corrected` notes a provable repair (e.g. single-bit fix).
    values: dict[str, Any] | None = None
    verified: bool = True
    issues: list[str] = field(default_factory=list)
    corrected: str | None = None

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
    lossy: bool = True         # False when the damage was found but nothing was lost (e.g. repaired)

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
    input_sha256: str | None = None  # SHA-256 of input file bytes
    extra: dict[str, Any] = field(default_factory=dict)  # format-specific (e.g. unknown-file entropy map)
    metadata: dict[str, Any] = field(default_factory=dict)  # contract "metadata" (header values)
    status: str | None = None        # contract status override: ok|partial|unsupported|unrecognized|failed

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
            "input_sha256": self.input_sha256,
            "header": {k: v.to_dict() for k, v in self.header.items()},
            "records": [r.to_dict() for r in self.records],
            "damage": [d.to_dict() for d in self.damage],
            "warnings": self.warnings,
            "error": self.error,
            "extra": self.extra,
        }
