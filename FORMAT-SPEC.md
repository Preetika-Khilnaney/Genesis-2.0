# FORMAT-SPEC

Generated from the spec library (`src/salvage/formats/`). Do not edit by hand:
change the FormatSpec and regenerate with `make spec`.

Field statuses used in outputs: `verified`, `corrected`, `unverified`, `lost`.

## game_archive

TODO

- Magic: `none` at offset 0
- Endianness: little

_Status: in progress (decoder not ready)._

## lablog

TODO

- Magic: `none` at offset 0
- Endianness: little
- Checksum: TODO: algorithm, coverage, where it is stored

_Status: in progress (decoder not ready)._

## libra98

Header of 20 bytes, then record_count fixed-size records of 30 bytes. No checksum, so values are verified by the layout fitting the file exactly, an exact round trip and per-field checks (ids count up by 1, readable names, real dates, scores 0-100). STAND-IN layout from our own samples; redo from the real samples.

- Magic: `4c 49 42 52 41 2d 39 38` at offset 0
- Endianness: little
- Record count: header field `record_count`

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 8 | file signature 'LIBRA-98' | FIELD-LOG: same in all samples |
| version | u8 | 1 | format version, 1 in every sample | FIELD-LOG: constant 1; kept out of the magic so other versions still match |
| record_count | u16 | 2 | number of records | FIELD-LOG: 20 + count * 30 == file size in every undamaged sample |
| created | unix32 | 4 | file creation time (UTC) | FIELD-LOG: plausible 1998 timestamp in every sample |
| decoy_15 | u16 | 2 | unknown: equals record_count * 30 + 7, but is NOT the file size, the bytes after it, or the record area length | FIELD-LOG: 3 length meanings rejected |
| reserved | bytes | 3 | zero padding | FIELD-LOG: zero in every sample |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| id | u32 | 4 | record id, counts up by 1 from 1000 | FIELD-LOG: counts up by 1 in every undamaged sample |
| name | str | 20 | name, NUL-padded | FIELD-LOG: printable text + NUL padding in every undamaged sample |
| enrolled | dos_date | 2 | enrolment date (DOS date) | FIELD-LOG: valid 1985-2010 DOS date in every undamaged sample |
| grade | u8 | 1 | score 0-100 | FIELD-LOG: 0-100 in every sample |
| flags | u8 | 1 | flag bits, values 0-3 seen | FIELD-LOG: 0-3 in every sample |
| pad | bytes | 2 | zero padding | FIELD-LOG: zero in every sample |

- decoy_15 looks like a length field but every length meaning was rejected; it stays unverified.

## realworld

TODO

- Magic: `none` at offset 0
- Endianness: little

_Status: in progress (decoder not ready)._

## vault

TODO

- Magic: `none` at offset 0
- Endianness: little

_Status: in progress (decoder not ready)._
