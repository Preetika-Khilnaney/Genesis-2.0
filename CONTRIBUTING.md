# Contributing (hackathon rules)

## Owners

| Person | Owns | Files |
| --- | --- | --- |
| Preetika | Core engine, CLI, shared interfaces, LIBRA-98, integration | `cli.py`, `core/`, `formats/libra98.py` |
| Khushi | Recovery: CRC gate, resync, LABLOG, VAULT, game archive | `recovery/`, `formats/lablog.py`, `formats/vault.py`, `formats/game_archive.py` |
| Bhupesh | Evidence: field meanings, checker, FIELD-LOG, real-world format | `evidence/`, `formats/realworld.py`, LIBRA-98 field evidence |
| Manas | Delivery: outputs, report.json, receipts, FORMAT-SPEC, tests, Docker, README | `output/`, `tests/`, `tools/corrupt.py`, `Dockerfile` |

## Shared interfaces (change only after telling the team)

- `core/model.py`: `FieldStatus`, `Field`, `Record`, `DamageEntry`, `FileResult`
- `core/spec.py`: `FieldSpec`, `FormatSpec`
- `core/registry.py`: `Decoder` + `@register` + `DecodeContext` (siblings of the same format)

Code against these and you never wait on anyone.

## Adding a format

1. Fill the module's `FormatSpec` (every field with `desc` and `evidence`).
2. Implement `decode(path, data, ctx)` (header + records formats can just call `core.simple.decode_simple`).
   `ctx.samples(data)` gives this file plus every other file of the same format, for the evidence check.
3. Set `ready = True`. Until then the fingerprinter ignores it.
   Files with a damaged magic are still matched: 1–2 wrong magic bytes (`near_magic`), or a header
   whose record count explains the file exactly (`structure_score`). Override `structure_score()` for
   block or index formats so damaged-header files of your format are still recognised.
4. Add a test, run `make test`, run `./salvage samples out`, run `make spec`.

## Rules every module follows

- **Never invent data.** Unproven = `unverified`. Unreadable = `lost` with value `None`.
- **Never crash.** Use `ByteReader` (bounds-checked). Turn `OutOfBounds` into a `DamageEntry`.
- **Verified needs evidence:** checksum pass, round-trip match, or an accepted checker verdict.
- **Log every hypothesis**, including failures, as you go:
  `python3 tools/log.py <format> "<hypothesis>" "<evidence>" accepted|rejected|open --by <name>`
- **No network, no new runtime dependencies** (standard library only).
- **Deterministic output.** Seed anything random.

## Git workflow

- Branch per task: `preetika/libra98`, `khushi/lablog-crc`, `bhupesh/checker`, `manas/report`.
- Small PRs into `main`; `make test` must pass (CI runs it).
- Pull `main` before you start and before you open a PR.
- **Hour 8 checkpoint:** LIBRA-98 passes through the CLI in Docker, or everyone helps until it does.
- Cut order if behind: receipts, real-world format, game archive. Never cut LABLOG, damage reports or the logs.
