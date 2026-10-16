"""Generate clean synthetic test files from encoders / sample generators.
OWNER: Manas (delivery).

Provides ground truth reference files for the corruption lab and test suite.
Shares the same source of truth as decoders and sample generators.
"""
from __future__ import annotations

import random
from pathlib import Path

# Try importing from tools if available
try:
    from tools import make_samples, practice
    _HAS_TOOLS = True
except ImportError:
    _HAS_TOOLS = False


def generate_synthetic(fmt: str, k: int = 0, seed: int = 2026) -> tuple[bytes, dict]:
    """Generate clean synthetic binary bytes and associated ground truth dictionary.

    Returns:
        (clean_bytes, ground_truth_dict)
    """
    rng = random.Random(seed + k)

    if _HAS_TOOLS and hasattr(make_samples, "MAKERS") and fmt in make_samples.MAKERS:
        make_fn, _ext = make_samples.MAKERS[fmt]
        return make_fn(rng, k)

    # Fallback to existing sample fixtures on disk
    search_paths = [
        Path(f"samples/{fmt}"),
        Path(f"tests/fixtures/clean/{fmt}"),
        Path("samples"),
    ]
    for sp in search_paths:
        if sp.is_dir():
            for f in sorted(sp.glob("*")):
                if f.is_file() and not f.name.endswith(".md") and "damaged" not in f.name:
                    data = f.read_bytes()
                    return data, {
                        "format": fmt,
                        "source_file": f.name,
                        "size": len(data),
                        "note": "from disk fixture",
                    }

    # Generic synthetic block with header and records if no maker or sample exists
    header = f"{fmt.upper():<8}".encode()[:8]
    body = b"".join(f"RECORD_{i:04d}".encode() for i in range(10))
    synthetic_data = header + body
    return synthetic_data, {
        "format": fmt,
        "size": len(synthetic_data),
        "note": "minimal synthetic fallback",
    }


def supported_formats() -> list[str]:
    """List formats supported by synthetic generation or fixtures."""
    fmts = ["libra98", "lablog", "vault", "wks", "pak"]
    return fmts
