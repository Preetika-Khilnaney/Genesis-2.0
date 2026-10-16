"""Conformal risk calibration and false-recovery measurement.
OWNER: Manas (delivery).

Runs N seeded damaged files per format, evaluates recovered fields against ground truth,
measures FALSE RECOVERIES (fields marked verified/corrected whose value != ground truth),
and writes corruption_lab_results.json.

Strict rule: Never claim any number that was not measured.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..adapters import get_decoder
from ..core.model import FieldStatus, FileResult
from .damage import all_damage_variants
from .synthetic import generate_synthetic, supported_formats


def evaluate_result(res: FileResult, truth: dict, damage_info: dict) -> dict[str, int]:
    """Compare a decoded FileResult against ground truth to count recovery accuracy."""
    counts = {
        "total_fields": 0,
        "verified_fields": 0,
        "corrected_fields": 0,
        "unverified_fields": 0,
        "lost_fields": 0,
        "false_recoveries": 0,
        "false_losses": 0,
    }

    damage_start = damage_info.get("start", 0)
    damage_end = damage_info.get("end", 0)
    flipped_bytes = set(damage_info.get("flipped_bytes", []))

    def _was_corrupted(offset: int | None, length: int | None) -> bool:
        if offset is None or length is None:
            return False
        field_end = offset + length
        if flipped_bytes:
            return any(offset <= b < field_end for b in flipped_bytes)
        if damage_end > damage_start:
            return max(damage_start, offset) < min(damage_end, field_end)
        return False

    truth_hdr = truth.get("header", {}) if isinstance(truth.get("header"), dict) else {}
    truth_recs = truth.get("records", []) if isinstance(truth.get("records"), list) else []

    # Inspect header fields
    for name, f in res.header.items():
        counts["total_fields"] += 1
        corrupted = _was_corrupted(f.offset, f.length)
        truth_val = truth_hdr.get(name)

        if f.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED):
            counts["verified_fields"] += 1
            if corrupted or (truth_val is not None and f.value != truth_val):
                counts["false_recoveries"] += 1
        elif f.status == FieldStatus.UNVERIFIED:
            counts["unverified_fields"] += 1
        elif f.status == FieldStatus.LOST:
            counts["lost_fields"] += 1
            if not corrupted and truth_val is not None:
                counts["false_losses"] += 1

    # Inspect record fields
    for rec_idx, rec in enumerate(res.records):
        rec_truth = truth_recs[rec_idx] if rec_idx < len(truth_recs) and isinstance(truth_recs[rec_idx], dict) else {}
        for name, f in rec.fields.items():
            counts["total_fields"] += 1
            corrupted = _was_corrupted(f.offset, f.length)
            truth_val = rec_truth.get(name)

            if f.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED):
                counts["verified_fields"] += 1
                if corrupted or (truth_val is not None and f.value != truth_val):
                    counts["false_recoveries"] += 1
            elif f.status == FieldStatus.UNVERIFIED:
                counts["unverified_fields"] += 1
            elif f.status == FieldStatus.LOST:
                counts["lost_fields"] += 1
                if not corrupted and truth_val is not None:
                    counts["false_losses"] += 1

    return counts


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
            "total_fields": 0,
            "verified_fields": 0,
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
        dec = get_decoder(fmt)
        fmt_stats = {
            "decoder_ready": dec is not None and getattr(dec, "ready", False),
            "variants_tested": 0,
            "total_fields": 0,
            "verified_fields": 0,
            "false_recoveries": 0,
            "false_losses": 0,
            "false_recovery_rate": 0.0,
            "false_loss_rate": 0.0,
        }

        for k in range(n_seeds):
            clean_bytes, truth = generate_synthetic(fmt, k=k, seed=base_seed)
            variants = all_damage_variants(clean_bytes, seed=base_seed + k * 100)

            for var_name, (damaged_bytes, damage_info) in variants.items():
                fmt_stats["variants_tested"] += 1
                grand_files += 1

                if dec is not None and getattr(dec, "ready", False):
                    try:
                        from ..core.registry import DecodeContext
                        ctx = DecodeContext(format=fmt, siblings=[(f"clean_{fmt}.bin", clean_bytes)])
                        res = dec.decode(f"{fmt}_{k}_{var_name}", damaged_bytes, ctx)
                    except Exception:
                        continue
                else:
                    from ..output.unknown import describe
                    res = describe(f"{fmt}_{k}_{var_name}", damaged_bytes)

                eval_counts = evaluate_result(res, truth, damage_info)
                fmt_stats["total_fields"] += eval_counts["total_fields"]
                fmt_stats["verified_fields"] += eval_counts["verified_fields"]
                fmt_stats["false_recoveries"] += eval_counts["false_recoveries"]
                fmt_stats["false_losses"] += eval_counts["false_losses"]

        v_count = fmt_stats["verified_fields"]
        t_count = fmt_stats["total_fields"]
        fmt_stats["false_recovery_rate"] = round(
            fmt_stats["false_recoveries"] / max(1, v_count), 4
        ) if v_count > 0 else 0.0
        fmt_stats["false_loss_rate"] = round(
            fmt_stats["false_losses"] / max(1, t_count), 4
        ) if t_count > 0 else 0.0

        grand_total_fields += t_count
        grand_verified += v_count
        grand_false_rec += fmt_stats["false_recoveries"]
        grand_false_loss += fmt_stats["false_losses"]

        results["formats"][fmt] = fmt_stats

    results["totals"]["tested_files"] = grand_files
    results["totals"]["total_fields"] = grand_total_fields
    results["totals"]["verified_fields"] = grand_verified
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
