"""Hypothesis property tests: salvage never crashes on arbitrary bytes, statuses are always valid.
OWNER: Manas (delivery).

Uses a fixed seed profile and bounded examples so `make test` runs fast (< 5 s).
Note: Hypothesis does NOT support function-scoped pytest fixtures (tmp_path).
      We create temp dirs manually inside each test.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salvage.adapters import run_cli
from salvage.output.schema_validate import VALID_STATUSES


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(content=st.binary(min_size=0, max_size=4096))
def test_never_crashes_on_arbitrary_bytes(content: bytes) -> None:
    """The CLI must not crash or return non-zero for any byte sequence."""
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "in"
        out = Path(td) / "out"
        inp.mkdir()
        (inp / "arb.bin").write_bytes(content)
        code = run_cli(inp, out)
        assert code == 0, f"Exit {code} on input len={len(content)}"
        assert (out / "report.json").exists(), "report.json missing"
        report = json.loads((out / "report.json").read_text())
        assert len(report["files"]) == 1 and report["files"][0]["status"] in VALID_STATUSES


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(content=st.binary(min_size=0, max_size=4096))
def test_no_illegal_status_on_arbitrary_bytes(content: bytes) -> None:
    """Status labels in output must always be one of the four legal values."""
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "in"
        out = Path(td) / "out"
        inp.mkdir()
        (inp / "arb.bin").write_bytes(content)
        run_cli(inp, out)
        for p in sorted(out.glob("*.json")):
            if p.name == "report.json":
                continue
            doc = json.loads(p.read_text())
            assert doc["status"] in VALID_STATUSES, f"illegal status {doc['status']!r} in {p.name}"


def _collect(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        if "status" in obj:
            found.add(str(obj["status"]))
        for v in obj.values():
            _collect(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect(item, found)
