#!/usr/bin/env bash
# tools/demo.sh  OWNER: Manas (delivery)
# 3-4 minute scripted demo on the organisers' real samples.
# Usage: bash tools/demo.sh            (uses Docker with networking off if the image exists)
#        DOCKER=0 bash tools/demo.sh   (runs ./salvage directly)
set -uo pipefail

SAMPLES="real-samples/samples"
OUT="demo_out"
IMAGE="salvage"
rm -rf "$OUT"; mkdir -p "$OUT"

say() { echo ""; echo "$@"; }
show() { PYTHONPATH=src python3 -c "$1"; }

echo "============================================================"
echo "  GENESIS 2.0 · PS 02 — Salvage · Team Chargeman Ken"
echo "============================================================"

say "[1/5] ONE COMMAND, OFFLINE: 30 legacy files, 10 formats, plus hostile files"
if [ "${DOCKER:-1}" = "1" ] && docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "  docker run --network none salvage $SAMPLES $OUT"
  docker run --rm --network none -v "$(pwd)/$SAMPLES:/in:ro" -v "$(pwd)/$OUT:/out" "$IMAGE" /in /out
else
  echo "  ./salvage $SAMPLES $OUT"
  ./salvage "$SAMPLES" "$OUT"
fi
echo "  exit code: $?"
show "
import json
r = json.load(open('$OUT/report.json'))
for f in r['files']:
    print(f\"  {f['file']:22} {f['format']:12} {f['status']:13} records={f['records']:<3} damage={f['damage']}\")
print('  totals:', r['totals'])"

say "[2/5] MATCHES THE ORGANISERS' EXPECTED OUTPUTS"
python3 tools/check_expected.py --out "$OUT" | tail -1

say "[3/5] DAMAGE IS REPORTED, NEVER HIDDEN (s04: library file cut off mid-record)"
show "
import json
d = json.load(open('$OUT/s04.dat.json'))
print('  status:', d['status'])
for x in d['damage']: print(f\"  damage: {x['kind']} at byte {x['offset']} lossy={x['lossy']}: {x['detail']}\")
print('  last record:', d['records'][-1])"

say "[4/5] PROVEN REPAIR (s07 lab log, s10 vault): exactly one flipped bit explains the CRC failure"
show "
import json
for f in ('s07.dat', 's10.dat'):
    d = json.load(open('$OUT/' + f + '.json'))
    for x in d['damage']: print(f\"  {f}: {x['kind']} lossy={x['lossy']}: {x['detail']}\")"

say "[5/5] HOSTILE FILES DO NOT CRASH IT, AND NOTHING IS INVENTED"
show "
import json
for f in ('s25_random.bin', 's26_empty.dat', 's27_notes.txt', 's28_tiny.dat', 's29_almost_libra.dat', 's30_png_like.dat'):
    d = json.load(open('$OUT/' + f + '.json'))
    print(f\"  {f:22} {d['status']:13} records={len(d['records'])}  {d['metadata'].get('looks_like', '')}\")"

if [ -f "$OUT/receipts.jsonl" ]; then
  say "BONUS: tamper-evident receipts"
  show "
from pathlib import Path
from salvage.output.receipts import verify_chain
p = Path('$OUT/receipts.jsonl')
print('  receipt chain:', 'PASS' if verify_chain(p) else 'FAIL')
t = Path('$OUT/receipts.tampered.jsonl')
t.write_text(p.read_text().replace('LIBRA-98', 'LIBRA-99', 1))
print('  after editing one receipt:', 'PASS (unexpected!)' if verify_chain(t) else 'FAIL (tampering detected)')"
fi

echo ""
echo "============================================================"
echo "  Demo complete. Outputs in $OUT/"
echo "============================================================"
