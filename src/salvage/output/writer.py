"""Per-file JSON writer. OWNER: Manas (delivery).

Writes `<output_dir>/<input file name>.json` (e.g. s01.dat.json) in the shape of
OUTPUT-CONTRACT.md. The mapping itself lives in output/contract.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.model import FileResult
from .contract import to_contract


def output_name(source_file: str) -> str:
    """The contract wants the exact input file name plus '.json'."""
    return Path(source_file).name + ".json"


def to_schema(res: FileResult) -> dict:
    return to_contract(res)


def write_result(out_dir: Path, res: FileResult) -> Path:
    path = Path(out_dir) / output_name(res.source_file)
    path.write_text(json.dumps(to_schema(res), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
