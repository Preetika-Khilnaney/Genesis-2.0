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

A 6-byte header, then checksummed blocks back to back until the end of the file. Each block is a 2-byte marker A5 5A, a sequence number, a payload length, the payload (text like t=89;temp=24.9;ph=6.81) and a CRC-32 of the payload. STAND-IN layout from our own samples; redo from the real samples.

- Magic: `4c 42 4c 47` at offset 0
- Endianness: little
- Checksum: CRC-32 (zlib.crc32) of the payload only, stored as u32 little-endian after the payload

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 4 | file signature 'LBLG' | FIELD-LOG: same in all 6 samples |
| unknown_4 | u16 | 2 | meaning unknown; one value per file (40-45 seen) | FIELD-LOG: not the block count, the file size or a constant (open) |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| seq | u16 | 2 | block sequence number, 0, 1, 2 ... (after marker A5 5A) | FIELD-LOG: counts up by 1 from 0 in every sample |
| length | u16 | 2 | payload length in bytes; block = length + 10 | FIELD-LOG: walks all 37 blocks to EOF; the CRC rejects 2 rival readings |
| payload | bytes | var | printable ASCII text, ';'-separated key=value pairs | FIELD-LOG: printable in every block; crc32 matches all 37 blocks |
| t | str | var | payload key t (number) | FIELD-LOG: key order t, temp, ph |
| temp | str | var | payload key temp (number) | FIELD-LOG: key order t, temp, ph |
| ph | str | var | payload key ph (number) | FIELD-LOG: key order t, temp, ph |

- Blocks: A5 5A | u16 seq | u16 length N | N payload bytes | u32 crc32(payload).
- The CRC does not cover seq or length; see the module docstring for how they are verified.
- unknown_4 stays unverified until its meaning is proven.

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

A 6-byte header with the entry count, an index table of 24-byte entries, then the blobs back to back. Names are XORed with a single-byte key; blobs are run-length encoded (count, byte) pairs. No checksum. STAND-IN layout from our own samples; redo from the real samples.

- Magic: `56 41 4c 54` at offset 0
- Endianness: little

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 4 | file signature 'VALT' | FIELD-LOG: same in all 6 samples |
| count | u16 | 2 | number of index entries | FIELD-LOG: first blob starts at 6 + count * 24 in every sample |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| name | str | 12 | entry name, XORed with a single-byte key, NUL-padded | FIELD-LOG: key 0x5C wins on every sample; not per file or per entry |
| offset | u32 | 4 | absolute offset of the blob | FIELD-LOG: blobs tile the data area exactly in every sample |
| size | u32 | 4 | stored (compressed) blob size | FIELD-LOG: blobs chain end to start to EOF; 56 in every sample entry |
| raw_size | u32 | 4 | decoded blob size | FIELD-LOG: equals the RLE-decoded size of every blob |
| data | bytes | var | decoded blob content (text when printable, else hex) | FIELD-LOG: RLE 'pairs' round-trips every blob; 'packbits' none |

- The RLE variant and the XOR key are chosen from the samples at run time (all-samples rule).
- No checksum: a bit flip in a literal byte that keeps the text printable cannot be detected.
