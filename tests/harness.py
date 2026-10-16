"""Central test harness helpers. OWNER: Manas (delivery).

Provides:
  run_salvage(input_dir, *, extra_args) -> (per_file_outputs, report, exit_code)

Tests use this and never shell out directly, so we can switch between the
programmatic CLI and the subprocess if needed without touching every test file.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from salvage.adapters import run_cli
from salvage.output.schema_validate import VALID_STATUSES, validate_output_dir


def run_salvage(
    input_dir: Path,
    *,
    output_dir: Path | None = None,
    extra_args: list[str] | None = None,
) -> tuple[dict[str, dict], dict, int]:
    """Run the CLI against input_dir and return (per_file_outputs, report, exit_code).

    per_file_outputs is a dict of filename -> parsed JSON.
    report is the parsed report.json dict.
    Callers are responsible for cleaning up output_dir if they supply one.
    """
    if output_dir is None:
        # Use a temp dir; the caller doesn't clean it up but Python will at process end.
        td = tempfile.mkdtemp(prefix="salvage_test_")
        output_dir = Path(td)

    code = run_cli(input_dir, output_dir, extra_args)

    report_path = output_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}

    outputs: dict[str, dict] = {}
    for p in sorted(output_dir.glob("*.json")):
        if p.name == "report.json":
            continue
        try:
            outputs[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            outputs[p.name] = {}

    return outputs, report, code


def assert_schema_valid(output_dir: Path) -> None:
    """Fail the test if any output in output_dir violates the schemas."""
    errs = validate_output_dir(output_dir)
    assert not errs, "Schema errors:\n" + "\n".join(errs)


def assert_no_invented_values(file_result: dict) -> None:
    """The 'never invent data' invariant for contract output: an unrecognized file has no
    records, and a failed or unsupported file has no verified records."""
    status = file_result.get("status")
    if status == "unrecognized":
        assert file_result.get("records") == [], f"unrecognized file invented records: {file_result['records']}"
    if status in ("failed", "unsupported"):
        assert all(r.get("verified") is False for r in file_result.get("records", [])), \
            "failed/unsupported file has records not marked verified=false"


def assert_only_valid_statuses(file_result: dict) -> None:
    """Assert that the file status is one of the contract's five."""
    found: set[str] = set()
    from salvage.output.schema_validate import _collect_field_statuses
    _collect_field_statuses(file_result, found)
    bad = found - VALID_STATUSES
    assert not bad, f"Illegal status labels in output: {sorted(bad)}"


# ── pytest fixtures ────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_input(tmp_path):
    """Yields an empty input directory."""
    d = tmp_path / "in"
    d.mkdir()
    return d


@pytest.fixture()
def tmp_output(tmp_path):
    """Yields an empty output directory."""
    d = tmp_path / "out"
    d.mkdir()
    return d
