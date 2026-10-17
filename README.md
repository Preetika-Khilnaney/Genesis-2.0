# Genesis 2.0 · PS 02 — Legacy File Recovery

Team **Chargeman Ken** · Track EVA 03 · Problem statement ASCENSION 02

An offline tool that uses neuro-symbolic inference to decode undocumented legacy files, recover every verifiable record, and report any unrecoverable data.

## Build and run (one command each)

```sh
make docker                         # build the image (offline once python:3.12-slim is present)
make docker-run                     # real-samples/samples -> out/, networking off (IN=<folder> for others)
```

Without Docker:

```sh
./salvage <input_dir> <output_dir>  # Python 3.11+, standard library only, no network, no AI calls
make test                           # pip install -r requirements-dev.txt first
make check                          # decode the organisers' samples and compare with their expected outputs
```

It reads every file directly in `input_dir` (sub-directories are skipped) and always exits 0,
including for empty, unknown, damaged or hostile files.

## Results on the organisers' kit (`real-samples/`)

| | |
| --- | --- |
| Expected outputs matched | **7 of 7** (`make check`) |
| Files handled | 30 of 30: 10 formats + 6 hostile files; `nested/` skipped as the contract requires |
| Proven repairs | s07 (LABLOG) and s10 (VAULT): exactly one flipped bit explains each CRC failure |
| Crashes on 25,000 damaged / random variants | 0 |
| False recoveries (wrong but verified) on random bit flips | LABLOG 0%, LIBRA-98 0.1%, VAULT 3%, EBCDIC 7% (`make false-recovery`) |

Formats without any checksum (WKS, WPD, BRAVO, CVT, WAD, PAK) are verified by structure only, so
a bit flipped inside a value there cannot be detected by any tool; `make false-recovery` shows it.

## What it writes to `output_dir` (real-samples/OUTPUT-CONTRACT.md)

| File | Contents |
| --- | --- |
| `<input name>.json` | `source_file`, `format`, `status`, `metadata`, `records`, `damage` |
| `report.json` | `tool_version`, one line per file (format, status, records, damage), `totals` per status |
| `receipts.jsonl` | SHA-256 hash chain, one entry per input (tamper-evident) |

### Verifying outputs and the audit trail

```sh
# 1. Verify the SHA-256 hash chain in receipts.jsonl
python3 -c "from salvage.output.receipts import verify_chain; from pathlib import Path; assert verify_chain(Path('out/receipts.jsonl')), 'Broken hash chain!'"

# 2. JSON schema validation of every output against the contract schemas in schema/
PYTHONPATH=src python3 -m salvage.output.schema_validate out

# 3. Full gate check (Docker offline build, run with --network none, schema validation)
make gate
```

`status`: `ok` (nothing lost), `partial` (some data lost or unverified), `unsupported` (recognised,
e.g. encrypted), `unrecognized`, `failed` (recognised but unreadable). A record that could not be
verified carries `"verified": false` and `"issues"`; damage uses the contract vocabulary
(`truncated`, `crc_mismatch`, `checksum_mismatch`, ...), with `"lossy": false` for damage that was
found and repaired with proof.

## Formats

| Format | How a record is verified |
| --- | --- |
| LIBRA-98 | per-record sum-8 checksum + file sum-16 trailer |
| LABLOG | CRC-16/CCITT-FALSE per block and on the header; provable single-bit repair |
| VAULT | CRC-32 of each decoded blob; XOR (key+i) and RLE90 undone; provable single-bit repair |
| EBCDIC-DUMP | packed-decimal validity + trailer count and credits total cross-check |
| WKS, WPD, BRAVO, CVT, WAD, PAK | structure (lengths tile the file, pointers in bounds, declared counts) |

Layouts are in `FORMAT-SPEC.md`; every hypothesis we tried, including the rejected ones, is in
`FIELD-LOG.md` and can be re-checked with `python3 tools/field_evidence.py`.

## Repo map

```
salvage                     CLI wrapper
src/salvage/cli.py          entry point (Preetika)
src/salvage/core/           shared interfaces: model, reader, spec, registry, fingerprint, helpers (Preetika)
src/salvage/formats/        one module per format: libra98, lablog, vault, wks, documents (WPD, BRAVO),
                            cvt, ebcdic, archives (WAD, PAK)
src/salvage/recovery/       CRC gate, resync, RLE, XOR (Khushi)
src/salvage/evidence/       candidate meanings, all-samples checker, FIELD-LOG ledger (Bhupesh)
src/salvage/output/         contract.py (the OUTPUT-CONTRACT mapping), per-file JSON, report.json, unknown
                            files, receipts, FORMAT-SPEC generator (Manas)
real-samples/               the organisers' participant kit: samples/, expected_outputs/, OUTPUT-CONTRACT.md
tools/check_expected.py     compare output with the expected outputs (make check)
tools/false_recovery.py     flip bits in real samples, count wrong-but-verified records (make false-recovery)
tools/field_evidence.py     re-test every format hypothesis on the real samples, write FIELD-LOG.md
tools/survey.py             propose a layout from a folder of samples of one format
tools/hexview.py            hex / entropy / cross-sample diff helper for reverse engineering
tools/corrupt.py            make damaged copies of samples for testing
tools/log.py                append a hypothesis to FIELD-LOG.md
tests/                      pytest suite
FORMAT-SPEC.md              generated from the specs (`make spec`)
FIELD-LOG.md                dated log of every hypothesis, including failures
```

## Roadmap (beyond the hackathon build)

- MDL scoring and held-out e-values (accept a field at ≥ 20 : 1) in place of the all-samples rule
- Local Liquid LFM2 via llama.cpp as a propose-only layout generator, development only (the rules
  forbid AI calls at runtime, so it never runs inside `./salvage`)
- Full corruption lab with a calibrated abstain threshold

See `CONTRIBUTING.md` for ownership, branches and the rules every module follows.
