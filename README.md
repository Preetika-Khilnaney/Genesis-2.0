# Genesis 2.0 · PS 02 — Legacy File Recovery

Team **Chargeman Ken** · Track EVA 03 · Problem statement ASCENSION 02

An offline tool that uses neuro-symbolic inference to decode undocumented legacy files, recover every verifiable record, and report any unrecoverable data.

## Build and run (one command each)

```sh
make docker                         # build the image (offline once python:3.12-slim is present)
make docker-run                     # samples/ -> out/, networking off (IN=real-samples for theirs)
```

Without Docker:

```sh
./salvage <input_dir> <output_dir>  # Python 3.11+, standard library only
make test                           # pip install -r requirements-dev.txt first
```

The tool always exits with code 0, including for empty, unknown or damaged files.

## What it writes to `output_dir`

| File | Contents |
| --- | --- |
| `<input>.json` | One per input: header and records, every field with a status |
| `report.json` | Run summary: format per file, status counts, damage byte ranges and causes, errors |
| `receipts.jsonl` | SHA-256 hash chain, one entry per input (tamper-evident audit trail) |

Field statuses: `verified` (backed by checksum / round-trip / evidence), `corrected` (provable single-bit fix), `unverified` (decoded, not proven), `lost` (no value, never guessed).

### Verifying Outputs & Audit Trail

```sh
# 1. Verify cryptographic hash chain on receipts.jsonl (returns True/False)
python3 -c "from salvage.output.receipts import verify_chain; from pathlib import Path; assert verify_chain(Path('out/receipts.jsonl')), 'Broken hash chain!'"

# 2. Strict JSON schema validation across all outputs and receipts
PYTHONPATH=src python3 -m salvage.output.schema_validate out

# 3. Full gate check (Docker offline build, run with --network none, schema validation)
make gate
```

## How it works

1. **Fingerprint** each file (magic bytes, structure checks, entropy).
2. **Decode** with the format's declarative spec (`FormatSpec`), bounds-checked.
3. **Verify**: checksum gate per block, round-trip re-encode, evidence check across samples.
4. **Recover**: damaged blocks are skipped and logged with byte ranges; parsing resyncs on the next valid block.
5. **Report**: JSON per file, `report.json`, receipts. Unknown files get an entropy map and strings, never invented records.

## Repo map

```
salvage                     CLI wrapper
src/salvage/cli.py          entry point (Preetika)
src/salvage/core/           shared interfaces: model, reader, spec, registry, fingerprint, simple decoder (Preetika)
src/salvage/formats/        one module per format (LIBRA-98: Preetika+Bhupesh; LABLOG, VAULT, game archive: Khushi; real-world: Bhupesh)
src/salvage/recovery/       CRC gate, resync, RLE, XOR (Khushi)
src/salvage/evidence/       candidate meanings, all-samples checker, FIELD-LOG ledger (Bhupesh)
src/salvage/output/         per-file JSON, report.json, unknown files, receipts, FORMAT-SPEC generator (Manas)
tools/hexview.py            hex / entropy / cross-sample diff helper for reverse engineering
tools/corrupt.py            make damaged copies of samples for testing
tools/log.py                append a hypothesis to FIELD-LOG.md
tests/                      pytest suite
FORMAT-SPEC.md              generated from the specs (`make spec`)
FIELD-LOG.md                dated log of every hypothesis, including failures
```

## Roadmap (beyond the hackathon build)

- MDL scoring and held-out e-values (accept a field at ≥ 20 : 1) in place of the all-samples rule
- Local Liquid LFM2 via llama.cpp as a propose-only layout generator (`--discover`)
- Full corruption lab with a calibrated abstain threshold

See `CONTRIBUTING.md` for ownership, branches and the rules every module follows.
