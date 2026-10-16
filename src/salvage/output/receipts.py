"""Hash-chained receipts (tamper-evident audit trail). OWNER: Manas (delivery). STRETCH GOAL.

One line per input in receipts.jsonl. Each entry hashes the previous entry, so
editing or deleting any entry breaks the chain (verify with `verify_chain`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..core.model import FileResult

GENESIS = "0" * 64


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_chain(out_dir: Path, input_root: Path, results: list[FileResult]) -> Path:
    path = out_dir / "receipts.jsonl"
    prev = GENESIS
    lines = []
    for r in results:
        src = input_root / r.source_file
        input_hash = _sha(src.read_bytes()) if src.is_file() else None
        entry = {
            "source_file": r.source_file,
            "input_sha256": input_hash,
            "format": r.format,
            "spec_version": getattr(r, "extra", {}).get("spec_version"),
            "field_status": r.status_counts(),
            "prev": prev,
        }
        body = json.dumps(entry, sort_keys=True).encode()
        entry["hash"] = _sha(body)
        prev = entry["hash"]
        lines.append(json.dumps(entry, sort_keys=True))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def verify_chain(path: Path) -> bool:
    prev = GENESIS
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        h = entry.pop("hash")
        if entry["prev"] != prev or _sha(json.dumps(entry, sort_keys=True).encode()) != h:
            return False
        prev = h
    return True
