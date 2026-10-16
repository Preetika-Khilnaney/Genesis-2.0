# Contributing (hackathon rules)

## Owners

| Person | Owns | Files |
| --- | --- | --- |
| Preetika | Core engine, CLI, shared interfaces, LIBRA-98, integration | `cli.py`, `core/`, `formats/libra98.py`, `formats/_common.py` |
| Khushi | Recovery: CRC gate, **single-bit correction**, resync, LABLOG, VAULT, game archives (WAD, PAK) | `recovery/`, `core/blocks.py` (with Preetika), `formats/lablog.py`, `formats/vault.py`, `formats/archives.py` |
| Bhupesh | Evidence: field meanings, checker, FIELD-LOG, **real-world formats** (WKS, WPD, BRAVO, CVT, EBCDIC-DUMP) | `evidence/`, `formats/wks.py`, `formats/documents.py`, `formats/cvt.py`, `formats/ebcdic.py`, `tools/field_evidence.py` |
| Manas | Delivery: OUTPUT-CONTRACT mapping, report.json, receipts, FORMAT-SPEC, tests, corruption tool, Docker, README | `output/` (incl. `contract.py`), `tests/`, `tools/check_expected.py`, `tools/false_recovery.py`, `tools/corrupt.py`, `Dockerfile` |

Single-bit correction lives in `recovery/crc.py` (`single_bit_fix`) and is applied by `core/blocks.py`.
Khushi owns its behaviour; Preetika only reviews changes to `core/blocks.py` because other formats use it.

## Shared interfaces (change only after telling the team)

- `core/model.py`: `FieldStatus`, `Field`, `Record`, `DamageEntry`, `FileResult`
- `core/spec.py`: `FieldSpec`, `FormatSpec`
- `core/registry.py`: `Decoder` + `@register` + `DecodeContext` (siblings of the same format)

- `core/blocks.py`: `BlockLayout`, `read_blocks`

These are already written and agreed at H0. Code against these and you never wait on anyone.

## How a format is written

A format is **data, not a parser**. Each `formats/*.py` file is:

1. a `FormatSpec` (magic, header fields, record fields, each with `desc` and `evidence`), and
2. a thin `Decoder.decode()` that calls the shared helpers: `core.simple.decode_simple` for
   header + records, or `core.blocks.read_blocks` for block formats, plus format-specific steps
   (RLE, XOR key, index table) from `recovery/`.

Nobody writes their own byte-reading loop or their own JSON. The interfaces above are fixed,
so all four of us can work in parallel from H0.

## Adding a format

1. Fill the module's `FormatSpec` (every field with `desc` and `evidence`).
2. Implement `decode(path, data, ctx)` (header + records formats can just call `core.simple.decode_simple`).
   `ctx.samples(data)` gives this file plus every other file of the same format, for the evidence check.
3. Set `ready = True`. Until then the fingerprinter ignores it.
   Files with a damaged magic are still matched: 1–2 wrong magic bytes (`near_magic`), or a header
   whose record count explains the file exactly (`structure_score`). Override `structure_score()` for
   block or index formats so damaged-header files of your format are still recognised.
4. Add a test, run `make test`, `make check` (7 of 7 must still match) and `make spec`.

## Shared helpers in core/

- `core/simple.py`: `decode_simple()` for header + repeated-record formats
- `core/gate.py`: `gate_records()` decides which `decode_simple` fields are VERIFIED (layout proven
  on all samples, file fits or record is before the damage, exact round trip, per-field checks).
  Never mark a field verified on round trip alone: without a checksum, damage round-trips too.
- `core/blocks.py`: `read_blocks()` for marker / length / payload / checksum formats (CRC gate,
  single-bit fix, resync, truncation, damage entries all handled)
- `core/index.py`: `read_index()` for index-table formats (VAULT, game archives): blobs past the
  end, offsets into the header, overlaps and gaps all reported; `index_structure_score()` for the
  damaged-header fallback

## Tools

- `tools/survey.py <folder>`: compares all samples of one format and prints only what holds in
  every file: magic, constant bytes, size fields, `header + N x record` layouts, record columns
  (ids, text, dates) and a draft `FormatSpec`. Add `--log --by <name>` to write its findings to
  FIELD-LOG. Start every new format with it.
- **Real samples** are the organisers' participant kit in `real-samples/` (committed: `samples/`,
  `expected_outputs/`, `OUTPUT-CONTRACT.md`, `HINTS.md`). `make check` runs the tool on them and
  compares with the expected outputs; it must stay at 7 of 7. `make false-recovery` flips bits in
  them and counts wrong-but-verified records; it must not get worse.
- `tools/field_evidence.py`: every format hypothesis as a test on the real samples. Add a row there
  (accepted or rejected) whenever you learn something about a format, then run it to log it.
- `tools/survey.py` tolerates damaged files: it analyses the files most of them agree on and lists
  the rest as likely damaged.
- `tools/hexview.py <file>`: hex + ASCII view with offsets
- `tools/corrupt.py <file> --out <dir>`: damaged copies + `manifest.json`
- `tools/log.py`: add a FIELD-LOG row

## Rules every module follows

- **Output only through `output/contract.py`** (OUTPUT-CONTRACT.md). Decoders fill `FileResult`
  (`metadata`, records with `values` / `verified` / `issues`, `DamageEntry` with `lossy`).
- **Never invent data.** Unproven = `verified: false`. Unreadable = field `None`, never a guess.
- **Never crash.** Use `ByteReader` (bounds-checked). Turn `OutOfBounds` into a `DamageEntry`.
- **Verified needs evidence:** checksum pass, round-trip match, or an accepted checker verdict.
- **Log every hypothesis from H1**, including failures, as you go. Everyone logs, not only Bhupesh:
  `python3 tools/log.py <format> "<hypothesis>" "<evidence>" accepted|rejected|open --by <name>`
  Bhupesh reviews FIELD-LOG.md at the end; he does not write other people's entries.
- **How a field is accepted today:** the all-samples rule in `evidence/checker.py`. A guess is
  accepted only if it holds on every sample (at least 2); one counterexample rejects it.
  MDL scoring and e-values at 20:1 are the design for the next version, not today's build,
  so do not claim them in the demo as implemented.
- **No network, no new runtime dependencies** (standard library only).
- **Deterministic output.** Seed anything random.

## Git workflow

- Branch per task: `preetika/libra98`, `khushi/lablog-crc`, `bhupesh/checker`, `manas/report`.
- Small PRs into `main`; `make test` must pass (CI runs it).
- Pull `main` before you start and before you open a PR.
- **Game archives**: both WAD (s23) and PAK (s24) are decoded (`formats/archives.py`).
- **Hour 8 checkpoint:** LIBRA-98 passes through the CLI in Docker, or everyone helps until it does.
- Cut order if behind: receipts, real-world format, game archive. Never cut LABLOG, damage reports or the logs.
