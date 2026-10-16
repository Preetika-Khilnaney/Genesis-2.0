# Pitch Notes & Judge Defense

Team: **Chargeman Ken** · Problem: **PS 02 (Ascension 02)** · Track: **EVA 03**

---

## 1. The One-Line Solution

> **"An offline tool that uses neuro-symbolic inference to decode undocumented legacy files, recover every verifiable record, and report any unrecoverable data."**

---

## 2. 3-4 Minute Demo Script & Narrative

### Hook (0:00 – 0:45)
- **Problem**: Undocumented legacy binary files from obsolete systems. When corrupted or truncated, standard parsers crash, hallucinate corrupted bytes, or invent values.
- **Our Promise**: Strict zero-invented-data guarantee. Always exits code 0. Deterministic, fully offline, and backed by cryptographic audit receipts.

### Live Demo Flow (`bash tools/demo.sh`) (0:45 – 2:30)
1. **[1/5] Clean Decoding (`libra98`)**:
   - Runs in Docker with `--network none`.
   - Every field is verified by layout invariance, cross-sample evidence, and exact round-trip reconstruction.
2. **[2/5] Damage Reporting (`libra98_damaged`)**:
   - When blocks are cut or bytes deleted, salvage does not guess.
   - Outputs explicit `damage` ranges with exact causes (`truncated`, `bad_magic`, `bad_length`, `crc_fail`).
   - Intact records preceding damage remain recovered; damaged fields are honestly marked `lost` with `value: null`.
3. **[3/5] Unknown File Handling**:
   - Random/unrecognised binary inputs are never forced into guessed formats.
   - Extracts Shannon entropy, 256-byte block entropy maps (NumPy), and printable ASCII/UTF-16LE strings.
   - Output contains zero invented records (`records: []`).
4. **[4/5] Tamper-Evident Receipt Chain**:
   - `receipts.jsonl` implements a SHA-256 hash chain starting from 64 zeros (`GENESIS`).
   - Every file's processing is sealed with `spec_version`, input hash, and status counts.
   - Editing, reordering, or deleting any line instantly breaks `verify_chain()`.
5. **[5/5] Empirical Risk Calibration**:
   - Live calibration numbers over 180 adversarial damage variants.
   - Measured false recovery and false loss rates recorded directly into `corruption_lab_results.json`.

### Conclusion & Wrap-Up (2:30 – 3:30)
- Fully containerised, runs offline with vendored dependencies, passes all JSON schemas.

---

## 3. Likely Judge Questions & Honest Answers

### Q1: "Did you invent these methods?"
**Answer**:
> *"No single component is invented from scratch: declarative binary specs, CRC-gated parsing, Shannon entropy fingerprinting, and hash-chained audit trails are established engineering techniques. What is new is combining them into a zero-trust, neuro-symbolic recovery pipeline designed specifically to never invent data on legacy files."*

### Q2: "How do you know you aren't outputting false recoveries?"
**Answer**:
> *"We enforce a strict 4-state status contract: `verified`, `corrected`, `unverified`, `lost`. A field is only marked `verified` if it satisfies mathematical proof (CRC-32 match, exact round-trip byte identity, or all-sample layout invariance across $\ge 2$ siblings). If a format lacks a checksum (like LIBRA-98), our corruption lab empirically measures the false-recovery risk under bit flips and reports it honestly (e.g. 11.38% on sparse flips), rather than claiming impossible perfection."*

### Q3: "What external benchmark numbers do you cite, and how do they compare?"
**Answer**:
> - **LFM2 vs Qwen3 on CPU**: Published benchmarks show Liquid LFM2 is $\sim 2\times$ faster on CPU inference than comparable dense models, making it ideal for offline edge extraction.
> - **BinaryInferno False Positive Rates**: Published literature for BinaryInferno cites a 0.04 false-positive rate compared to 0.11–0.22 for standard heuristics.
> - **Held-Out E-Values**: A conservative e-value threshold of $\ge 20:1$ provides a theoretical bound of at most 5% wrong-field acceptance.
> - **Our Own Measured Numbers**: In our corruption lab, across 180 damaged variants, false loss rate was measured at **0.00%**, and false recovery rate was measured at **11.38%** (concentrated exclusively in unchecksummed printable string bit-flips).

### Q4: "Why does the tool always exit code 0 even on corrupted files?"
**Answer**:
> *"In automated forensics and data recovery pipelines, an unexpected process exit 1 or unhandled exception halts batch ingestion. The salvage contract guarantees reliable completion: every input gets an output JSON, any failure is recorded inside `error` and `damage` fields, and the process completes cleanly."*

---

## 4. Definition of Done Checklist

| Criteria | Implementation Status | Evidence |
| --- | :---: | --- |
| **Zero invented data** | Pass | Destroyed fields are marked `lost` with `value: null`. Tested in `tests/test_damaged.py`. |
| **Strict status labels** | Pass | Only `verified`, `corrected`, `unverified`, `lost`. Validated by `schema_validate.py`. |
| **Offline Docker build** | Pass | Pinned wheels in `vendor/wheels/` for both `linux/amd64` and `linux/arm64`. `--network none` verified. |
| **Schema compliance** | Pass | All outputs validate against `output.schema.json`, `report.schema.json`, `receipt.schema.json`. |
| **Audit trail** | Pass | `receipts.jsonl` hash chain passes `verify_chain()`; tamper detection demonstrated live. |
| **Hostile inputs** | Pass | 0-byte, empty dirs, symlink loops, chmod 000, huge files tested in `tests/test_hostile.py`. |
| **Determinism** | Pass | Identical inputs processed twice produce 100% byte-identical output directory. |
| **Format specifications** | Pass | `FORMAT-SPEC.md` generated directly from declarative code via Jinja2 template (`make spec`). |
| **Empirical calibration** | Pass | Seeded damage variants measured in `corruption_lab_results.json`. |
