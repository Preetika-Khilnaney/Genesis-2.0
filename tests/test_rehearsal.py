"""End-to-end rehearsal: practice files -> ./salvage -> score. Nothing verified may be wrong.

Runs in a subprocess so the practice decoders never register inside the test session."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_rehearsal_has_no_false_recoveries(tmp_path):
    p, o = tmp_path / "practice", tmp_path / "out"
    subprocess.run([sys.executable, str(ROOT / "tools" / "practice.py"), "--damaged", "--count", "4",
                    "--seed", "7", "--out", str(p)], check=True, capture_output=True)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "rehearse.py"), "--practice", str(p), "--out", str(o)],
                       capture_output=True, text=True)
    assert "FALSE RECOVERIES: 0" in r.stdout, r.stdout[-2000:]
    clean = [line for line in r.stdout.splitlines() if " clean " in line]
    assert len(clean) == 3 and all(line.rstrip().endswith("100.0%") for line in clean), r.stdout
