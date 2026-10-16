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
from salvage.core.simple import decode_simple  # noqa: E402
from salvage.core.spec import FieldSpec, FormatSpec, decode_fields  # noqa: E402
from salvage.evidence.checker import evaluate  # noqa: E402
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
PREC_HEADER, PREC_RECORD = 20, 30


def _layout_holds(b: bytes) -> bool:
    return len(b) >= 11 and PREC_HEADER + int.from_bytes(b[9:11], "little") * PREC_RECORD == len(b)


@register
class PracticeRec(Decoder):
    """LIBRA-98 style. A record field is VERIFIED only when all three hold:
    1. the layout is proven across samples (all-samples rule), and THIS file fits it exactly;
    2. the record round-trips byte for byte;
    3. the value is plausible (ids count up by 1, real dates, printable names, zero padding).
    No checksum here, so anything else stays UNVERIFIED: we cannot prove it."""
    name, spec, ready = "practice_rec", PREC_SPEC, True

    def decode(self, path, data, ctx: DecodeContext | None = None) -> FileResult:
        res = decode_simple(self.spec, path, data)
        samples = ctx.samples(data) if ctx else [data]
        # judge the layout on clean-looking siblings; this file is checked on its own below
        layout = evaluate(self.name, "header 20 + record_count * 30 == file size", samples, _layout_holds,
                          log=False)
        fits = _layout_holds(data)
        if not fits:
            res.warnings.append("file size does not match header + count * 30: bytes inserted, deleted or cut")
            # if the count is believable but the file is short, decode_simple already logged TRUNCATED
            if not any(d.cause == DamageCause.TRUNCATED for d in res.damage):
                res.damage.append(DamageEntry(PREC_HEADER, len(data), DamageCause.BAD_LENGTH,
                                              "file size disagrees with record count; record boundaries "
                                              "cannot be trusted", ["all records"]))
        proven = layout.held >= 2 and fits
        for name in ("decoy", "reserved"):
            if name in res.header:
                res.header[name].status, res.header[name].note = U, "meaning unknown (looks like a length, is not)"
        if "record_count" in res.header and not proven:
            res.header["record_count"].status = U
        # first pass: which records look intact (round-trip + every field plausible)?
        intact_flags, prev_id = [], None
        for rec in res.records:
            raw = data[rec.offset:rec.offset + PREC_RECORD]
            rt = len(raw) == PREC_RECORD and bool(rec.fields) and all(f.note == "round-trip ok" for f in rec.fields.values())
            fv = {k: f.value for k, f in rec.fields.items()}
            ok = rt and _rec_plausible(fv, prev_id)
            intact_flags.append(ok)
            prev_id = fv.get("id")
        first_bad = next((i for i, ok in enumerate(intact_flags) if not ok), len(intact_flags))
        # Damage can sit inside the last record that still looks fine (only the NEXT record shows
        # the shift), so when the file size is off, trust records only up to first_bad - 1.
        prefix_end = first_bad - 1 if first_bad < len(intact_flags) or not fits else first_bad
        prev_id = None
        intact = True     # still before the first sign of damage in this file
        for rec in res.records:
            raw = data[rec.offset:rec.offset + PREC_RECORD]
            ok_rt = len(raw) == PREC_RECORD and rec.fields and all(f.note == "round-trip ok" for f in rec.fields.values())
            id_ok = prev_id is None or rec.fields["id"].value == prev_id + 1
            checks = {}
            for f in rec.fields.values():
                checks[f.name] = {
                    "id": id_ok,
                    "name": f.value.isprintable() and f.value.strip() != "" if isinstance(f.value, str) else False,
                    "enrolled": _date_ok(f.value),
                    "grade": 0 <= f.value <= 100 if isinstance(f.value, int) else False,
                    "flags": f.value in (0, 1, 2, 3) if isinstance(f.value, int) else False,
                    "pad": f.value == "0000",
                }[f.name]
            # damage is local: one implausible field makes the whole record suspect
            record_ok = all(checks.values())
            intact = intact and record_ok and ok_rt
            # file size is off (bytes cut/inserted/deleted): records before the first bad one
            # are still at their true offsets, because damage only shifts what comes after it
            prefix_ok = not fits and layout.held >= 2 and intact and rec.index < prefix_end
            for f in rec.fields.values():
                plausible = record_ok
                if (proven or prefix_ok) and ok_rt and plausible:
                    f.status, f.note = V, ("layout proven on all samples, round-trip ok, plausible" if proven else
                                           "before the first damaged record; round-trip ok, plausible")
                else:
                    f.status = U
                    f.note = "not proven: " + ", ".join(w for w, bad in (
                        ("layout", not proven), ("round-trip", not ok_rt), ("implausible value", not plausible)) if bad)
            prev_id = rec.fields["id"].value if "id" in rec.fields else None
        return res


def _rec_plausible(v: dict, prev_id) -> bool:
    try:
        return ((prev_id is None or v["id"] == prev_id + 1) and v["name"].isprintable() and v["name"].strip() != ""
                and _date_ok(v["enrolled"]) and 0 <= v["grade"] <= 100 and v["flags"] in (0, 1, 2, 3)
                and v["pad"] == "0000")
    except Exception:
        return False


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
