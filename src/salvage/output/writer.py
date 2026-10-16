"""Per-file JSON writer. OWNER: Manas (delivery).

The ONLY place that maps our internal FileResult to the published output schema.
When the organisers' schema arrives, adapt `to_schema()` here and nowhere else.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..core.model import FileResult


def output_name(source_file: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", source_file)
    return f"{safe}.json"


def to_schema(res: FileResult) -> dict:
    # TODO(Manas): map to the published schema once we have it (schema/output.schema.json).
    return res.to_dict()


def write_result(out_dir: Path, res: FileResult) -> Path:
    path = out_dir / output_name(res.source_file)
    path.write_text(json.dumps(to_schema(res), indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    return path
