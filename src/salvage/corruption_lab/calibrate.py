"""Conformal risk calibration and false-recovery measurement.
OWNER: Manas (delivery).

Damages every format's clean real samples on purpose (bit flips, truncation, zeroed blocks,
inserted / deleted bytes, wrecked headers, trailing garbage), decodes each copy, and measures
FALSE RECOVERIES (records the tool calls verified that differ from the clean file) and false
losses. Writes corruption_lab_results.json.

Strict rule: Never claim any number that was not measured.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..core.registry import get
from ..output.contract import to_contract
from .damage import all_damage_variants
from .sources import clean_sample, strip, supported_formats


def evaluate_result(doc: dict, truth: dict) -> dict[str, int]:
    """Compare a damaged copy's contract output with the clean file's records.

    A FALSE RECOVERY is a record the tool calls verified (no "verified": false) whose content
    differs from the clean record with the same key, or whose key does not exist in the clean
    file. Unverified records are allowed to be wrong: the tool said it was unsure.
    A FALSE LOSS is a clean record that is missing from the output although the damage did not
    remove the whole file."""
    key, recs = truth["key"], truth["records"]
    c = {"total_records": len(recs), "verified_records": 0, "unverified_records": 0,
         "false_recoveries": 0, "false_losses": 0}
    seen = set()
    for r in doc.get("records", []):
        k = r.get(key)
        seen.add(k)
        if r.get("verified") is False:
            c["unverified_records"] += 1
            continue
        c["verified_records"] += 1
        if recs.get(k) != strip(r):
            c["false_recoveries"] += 1
    c["false_losses"] = sum(1 for k in recs if k not in seen)
    return c


def run_calibration(
    formats: list[str] | None = None,
    n_seeds: int = 5,
    base_seed: int = 42,
    out_file: Path | str = "corruption_lab_results.json",
) -> dict:
    """Run calibration across formats and damage types, outputting measured metrics."""
    target_formats = formats or supported_formats()
    results: dict = {
        "formats": {},
        "totals": {
            "tested_files": 0,
            "total_records": 0,
            "verified_records": 0,
            "false_recoveries": 0,
            "false_recovery_rate": 0.0,
            "false_loss_rate": 0.0,
        },
    }

    grand_total_fields = 0
    grand_verified = 0
    grand_false_rec = 0
    grand_false_loss = 0
    grand_files = 0

    for fmt in target_formats:
        dec = get(fmt)
        st = {"variants_tested": 0, "total_records": 0, "verified_records": 0, "false_recoveries": 0,
              "false_losses": 0, "false_recovery_rate": 0.0, "false_loss_rate": 0.0}
        for k in range(n_seeds):
            clean_bytes, truth = clean_sample(fmt, k)
            for var_name, (damaged, _info) in all_damage_variants(clean_bytes, seed=base_seed + k * 100).items():
                st["variants_tested"] += 1
                grand_files += 1
                try:
                    doc = to_contract(dec.decode(f"{truth['source_file']}.{var_name}", damaged))
                except Exception:          # a crash would be a bug: count it as losing everything
                    doc = {"records": []}
                ev = evaluate_result(doc, truth)
                for name in ("total_records", "verified_records", "false_recoveries", "false_losses"):
                    st[name] += ev[name]
        st["false_recovery_rate"] = round(st["false_recoveries"] / st["verified_records"], 4) if st["verified_records"] else 0.0
        st["false_loss_rate"] = round(st["false_losses"] / st["total_records"], 4) if st["total_records"] else 0.0
        grand_total_fields += st["total_records"]
        grand_verified += st["verified_records"]
        grand_false_rec += st["false_recoveries"]
        grand_false_loss += st["false_losses"]
        results["formats"][fmt] = st

    results["totals"]["tested_files"] = grand_files
    results["totals"]["total_records"] = grand_total_fields
    results["totals"]["verified_records"] = grand_verified
    results["totals"]["false_recoveries"] = grand_false_rec
    results["totals"]["false_recovery_rate"] = round(
        grand_false_rec / max(1, grand_verified), 4
    ) if grand_verified > 0 else 0.0
    results["totals"]["false_loss_rate"] = round(
        grand_false_loss / max(1, grand_total_fields), 4
    ) if grand_total_fields > 0 else 0.0

    out_path = Path(out_file)
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run corruption lab calibration and measure false recoveries.")
    parser.add_argument("--out", type=Path, default=Path("corruption_lab_results.json"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    print(f"Running corruption lab calibration ({args.runs} seeds)...")
    res = run_calibration(n_seeds=args.runs, base_seed=args.seed, out_file=args.out)
    print(f"Calibration finished. Tested {res['totals']['tested_files']} variants.")
    print(f"Measured false recovery rate: {res['totals']['false_recovery_rate']}")
    print(f"Wrote measured rates to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
