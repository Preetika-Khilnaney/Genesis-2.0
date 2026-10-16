# Builds fully offline once the base image is present: the runtime uses the Python
# standard library only, so there is no pip install step.
#   docker build -t salvage .
#   docker run --rm --network none -v "$PWD/samples:/in:ro" -v "$PWD/out:/out" salvage /in /out
FROM python:3.12-slim
WORKDIR /app
COPY salvage ./salvage
COPY src ./src
RUN chmod +x /app/salvage
ENTRYPOINT ["/app/salvage"]
