# schema/

Drop the organisers' published JSON schema here as `output.schema.json`.
`src/salvage/output/writer.py::to_schema()` is the only place that maps our
internal result to it.
