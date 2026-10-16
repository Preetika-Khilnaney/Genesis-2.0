"""Clean source files for the corruption lab: the organisers' real samples. OWNER: Manas (delivery).

The ground truth for a format is what we decode from its CLEAN real samples (status "ok" and no
damage; several are also confirmed by the organisers' expected outputs). The lab damages these
files on purpose and compares what comes back with that truth.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .. import formats  # noqa: F401  (registers decoders)
from ..core.fingerprint import identify_detailed
from ..output.contract import to_contract

KIT = Path(__file__).resolve().parents[3] / "real-samples" / "samples"

# Key that identifies a record across a clean file and its damaged copy (contract "match_on").
KEYS = {"LIBRA-98": "id", "LABLOG": "sample", "VAULT": "id", "EBCDIC-DUMP": "student_id", "WKS": "cell",
        "CVT": "slot", "WAD": "name", "PAK": "name", "WPD": "index", "BRAVO": "index"}


@lru_cache(maxsize=None)
def _clean() -> dict[str, tuple[tuple[str, bytes, dict], ...]]:
    out: dict[str, list[tuple[str, bytes, dict]]] = {}
    if KIT.is_dir():
        for p in sorted(x for x in KIT.iterdir() if x.is_file()):
            b = p.read_bytes()
            dec = identify_detailed(b).decoder
            if dec is None:
                continue
            doc = to_contract(dec.decode(p.name, b))
            if doc["status"] == "ok" and not doc["damage"]:
                out.setdefault(dec.name, []).append((p.name, b, doc))
    return {k: tuple(v) for k, v in out.items()}


def supported_formats() -> list[str]:
    """Formats with at least one clean real sample."""
    return sorted(_clean())


def strip(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in ("verified", "issues")}


def clean_sample(fmt: str, k: int = 0) -> tuple[bytes, dict]:
    """(clean bytes, truth) for the k-th clean real sample of `fmt` (wraps around).
    truth = {"source_file", "format", "key", "records": {key value: record}}"""
    files = _clean().get(fmt)
    if not files:
        raise KeyError(f"no clean real sample for {fmt}")
    name, b, doc = files[k % len(files)]
    key = KEYS.get(fmt, "index")
    return b, {"source_file": name, "format": fmt, "key": key,
               "records": {r.get(key): strip(r) for r in doc["records"]}}
