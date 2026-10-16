"""Evidence gate for header + fixed-size record formats. OWNER: Preetika (core).

decode_simple() reads the fields; gate_records() decides which ones we may call VERIFIED.
This is the pattern the rehearsal proved safe (0 false recoveries on ~1,900 damaged files):

    res = decode_simple(SPEC, path, data)
    gate_records(res, data, SPEC, ctx.samples(data) if ctx else [data], checks={
        "id":    lambda v, prev: prev is None or v == prev["id"] + 1,   # counts up by 1
        "name":  lambda v, prev: v.isprintable() and v.strip() != "",
        "grade": lambda v, prev: 0 <= v <= 100,
    })

A record field becomes VERIFIED only when ALL of these hold:
  1. layout proven: header + count * record_size == file size on EVERY sample (>= 2);
  2. this file fits that layout exactly, OR the record lies before the first damaged
     record minus one (damage only shifts what comes after it, and the last record that
     still looks fine may hold the damage itself);
  3. the record round-trips byte for byte;
  4. every check of the record passes (one bad field makes the whole record suspect).
Everything else is UNVERIFIED, with a note saying which condition failed. Values are never
changed or invented. Header fields keep decode_simple's status unless the layout is unproven
(then the count is UNVERIFIED) or they are listed in `unknown_header` (meaning not known).

A check is (value, previous_record_values_or_None) -> bool. Fields without a check pass,
so add checks for every field you can: they are what catches damage in formats with no
checksum. If the format has a checksum, verify with it as well; this gate does not replace it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .model import DamageCause, DamageEntry, FieldStatus, FileResult
from .reader import type_size
from .spec import FieldSpec, FormatSpec
from ..evidence.checker import evaluate

Check = Callable[[Any, "dict | None"], bool]


@dataclass
class GateSummary:
    layout_proven: bool
    file_fits: bool
    first_bad_record: int | None
    verified_records: int
    notes: list[str] = field(default_factory=list)


def _size(f: FieldSpec) -> int | None:
    return type_size(f.type) or (f.length if f.type in ("bytes", "str") else None)


def header_layout(spec: FormatSpec) -> tuple[int, int, str] | None:
    """(header_size, count_offset, count_type) from the spec, or None if not fixed-size."""
    off, count_at, count_type = 0, None, None
    for f in spec.header:
        if f.name == spec.record_count_field:
            count_at, count_type = off, f.type
        s = _size(f)
        if s is None:
            return None
        off += s
    if count_at is None:
        return None
    return off, count_at, count_type


def layout_fits(spec: FormatSpec, data: bytes) -> bool:
    hl, rec = header_layout(spec), spec.record_size()
    if hl is None or not rec:
        return False
    hdr, at, t = hl
    size = type_size(t)
    if size is None or len(data) < at + size:
        return False
    big = t.endswith("be") or (spec.endian == "big" and not t.endswith("le"))
    count = int.from_bytes(data[at:at + size], "big" if big else "little")
    return hdr + count * rec == len(data)


def gate_records(res: FileResult, data: bytes, spec: FormatSpec, samples: list[bytes],
                 checks: dict[str, Check] | None = None, unknown_header: tuple[str, ...] = (),
                 author: str = "", log: bool = False) -> GateSummary:
    checks = checks or {}
    rec_size = spec.record_size()
    verdict = evaluate(spec.name, f"header + {spec.record_count_field} * {rec_size} == file size",
                       samples, lambda b: layout_fits(spec, b), author=author, log=log)
    proven = verdict.held >= 2           # held on >= 2 samples; damaged siblings may disagree
    fits = layout_fits(spec, data)
    notes: list[str] = []
    if not fits:
        notes.append(f"file size does not match header + count * {rec_size}: bytes cut, inserted or deleted")
        res.warnings.append(notes[-1])
        if not any(d.cause == DamageCause.TRUNCATED for d in res.damage):
            hl = header_layout(spec)
            start = hl[0] if hl else 0
            res.damage.append(DamageEntry(start, len(data), DamageCause.BAD_LENGTH,
                                          "file size disagrees with the record count; record boundaries "
                                          "after the first damaged record cannot be trusted", ["records"]))
    if not proven:
        notes.append(f"layout held on only {verdict.held}/{verdict.total} samples")

    for name in unknown_header:
        if name in res.header:
            res.header[name].status = FieldStatus.UNVERIFIED
            res.header[name].note = "meaning not known"
    cf = res.header.get(spec.record_count_field or "")
    if cf is not None and not (proven and fits):
        cf.status, cf.note = FieldStatus.UNVERIFIED, "record count not confirmed by the file size"

    # pass 1: which records look intact?
    intact, prev = [], None
    for rec in res.records:
        raw = data[rec.offset:rec.offset + rec_size] if rec.offset is not None and rec_size else b""
        rt = len(raw) == rec_size and bool(rec.fields) and all(f.note == "round-trip ok" for f in rec.fields.values())
        values = {k: f.value for k, f in rec.fields.items()}
        ok = rt and all(_safe(checks[k], values[k], prev) for k in checks if k in values)
        intact.append((rt, ok))
        prev = values
    first_bad = next((i for i, (_, ok) in enumerate(intact) if not ok), None)
    # when the file size is off, the last good-looking record before the damage may hold it
    limit = len(intact) if fits else max(0, (first_bad if first_bad is not None else len(intact)) - 1)

    verified = 0
    for i, rec in enumerate(res.records):
        rt, ok = intact[i]
        trusted = proven and rt and ok and (fits or i < limit)
        why = [w for w, bad in (("layout not proven", not proven), ("round-trip failed", not rt),
                                ("a check failed in this record", not ok),
                                ("after the first damaged record", not fits and i >= limit)) if bad]
        for f in rec.fields.values():
            if trusted:
                f.status = FieldStatus.VERIFIED
                f.note = "layout proven on all samples, round-trip ok, checks pass" if fits else \
                    "before the first damaged record; round-trip ok, checks pass"
            else:
                f.status, f.note = FieldStatus.UNVERIFIED, "not proven: " + ", ".join(why or ["unknown"])
        verified += trusted
    return GateSummary(proven, fits, first_bad, verified, notes)


def _safe(check: Check, value, prev) -> bool:
    try:
        return bool(check(value, prev))
    except Exception:
        return False
