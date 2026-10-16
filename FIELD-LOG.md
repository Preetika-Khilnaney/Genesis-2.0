# FIELD-LOG

Dated log of every hypothesis we tried, including the ones that failed. Append rows as you go
(`python3 tools/log.py ...` does it for you). Outcomes: `accepted`, `rejected`, `open`.

| Time | Format | Hypothesis | Evidence | Outcome | By |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16 10:11 | libra98 (stand-in) | bytes 0-7 are the magic 'LIBRA-98' | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | byte 8 is a version number, always 1 | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 9 is the record count: 20 + count*30 == file size | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u32 at 11 is a unix timestamp (1990-2010) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the file size | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the number of bytes after it | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the length of the record area | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 == record_count*30 + 7 (meaning unknown) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | bytes 17-19 are zero padding | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u32 at +0 is an id counting up by 1 | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record bytes +4..+23 are a NUL-padded name | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u16 at +24 is a DOS date (1985-2010) | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u8 at +26 is a score 0-100 | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u8 at +27 is a flag set (values 0-3) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record bytes +28..+29 are zero padding | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record u32 at +0 is an id counting up by 1 (undamaged files only; the 9/10 counterexample is libra98_1.damaged-zeroed_66_89, whose record 2 was wiped) | held on 6/6 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record bytes +4..+23 are a NUL-padded name (undamaged files only; same counterexample) | held on 6/6 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record u16 at +24 is a DOS date 1985-2010 (undamaged files only; same counterexample) | held on 6/6 samples | accepted | Preetika |
