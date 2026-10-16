"""Hash-chained receipts (tamper-evident audit trail). OWNER: Manas (delivery).

One line per input in receipts.jsonl. Each entry hashes the previous entry, so
editing, reordering, or deleting any entry breaks the chain (verify with `verify_chain`).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from ..core.model import FileResult

GENESIS = "0" * 64


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_chain(out_dir: Path, input_root: Path | None, results: list[FileResult]) -> Path:
    """Write hash-chained receipts to out_dir / receipts.jsonl atomically."""
    path = out_dir / "receipts.jsonl"
    prev = GENESIS
    lines = []

    # Get spec version hash if available
    spec_version = None
    try:
        from ..adapters import get_spec_version_hash
        spec_version = get_spec_version_hash()
    except Exception:  # noqa: BLE001
        spec_version = None

    for r in results:
        src = input_root / r.source_file if input_root else None
        input_hash = r.input_sha256
        if input_hash is None and src and src.is_file():
            try:
                input_hash = _sha(src.read_bytes())
            except Exception:  # noqa: BLE001
                input_hash = None

        r_spec_ver = (
            getattr(r, "extra", {}).get("spec_version")
            if hasattr(r, "extra") and isinstance(r.extra, dict)
            else None
        )
        if r_spec_ver is None:
            r_spec_ver = spec_version

        entry = {
            "source_file": r.source_file,
            "input_sha256": input_hash,
            "format": r.format,
            "spec_version": r_spec_ver,
            "field_status": r.status_counts(),
            "prev": prev,
        }
        body = json.dumps(entry, sort_keys=True).encode()
        entry["hash"] = _sha(body)
        prev = entry["hash"]
        lines.append(json.dumps(entry, sort_keys=True))

    content = "\n".join(lines) + ("\n" if lines else "")

    # Atomic write via temp file in same directory
    tmp_fd, tmp_path = tempfile.mkstemp(dir=out_dir, prefix="receipts_", suffix=".tmp")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)
    return path


def verify_chain(path: Path) -> bool:
    """Verify that receipts.jsonl exists, parses, and forms an unbroken hash chain."""
    if not path.is_file():
        return False
    prev = GENESIS
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return True
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if "hash" not in entry or "prev" not in entry:
                return False
            h = entry.pop("hash")
            if entry["prev"] != prev:
                return False
            expected_hash = _sha(json.dumps(entry, sort_keys=True).encode())
            if expected_hash != h:
                return False
            prev = h
        except Exception:
            return False
    return True
