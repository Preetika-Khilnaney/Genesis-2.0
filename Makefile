.PHONY: test run run-real spec samples practice rehearse docker docker-run clean

test:            ## run the test suite
	python3 -m pytest -q

run:             ## decode samples/ (our demo data) into out/
	./salvage samples out

run-real:        ## decode real-samples/ (the organisers' files) into out-real/
	./salvage real-samples out-real

spec:            ## regenerate FORMAT-SPEC.md from the spec library
	PYTHONPATH=src python3 -m salvage.output.formatspec > FORMAT-SPEC.md

samples:         ## regenerate samples/ and sample-answers/ (same files every time)
	python3 tools/make_samples.py

practice:        ## made-up practice files (NOT the real formats) in practice/
	python3 tools/practice.py --damaged

rehearse:        ## run ./salvage on practice/ and score it against the answers
	python3 tools/rehearse.py

docker:          ## build the image (offline once python:3.12-slim is pulled)
	docker build -t salvage .

IN ?= samples
docker-run:      ## run inside Docker with networking off (make docker-run IN=real-samples)
	mkdir -p out && docker run --rm --network none -v "$(PWD)/$(IN):/in:ro" -v "$(PWD)/out:/out" salvage /in /out

clean:
	rm -rf out out-real practice .pytest_cache **/__pycache__
