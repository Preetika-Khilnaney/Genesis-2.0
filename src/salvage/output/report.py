"""report.json for the whole run. OWNER: Manas (delivery).

Summarises every file: detected format, status counts, damage with byte ranges and
causes, and errors. This is what judges read to see what was lost and why.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import __version__
from ..core.model import FileResult


def build(results: list[FileResult], fatal: str | None = None) -> dict:
    files = []
    totals: dict[str, int] = {}
    summary = {"ok": 0, "partial": 0, "unknown": 0, "failed": 0}

    for r in results:
        counts = r.status_counts()
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v

        # Classify file status for run summary
        if r.error is not None:
            summary["failed"] += 1
        elif r.format == "unknown":
            summary["unknown"] += 1
        elif r.damage or counts.get("lost", 0) > 0:
            summary["partial"] += 1
        else:
            summary["ok"] += 1

        files.append({
            "source_file": r.source_file,
            "input_sha256": getattr(r, "input_sha256", None) or r.extra.get("input_sha256"),
            "format": r.format,
            "confidence": round(r.confidence, 3),
            "records": len(r.records),
            "field_status": counts,
            "damage": [d.to_dict() for d in r.damage],
            "warnings": r.warnings,
            "error": r.error,
        })

    return {
        "tool_version": __version__,
        "files_processed": len(results),
        "formats": sorted({r.format for r in results}),
        "unknown_files": sum(1 for r in results if r.format == "unknown"),
        "files_with_damage": sum(1 for r in results if r.damage),
        "summary": summary,
        "field_status_totals": totals,
        "fatal": fatal,
        "files": files,
    }


def write(out_dir: Path, results: list[FileResult], fatal: str | None = None) -> Path:
    """Write report.json atomically (write to temp file, then atomic rename)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "report.json"
    temp = out_dir / "report.json.tmp"
    data = json.dumps(build(results, fatal), indent=2, ensure_ascii=False) + "\n"
    temp.write_text(data, encoding="utf-8")
    temp.replace(target)
    return target
