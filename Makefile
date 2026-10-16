.PHONY: test run spec practice docker docker-run clean

test:            ## run the test suite
	python3 -m pytest -q

run:             ## decode samples/ into out/
	./salvage samples out

spec:            ## regenerate FORMAT-SPEC.md from the spec library
	PYTHONPATH=src python3 -m salvage.output.formatspec > FORMAT-SPEC.md

practice:        ## made-up practice files (NOT the real formats) in practice/
	python3 tools/practice.py --damaged

docker:          ## build the image (offline once python:3.12-slim is pulled)
	docker build -t salvage .

docker-run:      ## run inside Docker with networking off
	mkdir -p out && docker run --rm --network none -v "$(PWD)/samples:/in:ro" -v "$(PWD)/out:/out" salvage /in /out

clean:
	rm -rf out practice .pytest_cache **/__pycache__
