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
1. **[1/5] One command, offline**: the organisers' 30 sample files (10 formats + hostile files) in
   Docker with `--network none`. `report.json` lists every file's format and status.
2. **[2/5] Matches the expected outputs**: `tools/check_expected.py` compares with the organisers'
   reference JSON: **7 of 7 match**.
3. **[3/5] Damage is reported, never hidden**: s04 (LIBRA-98 cut off mid-record): status `partial`,
   `truncated` at the exact byte, the cut record kept with `"verified": false` and nulls, not guesses.
4. **[4/5] Proven repair**: s07 (LABLOG) and s10 (VAULT) fail a CRC; exactly one flipped bit explains
   each failure, so it is repaired and reported with `"lossy": false`.
5. **[5/5] Hostile files**: random, empty, text, 1-byte and PNG files are `unrecognized` with no
   records; the 7-byte LIBRA-98 stub is `failed`. Receipt chain: tampering is detected.

### Conclusion & Wrap-Up (2:30 – 3:30)
- Fully containerised, runs offline on the standard library alone, output validates against the contract schemas.

---

## 3. Likely Judge Questions & Honest Answers

### Q1: "Did you invent these methods?"
**Answer**:
> *"No single component is invented from scratch: declarative binary specs, CRC-gated parsing, Shannon entropy fingerprinting, and hash-chained audit trails are established engineering techniques. What is new is combining them into a zero-trust, neuro-symbolic recovery pipeline designed specifically to never invent data on legacy files."*

### Q2: "How do you know you aren't outputting false recoveries?"
**Answer**:
> *"We measured it on the organisers' own files. Every record is verified by the strongest check
> its format has: CRC-16 per block in LABLOG, CRC-32 per blob in VAULT, a sum-8 per record plus a
> file sum-16 in LIBRA-98, a trailer cross-check in the mainframe dump. Anything we cannot prove
> carries `verified: false`. In the corruption lab (`make calibrate`, 360 damaged variants
> of the clean real samples) LIBRA-98, LABLOG and VAULT returned **zero** wrong verified records.
> Formats with no checksum at all (WKS, WPD, BRAVO, CVT, WAD, PAK) can only be checked by
> structure, so a flipped letter inside their text is undetectable by any tool; we measure and
> report that too instead of hiding it."*

### Q3: "What numbers can you show?"
**Answer** (all measured by us on the organisers' kit; reproduce with the commands shown):
> - **Expected outputs**: 7 of 7 match (`make check`).
> - **Crashes**: 0 on about 25,000 damaged and random variants of the samples.
> - **False recoveries on random bit flips** (`make false-recovery`): LABLOG 0%, LIBRA-98 0.09%
>   (rare multi-bit collisions in its sum-8), VAULT 2.7%, EBCDIC 6.8%; no-checksum formats 6–29%.
> - **Corruption lab** (`make calibrate`): 0 false recoveries for LIBRA-98, LABLOG and VAULT.
> - Published figures (LFM2 speed, BinaryInferno, e-value bounds) belong to the methods in our
>   roadmap, not to this build: say so if asked.

### Q4: "Why does the tool always exit code 0 even on corrupted files?"
**Answer**:
> *"In automated forensics and data recovery pipelines, an unexpected process exit 1 or unhandled exception halts batch ingestion. The salvage contract guarantees reliable completion: every input gets an output JSON, any failure is recorded inside `error` and `damage` fields, and the process completes cleanly."*

---

## 4. Definition of Done Checklist

| Criteria | Status | Evidence |
| --- | :---: | --- |
| **Output contract** | Pass | Per-file JSON and `report.json` follow `real-samples/OUTPUT-CONTRACT.md`; schemas in `schema/`. |
| **Expected outputs** | Pass | 7 of 7 match (`make check`, also in CI). |
| **All sample files** | Pass | 30 of 30 identified with the right format and status; `nested/` skipped. |
| **Zero invented data** | Pass | Unprovable records carry `verified: false`; unreadable fields are null. `tests/test_damaged.py`. |
| **No AI at runtime, offline** | Pass | Standard library only; Docker run with `--network none`. |
| **Hostile inputs** | Pass | 0-byte, 1-byte, random, PNG, text, unreadable, symlinks, huge files: `tests/test_hostile.py`. |
| **Determinism** | Pass | Same input twice gives byte-identical output. |
| **FORMAT-SPEC.md** | Pass | Generated from the decoders (`make spec`), layout + evidence for all 10 formats. |
| **FIELD-LOG.md** | Pass | 66 hypotheses on the real bytes incl. 17 rejected (`tools/field_evidence.py`). |
| **Audit trail** | Pass | `receipts.jsonl` hash chain; tampering detected. |
