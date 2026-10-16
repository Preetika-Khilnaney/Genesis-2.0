.PHONY: test run run-real spec samples practice rehearse docker docker-run clean vendor build gate demo help

# ── Dev targets ───────────────────────────────────────────────────────────────

test:            ## run the full test suite (pytest + Hypothesis bounded profile)
	PYTHONPATH=src .venv/bin/python -m pytest -q

run:             ## decode samples/ (our demo data) into out/
	PYTHONPATH=src ./salvage samples out

run-real:        ## decode real-samples/ (the organisers' files) into out-real/
	PYTHONPATH=src ./salvage real-samples out-real

spec:            ## regenerate FORMAT-SPEC.md from the spec library
	PYTHONPATH=src python3 -m salvage.output.formatspec > FORMAT-SPEC.md

samples:         ## regenerate samples/ and sample-answers/ (same files every time)
	python3 tools/make_samples.py

practice:        ## made-up practice files (NOT the real formats) in practice/
	python3 tools/practice.py --damaged

rehearse:        ## run ./salvage on practice/ and score it against the answers
	python3 tools/rehearse.py

# ── Offline-build vendor cache ─────────────────────────────────────────────────

vendor:          ## (online, run once) download and build pinned wheels for linux/arm64
	mkdir -p vendor/wheels
	docker run --rm \
	  -v "$$(pwd)/vendor/wheels:/wheels" \
	  -v "$$(pwd)/requirements.txt:/requirements.txt:ro" \
	  python:3.12-slim bash -c \
	  "apt-get update -qq && apt-get install -y -qq gcc python3-dev && pip wheel -r /requirements.txt -w /wheels"

# ── Docker targets ─────────────────────────────────────────────────────────────

build:           ## build the image offline (vendor/wheels must exist; make vendor first)
	docker build --network=none -t salvage .

docker:          ## build the image (allows network; for CI / first-time setup)
	docker build -t salvage .

IN ?= samples
docker-run:      ## run inside Docker with networking off (make docker-run IN=real-samples)
	mkdir -p out && docker run --rm --network none -v "$(PWD)/$(IN):/in:ro" -v "$(PWD)/out:/out" salvage /in /out

# ── Gate check ────────────────────────────────────────────────────────────────

gate:            ## run the full gate check (build + run + schema validate; exits non-zero on failure)
	bash tools/gate_check.sh

# ── Demo ──────────────────────────────────────────────────────────────────────

demo:            ## run the 3-4 minute scripted demo
	bash tools/demo.sh

# ── Housekeeping ───────────────────────────────────────────────────────────────

clean:
	rm -rf out out-real practice .pytest_cache **/__pycache__ .hypothesis demo_out

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'
