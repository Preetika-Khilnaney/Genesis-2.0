# Dockerfile for the salvage tool.
# Builds fully offline once the base image + wheels are cached.
#
# One-time online setup:  make vendor          (downloads wheels to vendor/wheels/)
# Offline build:          make build            (docker build with --network none)
# Run offline:            make docker-run
#
# Build args:
#   WITH_LFM2=0    placeholder — LFM2 model is excluded from the default image

FROM python:3.12-slim

ARG WITH_LFM2=0

WORKDIR /app

# Install pinned wheels from the vendor cache; no network access needed.
COPY requirements.txt ./
COPY vendor/wheels/ ./vendor/wheels/
# The tool runs on the Python standard library alone (numpy/jsonschema are optional).
# Install vendored runtime extras only if vendor/wheels has wheels; never pytest/hypothesis.
RUN if ls vendor/wheels/*.whl >/dev/null 2>&1; then \
        grep -vE '^(hypothesis|pytest)==' requirements.txt > /tmp/runtime.txt && \
        pip install --no-index --find-links=vendor/wheels --no-cache-dir -r /tmp/runtime.txt; \
    else \
        echo "vendor/wheels is empty: standard library only"; \
    fi

# Copy source
COPY salvage ./salvage
COPY src/ ./src/
COPY schema/ ./schema/
COPY templates/ ./templates/

RUN chmod +x /app/salvage

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/app/salvage"]
