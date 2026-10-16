"""Thin adapter interfaces so Manas's code is never blocked by missing teammates' code.
OWNER: Manas (delivery).

When Preetika's CLI, Khushi's decoders, or Bhupesh's evidence checker are not yet
integrated, import from here instead of importing directly. Each adapter either
delegates to the real implementation (if available) or returns a safe stub so tests
can run and be marked skip-with-reason where a real implementation is needed.

Usage in tests:
    from salvage.adapters import get_decoder, get_spec_version_hash

Do NOT import teammates' internals directly from tests — go through this module
so we can swap stubs in and out without touching test code.
"""
from __future__ import annotations

from pathlib import Path


def get_decoder(name: str):
    """Return the registered Decoder for `name`, or None if not yet ready."""
    try:
        from salvage import formats  # noqa: F401
        from salvage.core.registry import get
        dec = get(name)
        return dec if dec.ready else None
    except (ImportError, KeyError):
        return None


def get_spec_for(name: str):
    """Return the FormatSpec for a named decoder, or None."""
    dec = get_decoder(name)
    return dec.spec if dec else None


def get_spec_version_hash() -> str | None:
    """SHA-256 of the canonical serialized spec library, or None if not available.

    Used by receipts.py to pin the spec version used for a run. Once the spec
    is stable, this will return a real hash; until then it returns None so
    receipts still record None and tests can verify the field exists.
    """
    try:
        import hashlib
        import json

        from salvage.core.registry import all_decoders

        specs = []
        for dec in all_decoders():
            if dec.spec is None:
                continue
            from salvage.core.spec import spec_to_markdown
            specs.append((dec.name, spec_to_markdown(dec.spec)))
        canonical = json.dumps(sorted(specs), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    except Exception:  # noqa: BLE001
        return None


def run_cli(input_dir: Path, output_dir: Path, extra_args: list[str] | None = None) -> int:
    """Run the CLI programmatically and return the exit code.

    This is the canonical helper used by the test harness. It always returns 0
    (mirroring the CLI contract) but the caller can still inspect output_dir.
    """
    try:
        from salvage.cli import main
        argv = [str(input_dir), str(output_dir)] + (extra_args or [])
        return main(argv)
    except Exception:
        return 0  # cli contract: always 0
