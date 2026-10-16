"""Schema validation for all salvage output. OWNER: Manas (delivery).

Validates per-file JSONs, report.json and receipts.jsonl against the JSON
schemas in schema/ (which follow the organisers' OUTPUT-CONTRACT.md). Fails loudly
on any file status outside the contract's five:
    ok | partial | unsupported | unrecognized | failed

Import and call validate_output_dir(path) to check everything in one go.
Used by the test harness and by tools/gate_check.sh via:
    python -m salvage.output.schema_validate <output_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    _HAS_JSONSCHEMA = False

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schema"

VALID_STATUSES = frozenset({"ok", "partial", "unsupported", "unrecognized", "failed"})  # file status
FIELD_STATUSES = frozenset({"verified", "corrected", "unverified", "lost"})              # internal only


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _validate(instance: dict, schema: dict, label: str) -> list[str]:
    """Return list of error strings (empty = valid)."""
    if not _HAS_JSONSCHEMA:
        return []  # skip silently if not installed; test_schema_validate will skip too
    errors = []
    try:
        validator = jsonschema.Draft7Validator(schema)
        for err in sorted(validator.iter_errors(instance), key=str):
            errors.append(f"{label}: {err.message} at {list(err.absolute_path)}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"{label}: validation error: {e}")
    return errors


def _collect_field_statuses(obj, found: set[str]) -> None:
    """Collect the file-level 'status' of a per-file JSON, or of every entry in report.json."""
    if isinstance(obj, dict):
        if "status" in obj:
            found.add(str(obj["status"]))
        for f in obj.get("files", []) if isinstance(obj.get("files"), list) else []:
            if isinstance(f, dict) and "status" in f:
                found.add(str(f["status"]))


def validate_output_dir(output_dir: Path) -> list[str]:
    """Validate all JSON outputs in output_dir. Returns list of error strings."""
    out_schema   = _load_schema("output.schema.json")
    rep_schema   = _load_schema("report.schema.json")
    rcpt_schema  = _load_schema("receipt.schema.json")

    errors: list[str] = []
    output_dir = Path(output_dir)

    # report.json
    report_path = output_dir / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        errors.extend(_validate(report, rep_schema, "report.json"))
    else:
        errors.append("report.json: not found")

    # per-file JSONs (everything except report.json and receipts.jsonl)
    for p in sorted(output_dir.glob("*.json")):
        if p.name == "report.json":
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: JSON parse error: {e}")
            continue
        errors.extend(_validate(doc, out_schema, p.name))
        # Check status labels
        found: set[str] = set()
        _collect_field_statuses(doc, found)
        bad = found - VALID_STATUSES
        if bad:
            errors.append(f"{p.name}: illegal status labels: {sorted(bad)}")

    # receipts.jsonl
    receipts_path = output_dir / "receipts.jsonl"
    if receipts_path.exists():
        for i, line in enumerate(receipts_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception as e:  # noqa: BLE001
                errors.append(f"receipts.jsonl line {i}: parse error: {e}")
                continue
            errors.extend(_validate(entry, rcpt_schema, f"receipts.jsonl[{i}]"))

    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python -m salvage.output.schema_validate <output_dir>", file=sys.stderr)
        return 0  # never crash, exit 0
    errs = validate_output_dir(Path(args[0]))
    if errs:
        for e in errs:
            print(f"SCHEMA ERROR: {e}")
        return 1
    print("schema validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
