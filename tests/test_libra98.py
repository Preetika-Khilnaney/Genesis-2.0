"""LIBRA-98 on samples/libra98 (STAND-IN layout) scored against sample-answers/libra98.

Clean files: every field verified and right. Damaged copies: nothing verified may be wrong,
except values rewritten in place where no checksum could notice (bit flip / zeroed inside
that very field). When the real samples arrive, keep this test and point it at the new spec."""
import json
from pathlib import Path

from salvage.cli import main

ROOT = Path(__file__).parent.parent
ANS = ROOT / "sample-answers" / "libra98"
FIELDS = ("id", "name", "enrolled", "grade", "flags")


def _silent(f: dict, d: dict) -> bool:
    lo, hi = f["offset"], f["offset"] + f["length"]
    return (d["type"] == "bit_flip" and lo <= d["byte"] < hi) or \
        (d["type"] == "zeroed" and d["start"] < hi and lo < d["end"])


def test_libra98_samples_match_answers(tmp_path):
    out = tmp_path / "out"
    assert main([str(ROOT / "samples" / "libra98"), str(out)]) == 0
    damaged = {m["file"]: m for m in json.loads((ANS / "manifest.json").read_text())}
    clean_ok = clean_total = false = 0
    for res_path in sorted(out.glob("*.json")):
        if res_path.name == "report.json":
            continue
        res = json.loads(res_path.read_text())
        name = res["source_file"]
        if res["format"] == "unknown":
            # only acceptable when the damage destroyed the magic itself: never guess the format
            d = damaged.get(name, {})
            assert d.get("offset", d.get("start", d.get("byte", 99))) < 8, name
            continue
        assert res["format"] == "libra98", name
        truth = json.loads((ANS / f"{damaged[name]['source'] if name in damaged else name}.json").read_text())
        rows = truth["records"]
        if name not in damaged:
            assert res["header"]["record_count"]["status"] == "verified"
            assert res["header"]["decoy_15"]["status"] == "unverified"     # looks like a length, is not
            assert not res["damage"]
        for rec in res["records"]:
            t = rows[rec["index"]] if rec["index"] < len(rows) else None
            for k in FIELDS:
                f = rec["fields"][k]
                right = t is not None and t[k] == f["value"]
                if name not in damaged:
                    clean_total += 1
                    clean_ok += right and f["status"] == "verified"
                elif f["status"] == "verified" and not right and not _silent(f, damaged[name]):
                    false += 1
        if name in damaged and damaged[name]["type"] in ("truncate", "inserted", "deleted"):
            assert res["damage"], f"{name}: structural damage must be reported"
    assert clean_total and clean_ok == clean_total
    assert false == 0
