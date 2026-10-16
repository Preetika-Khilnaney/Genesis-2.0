"""report.json for the whole run. OWNER: Manas (delivery).

One line per input file (format, status, record and damage counts) plus totals per
status, in the shape OUTPUT-CONTRACT.md defines. Details live in each file's own JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import __version__
from ..core.model import FileResult
from . import contract


def build(results: list[FileResult], fatal: str | None = None) -> dict:
    """report.json as OUTPUT-CONTRACT.md defines it:
    {"tool_version", "files": [{"file","format","status","records","damage"}], "totals": {...}}"""
    return contract.report(results, __version__, fatal)


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
