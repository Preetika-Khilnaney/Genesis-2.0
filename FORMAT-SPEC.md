# FORMAT-SPEC

Generated from the decoders in `src/salvage/formats/` with `make spec`. Do not edit by hand.
Every claim is tested against the organisers' real samples (`real-samples/samples/`); the
hypotheses, including the rejected ones, are in `FIELD-LOG.md` (regenerate with
`python3 tools/field_evidence.py`).

Output follows `real-samples/OUTPUT-CONTRACT.md`: per file `status` is ok / partial / unsupported /
unrecognized / failed; `damage[].kind` uses the contract vocabulary; a record that could not be
verified carries `"verified": false` and its `"issues"`. A damage entry with `"lossy": false` was
found and fully repaired (a provable single-bit fix) or did not lose data.

| Format | Files | Integrity check used for verification |
| --- | --- | --- |
| LIBRA-98 | s01-s04, s29 | per record: sum of bytes after the length field (mod 256); trailer: sum16 of all bytes before it |
| LABLOG | s05-s07 | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), little-endian, over type+length+payload; header CRC over bytes 0..29 |
| VAULT | s08-s10 | CRC-32 (zlib) of the decoded payload, little-endian, after the blob data |
| WKS | s11-s13 | none (structure only) |
| WPD | s14-s15 | none (structure: text start, packet offsets inside the file) |
| BRAVO | s16-s17 | none (structure: run table length) |
| CVT | s18-s19 | none (structure: declared block count, record table) |
| EBCDIC-DUMP | s20-s22 | trailer: record count and credits total cross-check the detail records |
| WAD | s23 | none (entries are checked against the file bounds) |
| PAK | s24 | none (entries are checked against the file bounds) |

## LIBRA-98

```
Layout, worked out from real-samples s01-s04 and expected_outputs (every claim is in FIELD-LOG.md):

  Header (16 bytes, little-endian)
    0   4  magic "LB98"
    4   1  version (2 in every sample)
    5   1  encoding flag: 0 = cp437 (DOS), 1 = cp1252     (s02 'Mis\x82rables' = cp437 e-acute)
    6   2  declared record count
    8   2  created date (DOS date)          10  2  created time (DOS time)
    12  2  data offset (16, or 40 when an extra header block follows: s03 'LIBSYS/98 REL 2.1')
    14  2  branch id
  Record (from data offset, repeated)
    0   1  marker 0xA5
    1   1  length L = number of bytes that follow
    2   1  flags: bit0 checked_out, bit1 deleted, bit2 reference_only
    3   4  id
    7   .  title  (u8 length + text)        .  author (u8 length + text)
    .   2  year - 1500                       .  2  price in cents
    .   1  copies                            .  10 ISBN (ASCII)
    .   2  due date (DOS date, 0 = none)    .  1  checksum = sum of bytes 2..L (mod 256)
  Trailer
    "END!" + u16 sum of every byte before the trailer (mod 65536)

Verification: a record is verified when its own checksum matches and its fields consume exactly
L bytes. The trailer sum covers the header too. Damage is reported, never patched over.
```

Library circulation file: 16-byte header, then variable-length records each with its own sum-8 checksum, then an 'END!' trailer with a sum-16 over the whole file.

- Magic: `4c 42 39 38` at offset 0
- Endianness: little
- Checksum: per record: sum of bytes after the length field (mod 256); trailer: sum16 of all bytes before it
- Record count: header field `declared_record_count`

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 4 | 'LB98' | same in all samples |
| version | u8 | 1 | format version | 2 in all samples |
| encoding | u8 | 1 | 0 = cp437, 1 = cp1252 | s02 text decodes only as cp437; s03 flag 1 |
| declared_record_count | u16 | 2 | records declared | matches record count in s01-s03 |
| created_date | dos_date | 2 | creation date | matches expected s01, s04 |
| created_time | dos_time | 2 | creation time | matches expected s01, s04 |
| data_offset | u16 | 2 | first record offset | 16, or 40 with an extra header (s03) |
| branch_id | u16 | 2 | library branch | matches expected s01, s04 |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| marker | u8 | 1 | 0xA5 | every record |
| length | u8 | 1 | bytes after this field | tiles records exactly |
| flags | u8 | 1 | bit0 checked_out, bit1 deleted, bit2 reference_only | bit0 set exactly when a due date exists; bit1/bit2 order from the contract field order |
| id | u32 | 4 | record id | matches expected |
| title | pstr8 | var | title | matches expected |
| author | pstr8 | var | author | matches expected |
| year | u16 | 2 | publication year - 1500 | 397 -> 1897 (Dracula) |
| price_cents | u16 | 2 | price in cents | matches expected |
| copies | u8 | 1 | copies held | matches expected |
| isbn | str | 10 | ISBN-10 | matches expected |
| due_date | dos_date | 2 | due date, 0 = none | 0x2593 -> 1998-12-19 |
| checksum | u8 | 1 | sum of bytes after length | holds on all 22 complete records |

- Trailer 'END!' + u16 sum of all preceding bytes (holds on s01-s03; s04 is truncated).

## LABLOG

```
Layout, worked out from real-samples s05-s07 and expected_outputs/s05 (evidence in FIELD-LOG.md):

  Header (32 bytes, little-endian)
    0  4  magic "LLOG"            4  1  version            5  1  channel count
    6  2  sample interval in 10 ms units (50 -> 500 ms)
    8  16 instrument name, NUL padded
    24 4  start time, seconds since 1990-01-01 UTC
    28 2  declared block count    30 2  CRC-16/CCITT-FALSE of bytes 0..29
  Blocks (from offset 32)
    0xB1, u8 type, u16 length, payload, u16 CRC-16/CCITT-FALSE over (type, length, payload)
    type 3  channels: per channel  unit[4] (NUL padded), f32 scale, f32 offset
    type 1  data:  u16 first sample, u8 n, then n x channels i16 raw; value = raw*scale + offset;
            raw 0x8000 = dropout -> null
    type 2  event: u16 sample, u8 severity, u8 length + message

A block whose CRC fails is repaired only when exactly one flipped bit explains it (provable for
CRC-16 on blocks this size); otherwise its samples are output as verified=false. Truncated and
unknown blocks are reported; the parser resyncs on the next 0xB1 whose CRC checks out.
```

Instrument log: 32-byte header with its own CRC-16, then CRC-16-protected blocks (channels, data, events).

- Magic: `4c 4c 4f 47` at offset 0
- Endianness: little
- Checksum: CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), little-endian, over type+length+payload; header CRC over bytes 0..29

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 4 | 'LLOG' | all samples |
| version | u8 | 1 | format version | 1 in all samples |
| channels | u8 | 1 | channel count | matches channel block size |
| interval | u16 | 2 | sample interval / 10 ms | 50 -> 500 ms (expected s05) |
| instrument | str | 16 | instrument name | expected s05 |
| start | u32 | 4 | seconds since 1990-01-01 UTC | -> 1992-10-11T05:07:43Z (expected s05) |
| declared_block_count | u16 | 2 | blocks that follow | 7 / 8 / 8, matches s05-s07 |
| header_crc | u16 | 2 | CRC-16/CCITT-FALSE of bytes 0..29 | holds on s05-s07 |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| marker | u8 | 1 | 0xB1 | every block |
| type | u8 | 1 | 1 data, 2 event, 3 channels | payload shapes |
| length | u16 | 2 | payload length | tiles blocks exactly |
| crc | u16 | 2 | CRC-16/CCITT-FALSE of type+length+payload | holds on 22 of 23 blocks |

- Data payload: u16 first_sample, u8 n, n x channels i16; 0x8000 = dropout (null).
- Channels payload: per channel unit[4], f32 scale, f32 offset; value = raw*scale + offset.

## VAULT

```
Layout, worked out from real-samples s08-s10 and expected_outputs/s08 (evidence in FIELD-LOG.md):

  Header (16 bytes, little-endian)
    0 4 magic "VLT1"   4 2 entry count   6 1 XOR key   7 1 flags (bit0: name lengths XOR'd too)
    8 4 index offset   12 4 name-table offset
  Index (entry count x 16 bytes)
    u16 id, u8 type (1 text, 2 bitmap, 3 binary), u8 flags (bit0 RLE90, bit1 XOR),
    u32 name offset (into the name table), u32 blob offset, u16 stored length, u16 decoded size
  Name table: u8 length + name, each byte XOR (key + i)
  Blob at blob offset: "BL", u16 id, then stored-length bytes = data + u32 CRC-32 of the DECODED data
    data: XOR (key + i) if flag bit1, then RLE90 (0x90 n: repeat previous byte n-1 more times;
    0x90 0x00 = a literal 0x90) if flag bit0
  Bitmap payload: u8 width, u8 height, width*height pixels.

Verification: an entry is verified when its CRC-32 matches the decoded data and the decoded size
matches the index. If XOR and RLE could apply in either order, the CRC decides which is right.
```

Archive: header, index table, XOR-obscured name table, and blobs (optionally XOR'd and RLE90-compressed), each with a CRC-32 of its decoded data.

- Magic: `56 4c 54 31` at offset 0
- Endianness: little
- Checksum: CRC-32 (zlib) of the decoded payload, little-endian, after the blob data

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| magic | bytes | 4 | 'VLT1' | all samples |
| entry_count | u16 | 2 | index entries | expected s08 |
| xor_key | u8 | 1 | XOR key; byte i uses key+i | names decode; expected s08 = 32 |
| flags | u8 | 1 | bit0: name lengths XOR'd with the key | s09 (flag 1) name lengths |
| index_offset | u32 | 4 | index table offset | index ends exactly at EOF |
| names_offset | u32 | 4 | name table offset | names decode |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| id | u16 | 2 | entry id (repeated after 'BL' in the blob) | expected s08 |
| type | u8 | 1 | 1 text, 2 bitmap, 3 binary | expected s08 types |
| flags | u8 | 1 | bit0 RLE90-compressed, bit1 XOR'd | expected 'compressed' |
| name_offset | u32 | 4 | offset in the name table | names decode |
| blob_offset | u32 | 4 | offset of 'BL' blob | 'BL'+id found there |
| stored_length | u16 | 2 | data + 4-byte CRC | tiles blobs exactly |
| size | u16 | 2 | decoded size | expected s08 sizes |

## WKS

```
Public format, checked against real-samples s11-s13 and expected_outputs/s11 (FIELD-LOG.md).
The documentation is a starting hypothesis; where the bytes disagree, the bytes win.

  Records: u16 opcode, u16 length, body (little-endian). BOF (0x0000, version) first, EOF (0x0001) last.
  0x0006 RANGE    u16 first col, first row, last col, last row       -> metadata.declared_range
  0x0008 COLW     u16 col, u8 width                                  -> metadata.column_widths
  Cells start with u8 format, u16 col, u16 row:
  0x000C BLANK    -                                    0x000D INTEGER  i16
  0x000E NUMBER   f64                                  0x000F LABEL    prefix char + NUL text
  0x0010 FORMULA  f64 cached value, u16 length, formula bytes (kept as hex: formula_raw_hex)
  Label prefix: ' left, " right, ^ center, \ repeat.
  Format byte: bit7 protected, bits 4-6 type (0 fixed, 1 sci, 2 currency, 3 percent, 4 comma,
  7 special), bits 0-3 decimals or special subtype (special 2/3/4 = dates, serial from 1899-12-30).

No checksum: a record is verified when its length is exactly right for its opcode and it lies
inside the file. A cell written twice keeps the last value (as 1-2-3 loads it) and is warned about.
```

Lotus 1-2-3 worksheet: a stream of opcode/length/body records from BOF to EOF.

- Magic: `00 00 02 00` at offset 0
- Endianness: little
- Checksum: none (structure only)

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| bof | u16 | 2 | opcode 0x0000, length 2 | all samples |
| version_code | u16 | 2 | 0x0404 = WKS | expected s11 |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| opcode | u16 | 2 | record type | Lotus documentation, checked on samples |
| length | u16 | 2 | body length | records tile the file exactly |
| format | u8 | 1 | cell format byte | 0xFF default / 0x22 currency,2 |
| col | u16 | 2 | 0-based column | expected s11 |
| row | u16 | 2 | 0-based row | expected s11 |

## WPD

```
Checked against real-samples s14-s17 (FIELD-LOG.md).

WPD
  Header: 0xFF "WPC", u32 text start, u8 product, u8 file type, u8 major, u8 minor,
          u16 encryption key (non-zero = password-protected -> status "unsupported"), u16 reserved.
  Packet index at 16: u16 type, u16 length, u32 offset (type 1 = document summary).
  Text from the text start to the first packet: 0x0A hard return (ends a paragraph), 0x0D soft
  return (a space), 0x0C hard page (page_break record), 0x09 tab, 0xA0 hard space, 0xA9-0xAB hard
  hyphen, 0xAC-0xAE soft hyphen (dropped), 0xC0-0xCF fixed-length codes (C3 xx C3 / C4 xx C4 =
  attribute on / off), 0xD0-0xFF variable-length codes (code, subcode, u16 length, body).
  s15's index says the text runs to byte 223 but the file is 136 bytes: truncated.

BRAVO
  Plain text, paragraphs terminated by CR (0x0D), then ^Z (0x1A), then the format runs:
  pad to an even file offset, u16 big-endian word count, runs of 6 bytes: u16 start, u16 length,
  u8 looks (bit1 bold, bit2 italic), u8 font (all big-endian). s16: "Alto users" bold,
  "Bold and italic" bold+italic. s17 declares 12 words but holds 15 bytes: last run cut off.
```

WordPerfect 5.x document: 16-byte prefix, packet index, text stream with function codes.

- Magic: `ff 57 50 43` at offset 0
- Endianness: little
- Checksum: none (structure: text start, packet offsets inside the file)

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| ident | bytes | 4 | FF 'WPC' | s14, s15 |
| text_start | u32 | 4 | first text byte | 48 in both samples |
| product | u8 | 1 | 1 = WordPerfect | s14 |
| file_type | u8 | 1 | 0x0A = document | s14 |
| major | u8 | 1 | major version | s14 |
| minor | u8 | 1 | minor version | s14 |
| encryption | u16 | 2 | 0 = not protected | 0 in both samples |

## BRAVO

```
Checked against real-samples s14-s17 (FIELD-LOG.md).

WPD
  Header: 0xFF "WPC", u32 text start, u8 product, u8 file type, u8 major, u8 minor,
          u16 encryption key (non-zero = password-protected -> status "unsupported"), u16 reserved.
  Packet index at 16: u16 type, u16 length, u32 offset (type 1 = document summary).
  Text from the text start to the first packet: 0x0A hard return (ends a paragraph), 0x0D soft
  return (a space), 0x0C hard page (page_break record), 0x09 tab, 0xA0 hard space, 0xA9-0xAB hard
  hyphen, 0xAC-0xAE soft hyphen (dropped), 0xC0-0xCF fixed-length codes (C3 xx C3 / C4 xx C4 =
  attribute on / off), 0xD0-0xFF variable-length codes (code, subcode, u16 length, body).
  s15's index says the text runs to byte 223 but the file is 136 bytes: truncated.

BRAVO
  Plain text, paragraphs terminated by CR (0x0D), then ^Z (0x1A), then the format runs:
  pad to an even file offset, u16 big-endian word count, runs of 6 bytes: u16 start, u16 length,
  u8 looks (bit1 bold, bit2 italic), u8 font (all big-endian). s16: "Alto users" bold,
  "Bold and italic" bold+italic. s17 declares 12 words but holds 15 bytes: last run cut off.
```

Xerox Alto Bravo document: CR-terminated paragraphs, ^Z, then big-endian format runs.

- Magic: `none` at offset 0
- Endianness: little
- Checksum: none (structure: run table length)

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| start | u16be | 2 | run start in the text | s16 4 = 'Alto users' |
| length | u16be | 2 | run length | s16 10, 15 |
| looks | u8 | 1 | bit1 bold, bit2 italic | s16 6 on 'Bold and italic' |
| font | u8 | 1 | font number | 0 in samples |

## CVT

```
Checked against real-samples s18-s19 and expected_outputs/s18 (FIELD-LOG.md). All text is PETSCII
(upper/lower case swapped versus ASCII, 0xA0 = padding, 0x0D = new line). Blocks are 254 bytes.

  Block 0  directory entry (30 bytes) + signature "PRG formatted GEOS file V1.0"
     0 file type   3..18 name (16, 0xA0 padded)   21 structure (0 seq, 1 vlir)   22 GEOS type
     23..27 year (19xx, 100+ = 20xx), month, day, hour, minute       28 u16 block count
  Block 1  info block: class name @0 (20 bytes), author @20 (20), description @40
  seq:  blocks 2.. are the data; text = data with trailing NULs removed      -> one record, slot 0
  vlir: block 2 is the record table: 127 x (u8 blocks, u8 bytes used in the last block);
        (0, 0xFF) = empty slot, (0, 0) = end. Records follow, each padded to whole blocks.
        Bytes used are taken as stored (NOT minus 1 as on a real 1541 disk): the samples prove it.

Verification: the signature must be present, the declared block count must match the blocks in
the file, and every vlir record must fit in the data that follows the table.
```

GEOS Convert file: directory entry + signature block, info block, then data (seq) or a record table followed by records (vlir), in 254-byte blocks, PETSCII text.

- Magic: `50 52 47 20 66 6f 72 6d 61 74 74 65 64 20 47 45 4f 53 20 66 69 6c 65` at offset 30
- Endianness: little
- Checksum: none (structure: declared block count, record table)

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| file_type | u8 | 1 | C64 file type | 0x83 in samples |
| name | bytes | 16 | PETSCII name, 0xA0 padded | expected s18 |
| structure | u8 | 1 | 0 seq, 1 vlir | expected s18 'seq'; s19 table |
| geos_type | u8 | 1 | GEOS file type | expected s18 = 7 |
| modified | bytes | 5 | year, month, day, hour, minute | expected s18 |
| declared_blocks | u16 | 2 | blocks after the directory block | s18 4 = info + 3 data; s19 6 = info + table + 4 data |

## EBCDIC-DUMP

```
Checked against real-samples s20-s22 and expected_outputs/s20 (FIELD-LOG.md). Text is EBCDIC
code page 037. IBM variable-length records: each record starts with an RDW (u16 big-endian length
including the 4-byte RDW, then 2 zero bytes). Some tapes also group records into blocks, each with
a BDW of the same shape (s21).

  H  header   'H', title (20), run date YYYYMMDD (8)
  D  detail   'D', student id (6), name (20), dob packed-decimal P5 (YYYYMMDD),
              gpa P3 (2 decimals), credits u16 big-endian binary, status (1), balance P4 (2 decimals,
              signed: sign nibble C/F = +, D = -), 2 filler bytes
  T  trailer  'T', record count P4, credits total P5

Verification: every packed field must have valid digits and sign; the trailer count and credits
total must agree with the detail records (they cross-check the whole file).
```

Mainframe tape dump: EBCDIC (cp037) variable-length records with RDWs, optionally blocked with BDWs; header, student detail records with packed-decimal fields, trailer.

- Magic: `none` at offset 0
- Endianness: little
- Checksum: trailer: record count and credits total cross-check the detail records

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| rdw | u16be | 2 | record length incl. RDW, then 00 00 | tiles s20/s22 |
| type | bytes | 1 | H / D / T | all samples |
| student_id | str | 6 | EBCDIC digits | expected s20 |
| name | str | 20 | EBCDIC, space padded | expected s20 |
| dob | bytes | 5 | packed decimal YYYYMMDD | 01 97 81 01 1F -> 1978-10-11 |
| gpa | bytes | 3 | packed decimal, 2 decimals | 00 26 3C -> 2.63 |
| credits | u16be | 2 | binary | 00 28 -> 40 |
| status | str | 1 | EBCDIC letter | expected s20 |
| balance | bytes | 4 | packed decimal, 2 decimals, signed | 00 69 83 6C -> 698.36 |

- s21 wraps records in blocks: BDW (u16be length, 00 00) then RDW records.
- Trailer count and credits total equal the sums over detail records in s20 and s21.

## WAD

```
Public formats, checked against real-samples s23 (WAD) and s24 (PAK); evidence in FIELD-LOG.md.

  WAD (Doom):  "IWAD"/"PWAD", i32 lump count, i32 directory offset;
               directory entries (16 bytes): i32 offset, i32 size, name[8] (NUL-terminated; bytes
               after the NUL are junk and ignored: s23 "SEGS\0\x7fAB").
               Zero-size lumps (F_START, MAP01...) are markers and are listed too.
  PAK (Quake): "PACK", i32 directory offset, i32 directory length;
               directory entries (64 bytes): name[56] NUL-terminated, i32 offset, i32 size.

Records: name, offset, size, sha256 of the lump/file bytes. An entry is verified when it lies
inside the file and does not start inside the header or directory.
```

Doom WAD: 12-byte header, lumps, directory of 16-byte entries.

- Magic: `50 57 41 44` at offset 0
- Endianness: little
- Checksum: none (entries are checked against the file bounds)

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| ident | bytes | 4 | IWAD or PWAD | s23 PWAD |
| lump_count | i32 | 4 | directory entries | s23: 7 entries end exactly at EOF |
| dir_offset | i32 | 4 | directory offset | s23 |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| offset | i32 | 4 | lump offset | s23 |
| size | i32 | 4 | lump size | s23 |
| name | bytes | 8 | NUL-terminated name | s23 |

## PAK

```
Public formats, checked against real-samples s23 (WAD) and s24 (PAK); evidence in FIELD-LOG.md.

  WAD (Doom):  "IWAD"/"PWAD", i32 lump count, i32 directory offset;
               directory entries (16 bytes): i32 offset, i32 size, name[8] (NUL-terminated; bytes
               after the NUL are junk and ignored: s23 "SEGS\0\x7fAB").
               Zero-size lumps (F_START, MAP01...) are markers and are listed too.
  PAK (Quake): "PACK", i32 directory offset, i32 directory length;
               directory entries (64 bytes): name[56] NUL-terminated, i32 offset, i32 size.

Records: name, offset, size, sha256 of the lump/file bytes. An entry is verified when it lies
inside the file and does not start inside the header or directory.
```

Quake PAK: 12-byte header, files, directory of 64-byte entries.

- Magic: `50 41 43 4b` at offset 0
- Endianness: little
- Checksum: none (entries are checked against the file bounds)

### Header

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| ident | bytes | 4 | PACK | s24 |
| dir_offset | i32 | 4 | directory offset | s24 |
| dir_length | i32 | 4 | directory bytes (64 per entry) | s24: 256 = 4 entries |

### Record

| Field | Type | Length | Description | Evidence |
| --- | --- | --- | --- | --- |
| name | bytes | 56 | NUL-terminated path | s24 |
| offset | i32 | 4 | file offset | s24 |
| size | i32 | 4 | file size | s24 |

## UNKNOWN

Files no decoder recognises (s25 random, s26 empty, s27 text, s28 one byte, s30 PNG) get
`format: UNKNOWN`, `status: unrecognized`, no records, and `metadata` describing the bytes
(size, entropy, what it looks like, readable strings). s29 starts with the LIBRA-98 magic but is
7 bytes long, so it is recognised and `failed` (header truncated).
