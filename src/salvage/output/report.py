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
    for r in results:
        counts = r.status_counts()
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
        files.append({
            "source_file": r.source_file,
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
        "field_status_totals": totals,
        "fatal": fatal,
        "files": files,
    }


def write(out_dir: Path, results: list[FileResult], fatal: str | None = None) -> Path:
    path = out_dir / "report.json"
    path.write_text(json.dumps(build(results, fatal), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
