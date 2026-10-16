"""./salvage <input_dir> <output_dir>   OWNER: Preetika (core).

Walks input_dir, identifies each file, decodes it, and writes one JSON per input
plus report.json. Every file is isolated in try/except: one bad file never stops
the run, and the process ALWAYS exits 0.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from . import formats  # noqa: F401  (importing registers every decoder)
from .core.fingerprint import identify
from .core.model import FileResult
from .output import receipts, report, unknown, writer


def process_file(path: Path, root: Path) -> FileResult:
    rel = str(path.relative_to(root))
    try:
        data = path.read_bytes()
    except Exception as e:  # unreadable file
        return FileResult(source_file=rel, format="unknown", error=f"read failed: {e}")

    decoder, conf = identify(data)
    if decoder is None:
        return unknown.describe(rel, data, best_confidence=conf)

    try:
        result = decoder.decode(rel, data)
        result.confidence = conf
        return result
    except Exception as e:
        # Decoder crashed: report it, fall back to the unknown-file description.
        res = unknown.describe(rel, data, best_confidence=conf)
        res.format = decoder.name
        res.error = f"{type(e).__name__}: {e}"
        res.warnings.append("decoder crashed; see error. Traceback tail: "
                            + traceback.format_exc().strip().splitlines()[-1])
        return res


def run(input_dir: str, output_dir: str) -> int:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(input_dir)
    results: list[FileResult] = []

    if not root.is_dir():
        report.write(out, results, fatal=f"input_dir not found or not a directory: {input_dir}")
        return 0

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        res = process_file(path, root)
        results.append(res)
        try:
            writer.write_result(out, res)
        except Exception as e:
            res.error = (res.error or "") + f" | write failed: {e}"

    try:
        receipts.write_chain(out, root, results)
    except Exception as e:
        print(f"warning: receipts failed: {e}", file=sys.stderr)
    report.write(out, results)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="salvage", description="Recover records from undocumented legacy binary files.")
    p.add_argument("input_dir")
    p.add_argument("output_dir")
    p.add_argument("--discover", action="store_true",
                   help="(optional, dev only) let the local model propose layouts for unknown formats")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 0  # bad arguments still exit 0, as required
    try:
        return run(args.input_dir, args.output_dir)
    except Exception:
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
