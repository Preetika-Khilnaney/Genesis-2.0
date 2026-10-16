"""OUTPUT-CONTRACT.md mapping. OWNER: Manas (delivery), with Preetika (core).

The ONE place that turns our internal FileResult into the organisers' per-file JSON and the
report.json summary. Decoders never write JSON themselves.

Per-file JSON:
    {"source_file", "format", "status", "metadata", "records", "damage"}
status:
    ok           nothing lost (repaired damage with lossy=false is still ok)
    partial      some data lost or unverified
    unsupported  recognised but cannot decode (e.g. encrypted)       -> decoder sets res.status
    unrecognized unknown format
    failed       recognised but unreadable (crash, or nothing decodable)
damage[]: {"kind", "offset", "length", "detail", "lossy"} with kind from the contract vocabulary.
records[]: the format's graded fields; "verified": false and/or "issues": [kinds] when needed.
"""
from __future__ import annotations

from typing import Any

from ..core.model import DamageCause, FieldStatus, FileResult, Record

UNKNOWN = "UNKNOWN"
STATUSES = ("ok", "partial", "unsupported", "unrecognized", "failed")

KINDS = {"truncated", "crc_mismatch", "checksum_mismatch", "bad_length", "unparsed_bytes",
         "count_mismatch", "invalid_value", "oob_pointer", "index_missing", "header_checksum",
         "encrypted", "unknown_record"}

# Older internal cause names (generic helpers) -> contract vocabulary
LEGACY = {"crc_fail": "crc_mismatch", "bad_offset": "oob_pointer", "bad_key": "encrypted",
          "index_overlap": "oob_pointer", "bad_magic": "invalid_value", "unknown": "unparsed_bytes"}


def kind_of(cause: DamageCause | str) -> str:
    v = cause.value if isinstance(cause, DamageCause) else str(cause)
    v = LEGACY.get(v, v)
    return v if v in KINDS else "unparsed_bytes"


def format_name(res: FileResult) -> str:
    return UNKNOWN if res.format in ("unknown", "", None, UNKNOWN) else res.format


def record_values(rec: Record) -> dict[str, Any]:
    if rec.values is not None:
        out = dict(rec.values)
    else:
        out = {k: f.value for k, f in rec.fields.items()}
    verified = rec.verified and all(f.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED)
                                    for f in rec.fields.values())
    if not verified:
        out["verified"] = False
    if rec.issues:
        out["issues"] = sorted(set(rec.issues), key=rec.issues.index)
    return out


def status_of(res: FileResult) -> str:
    if format_name(res) == UNKNOWN:
        return "unrecognized"
    if res.status in STATUSES:
        return res.status
    if res.error:
        return "failed"
    recs = [record_values(r) for r in res.records]
    if any(d.lossy for d in res.damage) or any(r.get("verified") is False for r in recs):
        return "partial"
    return "ok"


def damage_entry(d) -> dict[str, Any]:
    return {"kind": kind_of(d.cause), "offset": d.start, "length": max(0, d.end - d.start),
            "detail": d.detail, "lossy": bool(d.lossy)}


def to_contract(res: FileResult) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_file": res.source_file,
        "format": format_name(res),
        "status": status_of(res),
        "metadata": res.metadata if format_name(res) != UNKNOWN else _unknown_metadata(res),
        "records": [record_values(r) for r in res.records],
        "damage": [damage_entry(d) for d in res.damage],
    }
    if res.warnings:
        out["warnings"] = res.warnings
    if res.error:
        out["error"] = res.error
    return out


def _unknown_metadata(res: FileResult) -> dict[str, Any]:
    """For unrecognized files: what we can still say about them (size, entropy, strings)."""
    return dict(res.metadata)


def report(results: list[FileResult], tool_version: str, fatal: str | None = None) -> dict[str, Any]:
    files, totals = [], {s: 0 for s in STATUSES}
    for r in results:
        c = to_contract(r)
        totals[c["status"]] += 1
        files.append({"file": c["source_file"], "format": c["format"], "status": c["status"],
                      "records": len(c["records"]), "damage": len(c["damage"])})
    out: dict[str, Any] = {"tool_version": tool_version, "files": files, "totals": totals}
    if fatal:
        out["fatal"] = fatal
    return out
