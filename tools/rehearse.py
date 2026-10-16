#!/usr/bin/env python3
"""Dress rehearsal: run ./salvage on the practice files and score it against the answers.

    python3 tools/practice.py --damaged     # once (or: make practice)
    python3 tools/rehearse.py               # or: make rehearse

It registers three PRACTICE decoders (below, never shipped: they live in tools/, not
formats/), runs the real CLI on practice/, and then checks every output field against
practice/*/answers. For damaged copies it uses manifest.json to find the right answer.

The number that matters is FALSE RECOVERIES: a field marked verified or corrected
whose value is wrong. That must be 0. Wrong values marked unverified are allowed (we
said we were unsure); lost fields cost recall but never cost trust.

The three decoders are also worked examples of how a real decoder should look:
    PracticeRec  -> header + records with evidence and plausibility checks (LIBRA-98 style)
    PracticeLog  -> core.blocks.read_blocks (LABLOG style)
    PracticeArc  -> core.index.read_index + RLE + XOR (VAULT style)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import practice  # noqa: E402
from salvage import cli  # noqa: E402
from salvage.core.blocks import BlockLayout, read_blocks  # noqa: E402
from salvage.core.index import read_index  # noqa: E402
from salvage.core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record  # noqa: E402
from salvage.core.reader import ByteReader, OutOfBounds  # noqa: E402
from salvage.core.registry import DecodeContext, Decoder, register  # noqa: E402
from salvage.core.gate import gate_records  # noqa: E402
from salvage.core.simple import decode_simple  # noqa: E402
from salvage.core.spec import FieldSpec, FormatSpec, decode_fields  # noqa: E402
from salvage.recovery.rle import VARIANTS, best_variant  # noqa: E402
from salvage.recovery.xor import best_fixed_string_key, xor  # noqa: E402

V, U, L, C = FieldStatus.VERIFIED, FieldStatus.UNVERIFIED, FieldStatus.LOST, FieldStatus.CORRECTED


# =================== practice decoders (worked examples) ===================

PREC_SPEC = FormatSpec(
    name="practice_rec", magic=practice.PREC_MAGIC, endian="little",
    header=[FieldSpec("magic", "bytes", 8), FieldSpec("version", "u8"), FieldSpec("record_count", "u16"),
            FieldSpec("created", "unix32"), FieldSpec("decoy", "u16"), FieldSpec("reserved", "bytes", 3)],
    record=[FieldSpec("id", "u32"), FieldSpec("name", "str", 20), FieldSpec("enrolled", "dos_date"),
            FieldSpec("grade", "u8"), FieldSpec("flags", "u8"), FieldSpec("pad", "bytes", 2)],
    record_count_field="record_count")
@register
class PracticeRec(Decoder):
    """LIBRA-98 style: decode_simple reads the fields, core.gate.gate_records decides what is
    VERIFIED (layout proven on all samples, file fits or record is before the damage,
    round-trip ok, every check passes). This is exactly how formats/libra98.py should look."""
    name, spec, ready = "practice_rec", PREC_SPEC, True
    CHECKS = {
        "id": lambda v, prev: prev is None or v == prev["id"] + 1,
        "name": lambda v, prev: v.isprintable() and v.strip() != "",
        "enrolled": lambda v, prev: _date_ok(v),
        "grade": lambda v, prev: 0 <= v <= 100,
        "flags": lambda v, prev: v in (0, 1, 2, 3),
        "pad": lambda v, prev: v == "0000",
    }

    def decode(self, path, data, ctx: DecodeContext | None = None) -> FileResult:
        res = decode_simple(self.spec, path, data)
        gate_records(res, data, self.spec, ctx.samples(data) if ctx else [data], self.CHECKS,
                     unknown_header=("decoy", "reserved"))
        return res


def _date_ok(s) -> bool:
    try:
        y, m, d = map(int, s.split("-"))
        return 1980 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31
    except Exception:
        return False


PLOG_LAYOUT = BlockLayout(marker=practice.PLOG_MARK, extra=[FieldSpec("seq", "u16")], length_type="u16",
                          checksum_algo="crc32", checksum_type="u32")


@register
class PracticeLog(Decoder):
    """LABLOG style: everything comes from read_blocks. CRC passes -> verified,
    provable one-bit fix -> corrected, otherwise the block is LOST and reported."""
    name, ready = "practice_log", True
    spec = FormatSpec(name="practice_log", magic=practice.PLOG_MAGIC, header=[FieldSpec("magic", "bytes", 4),
                                                                              FieldSpec("instrument", "u16")])

    def decode(self, path, data, ctx=None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        r = ByteReader(data)
        try:
            res.header = decode_fields(r, self.spec.header)
        except OutOfBounds:
            res.damage.append(DamageEntry(0, len(data), DamageCause.TRUNCATED, "file ends inside header", ["header"]))
            return res
        for f in res.header.values():
            f.status = V if f.name == "magic" else U   # header has no checksum
        scan = read_blocks(data, PLOG_LAYOUT, start=6)
        res.damage += scan.damage
        res.warnings += scan.warnings
        good = [b for b in scan.blocks if b.status in (V, C)]   # only checksum-proven blocks are evidence
        seqs = [b.header["seq"].value for b in good]
        for i, b in enumerate(good):
            # seq is outside the CRC: trust it only if it agrees with both neighbours (+1 steps)
            before = i == 0 or seqs[i - 1] == seqs[i] - 1
            after = i == len(good) - 1 or seqs[i + 1] == seqs[i] + 1
            if before and after and len(good) > 1:
                b.header["seq"].status, b.header["seq"].note = V, "counts up by 1 with its neighbours"
        for b in scan.blocks:
            seq = b.header["seq"]
            payload = Field("payload", b.payload.decode("latin-1") if b.status != L else None, b.status,
                            b.payload_offset, len(b.payload), b.note)
            res.records.append(Record(b.index, b.offset, {"seq": Field("seq", seq.value if b.status != L else None,
                                                                         seq.status if b.status != L else L,
                                                                         seq.offset, seq.length, seq.note),
                                                            "payload": payload}))
        return res


PARC_ENTRY = [FieldSpec("name", "bytes", 12), FieldSpec("offset", "u32"), FieldSpec("size", "u32"),
              FieldSpec("raw_size", "u32")]


@register
class PracticeArc(Decoder):
    """VAULT style: read_index for the table; RLE variant and XOR key are chosen across ALL
    samples, and each blob is verified by an exact RLE round trip plus raw_size matching."""
    name, ready = "practice_arc", True
    spec = FormatSpec(name="practice_arc", magic=practice.PARC_MAGIC,
                      header=[FieldSpec("magic", "bytes", 4), FieldSpec("entry_count", "u16")])

    def decode(self, path, data, ctx=None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        if len(data) < 6:
            res.damage.append(DamageEntry(0, len(data), DamageCause.TRUNCATED, "file ends inside header", ["header"]))
            return res
        r = ByteReader(data)
        res.header = decode_fields(r, self.spec.header)
        res.header["magic"].status = V
        count = res.header["entry_count"].value
        scan = read_index(data, 6, count, PARC_ENTRY)
        res.damage += scan.damage
        res.warnings += scan.warnings
        key, variant = self._key_and_variant(data, ctx)
        res.extra["xor_key"] = key
        res.extra["rle_variant"] = variant
        for e in scan.entries:
            name_raw = bytes.fromhex(e.fields["name"].value)
            name = xor(name_raw, bytes([key])).rstrip(b"\x00") if key is not None else b""
            plain = xor(name_raw, bytes([key])) if key is not None else b""
            # printable text, then only NUL padding (or a name that fills the whole field)
            name_ok = key is not None and bool(name) and all(32 <= c < 127 for c in name) \
                and plain[len(name):] == bytes(len(plain) - len(name))
            if not name_ok:
                n_status, n_note = U, "name did not decode cleanly"
            elif not scan.tiles_exactly:
                n_status, n_note = U, "decodes, but the index does not tile the file"
            else:
                n_status, n_note = V, "xor key chosen on all samples, NUL padding intact"
            fields = {"name": Field("name", name.decode("latin-1") if name_ok else None, n_status,
                                    e.fields["name"].offset, 12, n_note)}
            content, status, note = None, L, e.note or "entry not usable"
            if e.ok and variant:
                dec, enc = VARIANTS[variant]
                try:
                    out = dec(e.blob)
                    if enc(out) == e.blob and len(out) == e.fields["raw_size"].value:
                        if scan.tiles_exactly:
                            content, status, note = out.decode("latin-1"), V, f"{variant} round-trip ok, raw_size matches"
                        else:
                            # index does not add up (bytes cut, inserted or deleted): boundaries unproven
                            content, status, note = out.decode("latin-1"), U, "decodes, but the index does not tile the file"
                    else:
                        content, status, note = None, L, "blob does not round-trip or raw_size disagrees"
                except Exception as ex:
                    note = f"blob does not decode: {ex}"
            if status == L and e.ok:
                res.damage.append(DamageEntry(e.offset, e.end, DamageCause.UNKNOWN, f"entry {e.index}: {note}",
                                              [f"entry {e.index}"]))
            fields["content"] = Field("content", content, status, e.offset, e.size, note)
            res.records.append(Record(e.index, e.offset, fields))
        return res

    @staticmethod
    def _key_and_variant(data, ctx):
        names, blobs = [], []
        for s in (ctx.samples(data) if ctx else [data]):
            if len(s) < 6:
                continue
            sc = read_index(s, 6, int.from_bytes(s[4:6], "little"), PARC_ENTRY)
            if sc.damage:
                continue          # learn only from files whose index is fully consistent
            names += [bytes.fromhex(e.fields["name"].value) for e in sc.entries]
            blobs += [e.blob for e in sc.entries]
        key, _ = best_fixed_string_key(names)        # None unless it clearly wins
        variant, _ = best_variant(blobs)             # None unless one variant clearly wins
        return key, variant


# =================== scoring ===================

FIELDS = {"practice_rec": ("id", "name", "enrolled", "grade", "flags"),
          "practice_log": ("seq", "payload"),
          "practice_arc": ("name", "content")}


def truth_rows(ans: dict) -> list[dict]:
    rows = ans.get("records") or ans.get("entries") or []
    return rows


def score(practice_dir: Path, out_dir: Path) -> dict:
    manifests = {}
    for m in practice_dir.glob("*_damaged/manifest.json"):
        for item in json.loads(m.read_text()):
            manifests[f"{m.parent.name}/{item['file']}"] = item
    stats: dict = defaultdict(Counter)
    false_examples = []
    for out in sorted(out_dir.glob("*.json")):
        if out.name in ("report.json",):
            continue
        res = json.loads(out.read_text())
        fmt, src = res.get("format"), res.get("source_file", "")
        if src.endswith(".json"):
            continue                      # answers/ and manifest.json are not sample files
        folder = src.split("/")[0]
        kind = "damaged" if folder.endswith("_damaged") else "clean"
        base = folder.removesuffix("_damaged")
        orig = manifests[src]["source"] if kind == "damaged" else src.split("/")[-1]
        ans_path = practice_dir / base / "answers" / f"{orig}.json"
        if fmt not in FIELDS or not ans_path.exists():
            stats[(base, kind)]["files_not_decoded"] += 1
            continue
        truth = truth_rows(json.loads(ans_path.read_text()))
        st = stats[(base, kind)]
        st["files"] += 1
        names = FIELDS[fmt]
        for rec in res["records"]:
            got = {k: rec["fields"][k] for k in names if k in rec["fields"]}
            match = _match(fmt, rec, got, truth)
            for k, f in got.items():
                status = f["status"]
                if status == "lost" or f["value"] is None:
                    st["lost"] += 1
                    continue
                right = match is not None and match.get(k) == f["value"]
                if not right and status in ("verified", "corrected") and kind == "damaged" \
                        and _silent(fmt, k, f, manifests[src]):
                    st["silent"] += 1      # value changed in place, no checksum covers it
                    continue
                st[f"{status}_{'right' if right else 'wrong'}"] += 1
                if not right and status in ("verified", "corrected"):
                    false_examples.append(f"{src} record {rec['index']} {k}={f['value']!r}")
        st["truth_fields"] += len(truth) * len(names)
    return {"stats": stats, "false": false_examples}


# fields no checksum protects: an in-place change there cannot be detected by any tool
UNPROTECTED = {"practice_rec": set(FIELDS["practice_rec"]), "practice_arc": {"name", "content"},
               "practice_log": {"seq"}}


def _silent(fmt: str, name: str, f: dict, damage: dict) -> bool:
    """True when the damage only rewrote bytes inside this unprotected field (bit flip or
    zeroed bytes), leaving the file's structure intact."""
    if name not in UNPROTECTED.get(fmt, ()) or f.get("offset") is None or not f.get("length"):
        return False
    lo, hi = f["offset"], f["offset"] + f["length"]
    if damage["type"] == "bit_flip":
        return lo <= damage["byte"] < hi
    if damage["type"] == "zeroed":
        return damage["start"] < hi and lo < damage["end"]
    return False


def _match(fmt: str, rec: dict, got: dict, truth: list[dict]) -> dict | None:
    if fmt == "practice_rec":
        i = rec["index"]
        t = truth[i] if i < len(truth) else None
        return {**t, "id": t["id"]} if t else None
    if fmt == "practice_log":
        p = got.get("payload", {}).get("value")
        return next((t for t in truth if t["payload"] == p), None)
    if fmt == "practice_arc":
        n = got.get("name", {}).get("value")
        c = got.get("content", {}).get("value")
        return next((t for t in truth if t["name"] == n or t["content"] == c), None)
    return None


def print_table(result: dict) -> int:
    rows = sorted(result["stats"].items())
    print(f"{'format':<8} {'files':<8} {'files':>5} {'verified ok':>12} {'FALSE':>6} {'silent':>7} {'unverified':>11} {'lost':>6}  recall")
    total_false = 0
    for (base, kind), st in rows:
        good = st["verified_right"] + st["corrected_right"]
        false = st["verified_wrong"] + st["corrected_wrong"]
        total_false += false
        unv = st["unverified_right"] + st["unverified_wrong"]
        recall = good / st["truth_fields"] if st["truth_fields"] else 0
        print(f"{base:<8} {kind:<8} {st['files']:>5} {good:>12} {false:>6} {st['silent']:>7} {unv:>11} {st['lost']:>6}  {recall:6.1%}")
    print()
    print("verified ok = verified or corrected and right   FALSE = verified or corrected but wrong (must be 0)")
    print("silent = damage rewrote a value no checksum protects; no tool can detect it, so it is listed")
    print("         separately. recall = verified-ok fields / all true fields")
    print()
    if total_false:
        print(f"FALSE RECOVERIES: {total_false}  (verified/corrected but wrong; must be 0)")
        for ex in result["false"][:15]:
            print("   ", ex)
    else:
        print("FALSE RECOVERIES: 0  (nothing marked verified or corrected was wrong)")
    return 1 if total_false else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--practice", type=Path, default=ROOT / "practice")
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "rehearsal")
    a = ap.parse_args(argv)
    if not a.practice.is_dir():
        print(f"{a.practice} not found: run `python3 tools/practice.py --damaged` first")
        return 1
    cli.main([str(a.practice), str(a.out)])
    return print_table(score(a.practice, a.out))


if __name__ == "__main__":
    sys.exit(main())
