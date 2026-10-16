"""The corruption tool makes every damage type, including inserted and deleted bytes."""
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import corrupt  # noqa: E402

DATA = bytes(range(200))


def test_all_damage_types_present_and_correct():
    v = corrupt.variants(DATA, random.Random(3))
    types = {info["type"] for _, info in v.values()}
    assert types == {"truncate", "bit_flip", "zeroed", "inserted", "deleted"}
    for name, (blob, info) in v.items():
        if info["type"] == "inserted":
            assert len(blob) == len(DATA) + info["count"]
            assert blob[:info["offset"]] == DATA[:info["offset"]]
        if info["type"] == "deleted":
            assert len(blob) == len(DATA) - info["count"]
            assert blob == DATA[:info["offset"]] + DATA[info["offset"] + info["count"]:]


def test_cli_writes_manifest(tmp_path):
    src = tmp_path / "s.bin"
    src.write_bytes(DATA)
    out = tmp_path / "dmg"
    tool = Path(__file__).resolve().parents[1] / "tools" / "corrupt.py"
    subprocess.run([sys.executable, str(tool), str(src), "--out", str(out), "--seed", "1"], check=True)
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest) == 10 and all((out / m["file"]).is_file() for m in manifest)
