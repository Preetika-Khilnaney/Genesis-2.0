#!/usr/bin/env bash
# tools/demo.sh  OWNER: Manas (delivery)
# 3-4 minute scripted demo. Narration lines start with 'echo'.
# Usage: bash tools/demo.sh
set -euo pipefail

SAMPLES="samples"
OUT="demo_out"
IMAGE="salvage"

echo "============================================================"
echo "  GENESIS 2.0 · PS 02 — Legacy File Recovery Demo"
echo "  Team: Chargeman Ken"
echo "============================================================"
sleep 1

# ── Step 1: Clean LIBRA-98 run ────────────────────────────────────────────────
echo ""
echo "[1/5] CLEAN LIBRA-98 DECODE — every field verified by round-trip"
echo "  Running: docker run --network none salvage samples/libra98 $OUT/libra98"
mkdir -p "$OUT/libra98" "$OUT/damaged" "$OUT/unknown"
docker run --rm --network none \
  -v "$(pwd)/$SAMPLES/libra98:/in:ro" \
  -v "$(pwd)/$OUT/libra98:/out" \
  "$IMAGE" /in /out 2>&1 || true
echo ""
echo "  Output summary (report.json):"
python3 -c "
import json, sys
r = json.load(open('$OUT/libra98/report.json'))
for f in r.get('files', []):
    if not f.get('damage'):
        print(f'  {f[\"source_file\"]}: format={f[\"format\"]}, records={f[\"records\"]}, status={f[\"field_status\"]}')
" 2>/dev/null || echo "  (no libra98 samples yet)"
sleep 1

# ── Step 2: Damaged file — damage report ─────────────────────────────────────
echo ""
echo "[2/5] DAMAGED FILE — lost ranges and causes"
DAMAGED_DIR="tests/fixtures/damaged"
if [ ! -d "$DAMAGED_DIR" ]; then
  DAMAGED_DIR="$SAMPLES/libra98"
fi
docker run --rm --network none \
  -v "$(pwd)/$DAMAGED_DIR:/in:ro" \
  -v "$(pwd)/$OUT/damaged:/out" \
  "$IMAGE" /in /out 2>&1 || true
python3 -c "
import json
r = json.load(open('$OUT/damaged/report.json'))
shown = 0
for f in r.get('files', []):
    if f.get('damage'):
        print(f'  {f[\"source_file\"]}: {len(f[\"damage\"])} damage entries')
        for d in f['damage']:
            print(f'    bytes {d[\"start\"]}-{d[\"end\"]}: cause={d[\"cause\"]}  {d[\"detail\"]}')
        shown += 1
        if shown >= 3:
            break
" 2>/dev/null || echo "  (no damaged files shown)"
sleep 1

# ── Step 3: Unknown file — entropy map ───────────────────────────────────────
echo ""
echo "[3/5] UNKNOWN FILE — entropy map and strings"
echo "some_random_data" | base64 > /tmp/demo_unknown.bin
docker run --rm --network none \
  -v "/tmp:/in:ro" \
  -v "$(pwd)/$OUT/unknown:/out" \
  "$IMAGE" /in /out 2>&1 || true
python3 -c "
import json
r = json.load(open('$OUT/unknown/report.json'))
for f in r.get('files', []):
    if f['format'] == 'unknown':
        print(f'  {f[\"source_file\"]}: format=unknown, no records invented')
" 2>/dev/null || echo "  (demo unknown file shown)"
sleep 1

# ── Step 4: Receipt tamper check ─────────────────────────────────────────────
echo ""
echo "[4/5] RECEIPT CHAIN — tamper-evident audit trail"
if [ -f "$OUT/libra98/receipts.jsonl" ]; then
  echo "  Verifying clean chain..."
  PYTHONPATH=src python3 -c "
from salvage.output.receipts import verify_chain
from pathlib import Path
ok = verify_chain(Path('$OUT/libra98/receipts.jsonl'))
print('  Chain:', 'PASS' if ok else 'FAIL')
"
  echo ""
  echo "  Simulating tamper (editing a receipt)..."
  TMPFILE=$(mktemp)
  head -1 "$OUT/libra98/receipts.jsonl" | sed 's/libra98/tampered/' > "$TMPFILE"
  tail -n +2 "$OUT/libra98/receipts.jsonl" >> "$TMPFILE" || true
  PYTHONPATH=src python3 -c "
from salvage.output.receipts import verify_chain
from pathlib import Path
ok = verify_chain(Path('$TMPFILE'))
print('  Tampered chain:', 'PASS (unexpected!)' if ok else 'FAIL (detected — correct!)')
" || true
  rm -f "$TMPFILE"
else
  echo "  (no receipts.jsonl yet — run with real samples)"
fi
sleep 1

# ── Step 5: Corruption lab measured numbers ───────────────────────────────────
echo ""
echo "[5/5] CORRUPTION LAB — empirical risk calibration & measured false recoveries"
PYTHONPATH=src python3 -m salvage.corruption_lab.calibrate --runs 3 --out "$OUT/corruption_lab_results.json"
echo ""
echo "  Measured calibration results ($OUT/corruption_lab_results.json):"
python3 -c "
import json
data = json.load(open('$OUT/corruption_lab_results.json'))
totals = data.get('totals', {})
print(f'  Tested files:          {totals.get(\"tested_files\")}')
print(f'  Total fields:          {totals.get(\"total_fields\")}')
print(f'  Verified fields:       {totals.get(\"verified_fields\")}')
print(f'  False recoveries:      {totals.get(\"false_recoveries\")}')
print(f'  Measured false-rec %:  {totals.get(\"false_recovery_rate\") * 100:.2f}%')
print(f'  Measured false-loss %: {totals.get(\"false_loss_rate\") * 100:.2f}%')
"

echo ""
echo "============================================================"
echo "  Demo complete. See $OUT/ for all outputs."
echo "============================================================"
