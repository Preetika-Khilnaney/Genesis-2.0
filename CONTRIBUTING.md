# Contributing (hackathon rules)

## Owners

| Person | Owns | Files |
| --- | --- | --- |
| Preetika | Core engine, CLI, shared interfaces, LIBRA-98, integration | `cli.py`, `core/`, `formats/libra98.py` |
| Khushi | Recovery: CRC gate, **single-bit correction**, resync, LABLOG, VAULT, game archive | `recovery/`, `core/blocks.py` (with Preetika), `formats/lablog.py`, `formats/vault.py`, `formats/game_archive.py` |
| Bhupesh | Evidence: field meanings, checker, FIELD-LOG, **real-world format** | `evidence/`, `formats/realworld.py`, LIBRA-98 field evidence |
| Manas | Delivery: outputs, report.json, receipts, FORMAT-SPEC, tests, corruption tool (truncate, bit flip, zero, insert, delete), Docker, README | `output/`, `tests/`, `tools/corrupt.py`, `Dockerfile` |

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
4. Add a test, run `make test`, run `./salvage samples out`, run `make spec`.

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
- `tools/practice.py` (or `make practice`): made-up practice formats with known answers, in
  `practice/` (git-ignored). `prec` is like LIBRA-98 (with a decoy length field), `plog` like
  LABLOG, `parc` like VAULT. Rehearse on these until the real samples arrive; never copy their
  layouts into `formats/`. `tests/test_practice.py` shows the shared helpers decoding all three.
- `tools/rehearse.py` (or `make rehearse`): runs the real `./salvage` on `practice/` with three
  practice decoders and scores every field against the answers. The number that matters is
  **FALSE RECOVERIES** (verified or corrected but wrong): it must stay 0. The practice decoders
  in that file are worked examples of evidence gates for each kind of format: copy the pattern,
  not the layout.
- `tools/hexview.py <file>`: hex + ASCII view with offsets
- `tools/corrupt.py <file> --out <dir>`: damaged copies + `manifest.json`
- `tools/log.py`: add a FIELD-LOG row

## Rules every module follows

- **Never invent data.** Unproven = `unverified`. Unreadable = `lost` with value `None`.
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
- **Game archive choice is decided by H12** (Khushi picks the format from the samples; until
  then `formats/game_archive.py` stays a stub with `ready = False`).
- **Hour 8 checkpoint:** LIBRA-98 passes through the CLI in Docker, or everyone helps until it does.
- Cut order if behind: receipts, real-world format, game archive. Never cut LABLOG, damage reports or the logs.
