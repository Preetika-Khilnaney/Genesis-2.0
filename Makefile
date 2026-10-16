.PHONY: test run check false-recovery calibrate spec docker docker-run clean vendor build gate demo help

# ── Dev targets ───────────────────────────────────────────────────────────────

test:            ## run the full test suite (pytest + Hypothesis bounded profile)
	PYTHONPATH=src python3 -m pytest -q

run:             ## decode the organisers' samples (real-samples/samples) into out-real/
	./salvage real-samples/samples out-real

check:           ## run, then compare with real-samples/expected_outputs (exit 1 on any difference)
	python3 tools/check_expected.py

false-recovery:  ## flip bits in the real samples and measure wrong-but-verified records per format
	python3 tools/false_recovery.py

calibrate:       ## corruption lab: damage samples on purpose and measure risk rates
	PYTHONPATH=src python3 -m salvage.corruption_lab.calibrate

spec:            ## regenerate FORMAT-SPEC.md from the spec library
	PYTHONPATH=src python3 -m salvage.output.formatspec > FORMAT-SPEC.md

# ── Offline-build vendor cache ─────────────────────────────────────────────────

vendor:          ## (online, run once) download and build pinned wheels for both linux/amd64 and linux/arm64
	mkdir -p vendor/wheels
	docker run --rm --platform linux/amd64 \
	  -v "$$(pwd)/vendor/wheels:/wheels" \
	  -v "$$(pwd)/requirements.txt:/requirements.txt:ro" \
	  python:3.12-slim bash -c \
	  "apt-get update -qq && apt-get install -y -qq gcc python3-dev && pip wheel -r /requirements.txt -w /wheels"
	docker run --rm --platform linux/arm64 \
	  -v "$$(pwd)/vendor/wheels:/wheels" \
	  -v "$$(pwd)/requirements.txt:/requirements.txt:ro" \
	  python:3.12-slim bash -c \
	  "apt-get update -qq && apt-get install -y -qq gcc python3-dev && pip wheel -r /requirements.txt -w /wheels"

# ── Docker targets ─────────────────────────────────────────────────────────────

build:           ## build the image offline (vendor/wheels must exist; make vendor first)
	docker build --network=none -t salvage .

docker:          ## build the image (allows network; for CI / first-time setup)
	docker build -t salvage .

IN ?= real-samples/samples
docker-run:      ## run inside Docker with networking off (make docker-run IN=<folder>)
	mkdir -p out && docker run --rm --network none -v "$(PWD)/$(IN):/in:ro" -v "$(PWD)/out:/out" salvage /in /out

# ── Gate check ────────────────────────────────────────────────────────────────

gate:            ## run the full gate check (build + run + schema validate; exits non-zero on failure)
	bash tools/gate_check.sh

# ── Demo ──────────────────────────────────────────────────────────────────────

demo:            ## run the 3-4 minute scripted demo
	bash tools/demo.sh

# ── Housekeeping ───────────────────────────────────────────────────────────────

clean:
	rm -rf out out-real .pytest_cache **/__pycache__ .hypothesis demo_out

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'
