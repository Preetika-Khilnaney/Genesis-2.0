"""./salvage <input_dir> <output_dir>   OWNER: Preetika (core).

Reads every file directly in input_dir (sub-directories are skipped), identifies each
file, decodes it, and writes one JSON per input plus report.json (OUTPUT-CONTRACT.md). Every file is isolated in try/except: one bad file never stops
the run, and the process ALWAYS exits 0.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import formats  # noqa: F401  (importing registers every decoder)
from .core.fingerprint import identify_detailed
from .core.model import DamageCause, DamageEntry, FieldStatus, FileResult
from .core.registry import DecodeContext, Decoder
from .output import receipts, report, unknown, writer

# Cap on siblings handed to a decoder, so a huge folder of one format stays fast.
MAX_SIBLINGS = 64


@dataclass
class Scanned:
    """Pass-1 result for one file."""
    rel: str
    data: bytes | None
    decoder: Decoder | None
    confidence: float
    read_error: str | None = None
    method: str = "none"                                    # how it was identified (see fingerprint.py)
    damaged_magic: list[int] = field(default_factory=list)


def scan(path: Path, root: Path) -> Scanned:
    """Pass 1: read and fingerprint one file. Never raises."""
    rel = path.relative_to(root).as_posix()  # "/" on every OS, so output is identical everywhere
    try:
        data = path.read_bytes()
    except Exception as e:
        return Scanned(rel, None, None, 0.0, read_error=f"read failed: {e}")
    try:
        ident = identify_detailed(data)
    except Exception as e:
        return Scanned(rel, data, None, 0.0, read_error=f"fingerprint failed: {e}")
    return Scanned(rel, data, ident.decoder, ident.confidence,
                   method=ident.method, damaged_magic=ident.damaged_magic)


def annotate_identification(res: FileResult, s: Scanned) -> None:
    """Record HOW a file was identified, and the damage implied by a fallback match."""
    res.extra.setdefault("identified_by", s.method)
    if s.method not in ("near_magic", "structure"):
        return
    spec = s.decoder.spec
    if s.method == "near_magic" and s.damaged_magic:
        bad = list(s.damaged_magic)
        detail = (f"magic bytes damaged at offsets {bad}; identified as {s.decoder.name} "
                  "from the rest of the signature")
    else:
        bad = list(range(spec.magic_offset, spec.magic_offset + len(spec.magic))) if spec and spec.magic else []
        detail = (f"magic/header signature did not match; identified as {s.decoder.name} "
                  "because its structure explains the whole file")
        res.warnings.insert(0, detail)
    if bad:
        res.damage.insert(0, DamageEntry(min(bad), max(bad) + 1, DamageCause.BAD_MAGIC, detail, ["magic"],
                                         lossy=False))
        res.metadata.setdefault("identified_by", s.method)
    # Any header field covering a damaged byte cannot be verified.
    for f in res.header.values():
        if f.offset is not None and f.length and any(f.offset <= o < f.offset + f.length for o in bad):
            f.status = FieldStatus.UNVERIFIED
            f.note = "overlaps damaged magic bytes"


def group_by_format(scanned: list[Scanned]) -> dict[str, list[Scanned]]:
    groups: dict[str, list[Scanned]] = {}
    for s in scanned:
        if s.decoder is not None:
            groups.setdefault(s.decoder.name, []).append(s)
    return groups


def context_for(s: Scanned, groups: dict[str, list[Scanned]]) -> DecodeContext:
    peers = [p for p in groups.get(s.decoder.name, []) if p is not s][:MAX_SIBLINGS]
    return DecodeContext(format=s.decoder.name, siblings=[(p.rel, p.data) for p in peers])


def decode_one(s: Scanned, ctx: DecodeContext | None) -> FileResult:
    """Pass 2: decode one file with its format's context. Never raises."""
    file_sha256 = hashlib.sha256(s.data).hexdigest() if s.data is not None else None
    if s.read_error is not None and s.data is None:
        return FileResult(source_file=s.rel, format="unknown", error=s.read_error, input_sha256=None)
    if s.decoder is None:
        res = unknown.describe(s.rel, s.data, best_confidence=s.confidence)
        res.input_sha256 = file_sha256
        if s.read_error:
            res.error = s.read_error
        return res
    try:
        result = s.decoder.decode(s.rel, s.data, ctx)
        for d in result.damage:            # damage offsets always point inside the file
            d.start = max(0, min(d.start, len(s.data)))
            d.end = max(d.start, min(d.end, len(s.data)))
        result.confidence = s.confidence
        result.input_sha256 = file_sha256
        annotate_identification(result, s)
        if ctx is not None:
            result.extra.setdefault("samples_in_context", ctx.sample_count)
        return result
    except Exception as e:
        # Decoder crashed: report it, fall back to the unknown-file description.
        res = unknown.describe(s.rel, s.data, best_confidence=s.confidence)
        res.format = s.decoder.name
        res.input_sha256 = file_sha256
        res.error = f"{type(e).__name__}: {e}"
        res.warnings.append("decoder crashed; see error. Traceback tail: "
                            + traceback.format_exc().strip().splitlines()[-1])
        annotate_identification(res, s)
        return res


def run(input_dir: str, output_dir: str) -> int:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(input_dir)
    results: list[FileResult] = []

    if not root.is_dir():
        report.write(out, results, fatal=f"input_dir not found or not a directory: {input_dir}")
        return 0

    # Pass 1: fingerprint everything, then group files by detected format.
    # The contract: every FILE directly in input_dir; sub-directories are skipped (non-recursive).
    scanned = [scan(p, root) for p in sorted((p for p in root.iterdir() if p.is_file()), key=lambda p: p.name)]
    groups = group_by_format(scanned)

    # Pass 2: decode each file with the other files of its format as context.
    for s in scanned:
        ctx = context_for(s, groups) if s.decoder is not None else None
        res = decode_one(s, ctx)
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
