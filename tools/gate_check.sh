#!/usr/bin/env bash
# tools/gate_check.sh  OWNER: Manas (delivery)
# Gate check for the LIBRA-98 milestone (H8):
#   1. Build the Docker image (network allowed here; use `make build` for offline-only)
#   2. Run with --network none on the sample dir
#   3. Schema-validate all outputs
#   4. Verify exit code 0
#   5. Verify report.json exists and is parseable
#   6. Exit non-zero on any failure
#
# Usage: bash tools/gate_check.sh [input_dir] [output_dir]
# Defaults: samples/, out/

set -euo pipefail

INPUT_DIR="${1:-samples}"
OUTPUT_DIR="${2:-out}"
IMAGE="salvage"

echo "=== GATE CHECK ==="
echo "  image:      $IMAGE"
echo "  input_dir:  $INPUT_DIR"
echo "  output_dir: $OUTPUT_DIR"
echo ""

# 1. Build the image (network allowed — gate runs while online during CI)
echo "[1/5] Building Docker image..."
docker build -t "$IMAGE" . 2>&1 | tail -5
echo "      OK"

# 2. Run with --network none
echo "[2/5] Running with --network none..."
mkdir -p "$OUTPUT_DIR"
docker run --rm --network none \
  -v "$(pwd)/$INPUT_DIR:/in:ro" \
  -v "$(pwd)/$OUTPUT_DIR:/out" \
  "$IMAGE" /in /out
EXIT=$?
if [ "$EXIT" -ne 0 ]; then
  echo "GATE FAIL: exit code $EXIT (must be 0)"
  exit 1
fi
echo "      exit code 0 OK"

# 3. report.json must exist and be valid JSON
echo "[3/5] Checking report.json..."
if ! python3 -c "import json; json.load(open('$OUTPUT_DIR/report.json'))" 2>&1; then
  echo "GATE FAIL: report.json missing or invalid"
  exit 1
fi
echo "      OK"

# 4. Schema validation
echo "[4/5] Schema validation..."
if ! PYTHONPATH=src python3 -m salvage.output.schema_validate "$OUTPUT_DIR"; then
  echo "GATE FAIL: schema errors"
  exit 1
fi

# 5. receipts.jsonl must exist and form a valid hash chain
echo "[5/5] Checking receipts.jsonl & hash chain..."
if [ ! -f "$OUTPUT_DIR/receipts.jsonl" ]; then
  echo "GATE FAIL: receipts.jsonl missing"
  exit 1
fi
if ! PYTHONPATH=src python3 -c "from salvage.output.receipts import verify_chain; from pathlib import Path; assert verify_chain(Path('$OUTPUT_DIR/receipts.jsonl'))"; then
  echo "GATE FAIL: receipts.jsonl hash chain broken"
  exit 1
fi
echo "      OK"

echo ""
echo "=== GATE CHECK PASSED ==="
