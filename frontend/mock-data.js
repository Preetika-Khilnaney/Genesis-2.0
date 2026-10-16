// Salvage Mock Data Fixtures according to Brief (Page 8, 9, 10, 12)
// Contains lab_run_07.dat (partial with damage), telemetry_core_01.dat (complete), and unknown_memory_dump.bin (not recognised)

export const MOCK_FORMATS = [
  { name: "EXAMPLE-LOG", category: "Scientific", description: "Structured multi-block experimental log format" },
  { name: "LABLOG", category: "Instrumentation", description: "Multi-channel sensor telemetry blocks with CRC checksums" },
  { name: "LIBRA-98", category: "Database", description: "Legacy library management record table" },
  { name: "VAULT", category: "Archive", description: "Compressed and XOR-obfuscated asset archive" },
  { name: "WKS", category: "Spreadsheet", description: "Lotus 1-2-3 / Symphony worksheet format" },
  { name: "WPD", category: "Document", description: "WordPerfect legacy document stream" },
  { name: "BRAVO", category: "Document", description: "Xerox Alto Bravo styled document format" },
  { name: "CVT", category: "Geos", description: "Commodore GEOS Convert file format" },
  { name: "EBCDIC-DUMP", category: "Mainframe", description: "Fixed-width IBM EBCDIC student records" },
  { name: "WAD", category: "Game", description: "Doom engine package format" },
  { name: "PAK", category: "Game", description: "Quake engine archive format" }
];

export const MOCK_FILES = [
  {
    name: "lab_run_07.dat",
    size: 640,
    declared_size: 1024,
    format: "EXAMPLE-LOG",
    status: "partial",
    status_label: "Partial",
    status_desc: "Some data recovered, some damaged or missing.",
    bytes_declared: 1024,
    bytes_actual: 640,
    bytes_verified: 424,
    recovered_ratio: 0.4141,
    fields_verified: 12,
    fields_unverified: 3,
    damage_count: 3,
    header_size: 64,
    block_count: 8,
    block_size: 120,
    // Byte map segments: [start, end, role, label, details]
    byte_segments: [
      { start: 0, end: 64, role: "header", label: "Header [0, 64)", status: "verified", desc: "Verified magic & declared parameters" },
      { start: 64, end: 184, role: "verified", label: "Block 0 [64, 184)", status: "verified", desc: "Checksum valid, 120 bytes" },
      { start: 184, end: 304, role: "verified", label: "Block 1 [184, 304)", status: "verified", desc: "Checksum valid, 120 bytes" },
      { start: 304, end: 424, role: "damaged", label: "Block 2 [304, 424)", status: "damaged", desc: "CHECKSUM_MISMATCH: stored 0x31C3, computed 0x21E2" },
      { start: 424, end: 544, role: "verified", label: "Block 3 [424, 544)", status: "verified", desc: "Resynchronised after bad block, 120 bytes" },
      { start: 544, end: 640, role: "unverified", label: "Block 4 [544, 640)", status: "unverified", desc: "BLOCK_TRUNCATED: only 96 of 120 bytes exist" },
      { start: 640, end: 1024, role: "missing", label: "Missing Tail [640, 1024)", status: "missing", desc: "FILE_TRUNCATED: 384 bytes missing (24 from block 4 + blocks 5..7)" }
    ],
    // Damage table (Wording strictly: Probable cause & Detected symptom)
    damage: [
      {
        id: 1,
        range: { start: 304, end: 424 },
        length: 120,
        cause_code: "CHECKSUM_MISMATCH",
        cause_name: "Checksum mismatch",
        block: 2,
        detected_symptom: "Stored CRC-16 0x31C3 differs from computed 0x21E2 (XOR 0x1021: 3 bits differ).",
        explanation: "The stored checksum for this block does not match the one computed from its bytes, so the block was excluded.",
        evidence: { algorithm: "CRC-16", stored: "0x31C3", computed: "0x21E2", xor_diff: "0x1021" },
        outcome: "excluded"
      },
      {
        id: 2,
        range: { start: 544, end: 640 },
        length: 96,
        cause_code: "BLOCK_TRUNCATED",
        cause_name: "Block truncated",
        block: 4,
        detected_symptom: "Block is cut off at end of physical file; only 96 of 120 expected bytes are present.",
        explanation: "The record payload ends prematurely at EOF. Partial fields cannot be verified against the block schema.",
        evidence: { bytes_present: 96, bytes_expected: 120, missing_in_block: 24 },
        outcome: "unverified"
      },
      {
        id: 3,
        range: { start: 640, end: 1024 },
        length: 384,
        cause_code: "FILE_TRUNCATED",
        cause_name: "File truncated",
        block: null,
        detected_symptom: "Physical file ends at offset 640, while header declares length of 1024 bytes (384 bytes missing).",
        explanation: "Header declares 8 total records (1024 bytes). Blocks 5, 6, 7 and the remainder of block 4 could not be read.",
        evidence: { declared_size: 1024, actual_size: 640, missing_range: "[640, 1024)" },
        outcome: "excluded"
      }
    ],
    // Decoded JSON
    result_json: {
      source_file: "lab_run_07.dat",
      format: "EXAMPLE-LOG",
      status: "partial",
      metadata: {
        tool_version: "2.0.0",
        header_declared_size: { value: 1024, status: "verified" },
        header_block_count: { value: 8, status: "verified" },
        header_block_size: { value: 120, status: "verified" },
        timestamp_epoch: { value: 915148800, status: "verified" },
        instrument_id: { value: "SPECTRO-44B", status: "verified" }
      },
      records: [
        {
          index: 0,
          offset: 64,
          verified: true,
          values: {
            sensor_id: { value: 101, status: "verified" },
            reading_volts: { value: 3.421, status: "verified" },
            reading_temp_c: { value: 24.8, status: "verified" },
            state_flags: { value: "0x0001 (ACTIVE)", status: "verified" }
          }
        },
        {
          index: 1,
          offset: 184,
          verified: true,
          values: {
            sensor_id: { value: 102, status: "verified" },
            reading_volts: { value: 3.419, status: "verified" },
            reading_temp_c: { value: 25.1, status: "verified" },
            state_flags: { value: "0x0001 (ACTIVE)", status: "verified" }
          }
        },
        {
          index: 2,
          offset: 304,
          verified: false,
          issues: ["checksum_mismatch"],
          values: {
            sensor_id: { value: null, status: "lost", note: "CRC mismatch: excluded" },
            reading_volts: { value: null, status: "lost", note: "CRC mismatch: excluded" },
            reading_temp_c: { value: null, status: "lost", note: "CRC mismatch: excluded" },
            state_flags: { value: null, status: "lost", note: "CRC mismatch: excluded" }
          }
        },
        {
          index: 3,
          offset: 424,
          verified: true,
          values: {
            sensor_id: { value: 104, status: "verified" },
            reading_volts: { value: 3.425, status: "verified" },
            reading_temp_c: { value: 25.4, status: "verified" },
            state_flags: { value: "0x0001 (ACTIVE)", status: "verified" }
          }
        },
        {
          index: 4,
          offset: 544,
          verified: false,
          issues: ["block_truncated"],
          values: {
            sensor_id: { value: 105, status: "unverified", note: "Block truncated at EOF" },
            reading_volts: { value: 3.402, status: "unverified", note: "Block truncated at EOF" },
            reading_temp_c: { value: 26.0, status: "unverified", note: "Block truncated at EOF" },
            state_flags: { value: null, status: "lost", note: "Field past EOF" }
          }
        }
      ],
      damage: [
        { kind: "checksum_mismatch", offset: 304, length: 120, detail: "Stored 0x31C3 != computed 0x21E2", lossy: true },
        { kind: "truncated", offset: 544, length: 96, detail: "Only 96/120 bytes present", lossy: true },
        { kind: "truncated", offset: 640, length: 384, detail: "File truncated before declared size", lossy: true }
      ]
    },
    // Trace steps for Block 2 (Inside the Machine)
    trace: {
      file: "lab_run_07.dat",
      declared_size: 1024,
      actual_size: 640,
      steps: [
        {
          id: "magic",
          title: "Magic Match",
          icon: "🔍",
          status: "ok",
          plain: "The engine inspected the initial 4 bytes of the file and compared them against the registered format signatures.",
          math: [
            {
              label: "Signature match",
              formula: "bytes[0..k] = registry magic",
              substitution: "4D 4F 43 4B = 4D 4F 43 4B",
              result: "Matched EXAMPLE-LOG signature"
            }
          ],
          byte_ranges: [{ start: 0, end: 4, role: "magic" }],
          consequence: "Identified format as EXAMPLE-LOG with confidence 1.0. Proceeding to header index parsing."
        },
        {
          id: "header",
          title: "Header Parsing",
          icon: "📄",
          status: "ok",
          plain: "Decoded declared file size, block count, and block length using little-endian byte representation.",
          math: [
            {
              label: "Declared size (little-endian)",
              formula: "N_d = ∑ b_i · 256<sup>i</sup>",
              substitution: "Bytes 00 04: 0 + 4 · 256",
              result: "1024 bytes"
            },
            {
              label: "Block specifications",
              formula: "Blocks = count · L",
              substitution: "8 blocks · 120 bytes",
              result: "960 payload bytes (+ 64-byte header)"
            }
          ],
          byte_ranges: [{ start: 0, end: 64, role: "header" }],
          consequence: "Header validated. 64 bytes verified. Partition layout established for 8 records."
        },
        {
          id: "block_offsets",
          title: "Block Offsets",
          icon: "📐",
          status: "ok",
          plain: "Calculated absolute file offsets for records 0 and 1, followed by payload boundary checks.",
          math: [
            {
              label: "Record 0 & 1 offsets",
              formula: "s<sub>k</sub> = H + k · L, e<sub>k</sub> = s<sub>k</sub> + L",
              substitution: "H = 64, L = 120: s<sub>0</sub> = 64, e<sub>0</sub> = 184; s<sub>1</sub> = 184, e<sub>1</sub> = 304",
              result: "Ranges [64, 184) and [184, 304)"
            }
          ],
          byte_ranges: [{ start: 64, end: 304, role: "verified" }],
          consequence: "Blocks 0 and 1 verified against schema with checksum validity."
        },
        {
          id: "validate",
          title: "Checksum Validation",
          icon: "⚠️",
          status: "warn",
          plain: "Each block's stored CRC-16 checksum was compared against a freshly computed CRC-16 over its payload bytes. Block 2 checksum did not match.",
          math: [
            {
              label: "CRC-16 comparison",
              formula: "match if stored = computed",
              substitution: "0x31C3 ⊕ 0x21E2 = 0x1021",
              result: "Mismatch: 3 bits differ"
            }
          ],
          byte_ranges: [{ start: 304, end: 424, role: "damaged" }],
          consequence: "Block 2 rejected: 120 bytes excluded from verified record set."
        },
        {
          id: "resync",
          title: "Stream Resynchronisation",
          icon: "🔄",
          status: "ok",
          plain: "Because block offsets are fixed-stride, the decoder safely resynchronised at offset 424 for Block 3 without domino failure.",
          math: [
            {
              label: "Next block stride",
              formula: "s<sub>3</sub> = 64 + 3 · 120",
              substitution: "64 + 360 = 424, e<sub>3</sub> = 544",
              result: "Valid block boundary at 424"
            }
          ],
          byte_ranges: [{ start: 424, end: 544, role: "verified" }],
          consequence: "Block 3 verified: 120 bytes recovered and added to verified output."
        },
        {
          id: "bounds_check",
          title: "Bounds Check",
          icon: "✂️",
          status: "warn",
          plain: "Evaluated whether Block 4 fits within actual physical file size before attempting full decoding.",
          math: [
            {
              label: "Bounds inequality",
              formula: "s<sub>k</sub> + L ≤ N<sub>a</sub>",
              substitution: "544 + 120 = 664 > 640",
              result: "Violated: 664 > 640 (only 96 bytes present)"
            }
          ],
          byte_ranges: [{ start: 544, end: 640, role: "unverified" }],
          consequence: "Block 4 marked unverified; remaining 24 bytes cut off."
        },
        {
          id: "truncation",
          title: "File Truncation",
          icon: "🛑",
          status: "fail",
          plain: "Calculated missing file volume between declared header size and physical EOF.",
          math: [
            {
              label: "Truncated volume",
              formula: "missing = N<sub>d</sub> - N<sub>a</sub>",
              substitution: "1024 - 640",
              result: "384 bytes missing in range [640, 1024)"
            }
          ],
          byte_ranges: [{ start: 640, end: 1024, role: "missing" }],
          consequence: "Blocks 5, 6, and 7 unreadable; flagged in damage table and report.json."
        },
        {
          id: "outcome",
          title: "Recovery Ratio",
          icon: "📊",
          status: "ok",
          plain: "Aggregated verified byte spans against declared volume to determine canonical recovery ratio.",
          math: [
            {
              label: "Recovery ratio calculation",
              formula: "r = verified_bytes / declared_bytes",
              substitution: "(64 + 3 · 120) / 1024 = 424 / 1024",
              result: "0.4141 (41.4%)"
            }
          ],
          byte_ranges: [
            { start: 0, end: 64, role: "header" },
            { start: 64, end: 304, role: "verified" },
            { start: 424, end: 544, role: "verified" }
          ],
          consequence: "Recovery finalized: 424 of 1024 declared bytes verified. Safe exit 0."
        }
      ]
    }
  },
  {
    name: "telemetry_core_01.dat",
    size: 512,
    declared_size: 512,
    format: "LABLOG",
    status: "ok",
    status_label: "Complete",
    status_desc: "Everything decoded and verified.",
    bytes_declared: 512,
    bytes_actual: 512,
    bytes_verified: 512,
    recovered_ratio: 1.0,
    fields_verified: 16,
    fields_unverified: 0,
    damage_count: 0,
    header_size: 32,
    block_count: 4,
    block_size: 120,
    byte_segments: [
      { start: 0, end: 32, role: "header", label: "Header [0, 32)", status: "verified", desc: "LABLOG magic & sample interval verified" },
      { start: 32, end: 152, role: "verified", label: "Block 0 [32, 152)", status: "verified", desc: "CRC-16 valid, 120 bytes" },
      { start: 152, end: 272, role: "verified", label: "Block 1 [152, 272)", status: "verified", desc: "CRC-16 valid, 120 bytes" },
      { start: 272, end: 392, role: "verified", label: "Block 2 [272, 392)", status: "verified", desc: "CRC-16 valid, 120 bytes" },
      { start: 392, end: 512, role: "verified", label: "Block 3 [392, 512)", status: "verified", desc: "CRC-16 valid, 120 bytes" }
    ],
    damage: [],
    result_json: {
      source_file: "telemetry_core_01.dat",
      format: "LABLOG",
      status: "ok",
      metadata: {
        instrument: "THERMO-ARRAY-7",
        sample_interval_ms: 100,
        channels: [
          { index: 0, unit: "deg_C" },
          { index: 1, unit: "kPa" }
        ],
        declared_block_count: 4
      },
      records: [
        { index: 0, sample: 1001, time_ms: 0, values: [21.4, 101.32], verified: true },
        { index: 1, sample: 1002, time_ms: 100, values: [21.5, 101.35], verified: true },
        { index: 2, sample: 1003, time_ms: 200, values: [21.7, 101.31], verified: true },
        { index: 3, sample: 1004, time_ms: 300, values: [21.8, 101.29], verified: true }
      ],
      damage: []
    },
    trace: {
      file: "telemetry_core_01.dat",
      declared_size: 512,
      actual_size: 512,
      steps: [
        {
          id: "magic",
          title: "Magic Match",
          icon: "🔍",
          status: "ok",
          plain: "Matched LABLOG signature bytes 'LABL' at byte offset 0.",
          math: [
            {
              label: "Magic signature",
              formula: "bytes[0..3] = 4C 41 42 4C",
              substitution: "4C 41 42 4C = 4C 41 42 4C",
              result: "Matched LABLOG"
            }
          ],
          byte_ranges: [{ start: 0, end: 4, role: "magic" }],
          consequence: "Identified format as LABLOG with confidence 1.0."
        },
        {
          id: "header",
          title: "Header Parsing",
          icon: "📄",
          status: "ok",
          plain: "Validated header fields, channel count (2), and declared block count (4).",
          math: [
            {
              label: "Total size equation",
              formula: "N_d = H + k · L",
              substitution: "32 + 4 · 120 = 512",
              result: "512 bytes declared"
            }
          ],
          byte_ranges: [{ start: 0, end: 32, role: "header" }],
          consequence: "Header validated. 32 bytes verified."
        },
        {
          id: "checksum",
          title: "CRC-16 Validation",
          icon: "✅",
          status: "ok",
          plain: "All 4 blocks passed CRC-16 integrity checks with zero bit discrepancies.",
          math: [
            {
              label: "All blocks CRC match",
              formula: "stored = computed",
              substitution: "Blocks 0..3: stored == computed",
              result: "4 of 4 blocks verified"
            }
          ],
          byte_ranges: [{ start: 32, end: 512, role: "verified" }],
          consequence: "All 480 payload bytes verified."
        },
        {
          id: "outcome",
          title: "Recovery Ratio",
          icon: "📊",
          status: "ok",
          plain: "Complete recovery achieved. Zero damage detected.",
          math: [
            {
              label: "Recovery ratio",
              formula: "r = verified_bytes / declared_bytes",
              substitution: "512 / 512",
              result: "1.0000 (100.0%)"
            }
          ],
          byte_ranges: [{ start: 0, end: 512, role: "verified" }],
          consequence: "Clean decode. Status 'ok'."
        }
      ]
    }
  },
  {
    name: "unknown_memory_dump.bin",
    size: 2048,
    declared_size: 2048,
    format: "UNKNOWN",
    status: "unrecognized",
    status_label: "Not recognised",
    status_desc: "No format matched. The file was fingerprinted and logged.",
    bytes_declared: 2048,
    bytes_actual: 2048,
    bytes_verified: 0,
    recovered_ratio: 0.0,
    fields_verified: 0,
    fields_unverified: 0,
    damage_count: 1,
    header_size: 0,
    block_count: 0,
    block_size: 0,
    byte_segments: [
      { start: 0, end: 2048, role: "unverified", label: "High Entropy Data [0, 2048)", status: "unverified", desc: "No known signature. Shannon Entropy H = 7.84 bits/byte" }
    ],
    damage: [
      {
        id: 1,
        range: { start: 0, end: 2048 },
        length: 2048,
        cause_code: "UNKNOWN_FORMAT",
        cause_name: "Unknown format",
        block: null,
        detected_symptom: "Initial magic bytes did not match any registered specification; high Shannon entropy (7.84 bits/byte) and 0.04 readable ASCII ratio.",
        explanation: "No known signature matched. The file was fingerprinted (entropy, printable text ratio) and logged in report.json without guessing.",
        evidence: { entropy_bits_per_byte: 7.84, readable_text_ratio: 0.04, first_8_bytes: "D4 9A 12 FF 8C 33 00 E1" },
        outcome: "unverified"
      }
    ],
    result_json: {
      source_file: "unknown_memory_dump.bin",
      format: "UNKNOWN",
      status: "unrecognized",
      metadata: {
        entropy_bits_per_byte: 7.84,
        printable_ratio: 0.04,
        likely_type: "compressed_or_encrypted_blob"
      },
      records: [],
      damage: [
        { kind: "unknown_record", offset: 0, length: 2048, detail: "No format signature matched; entropy 7.84 bits/byte", lossy: true }
      ]
    },
    trace: {
      file: "unknown_memory_dump.bin",
      declared_size: 2048,
      actual_size: 2048,
      steps: [
        {
          id: "magic",
          title: "Magic Comparison",
          icon: "❓",
          status: "fail",
          plain: "The engine scanned the file against all registered magic signatures. No format matched.",
          math: [
            {
              label: "Signature probe",
              formula: "bytes[0..k] ∈ registry_magics",
              substitution: "D4 9A 12 FF ... ∉ registry",
              result: "0 matches"
            }
          ],
          byte_ranges: [{ start: 0, end: 8, role: "damaged" }],
          consequence: "Standard decoders bypassed. Diverting execution to fingerprint analysis branch."
        },
        {
          id: "fingerprint",
          title: "Shannon Entropy Fingerprint",
          icon: "🔬",
          status: "warn",
          plain: "Calculated information entropy across the byte distribution to classify density, combined with printable ASCII string ratio.",
          math: [
            {
              label: "Shannon Entropy",
              formula: "H = - ∑ p(b) · log<sub>2</sub> p(b)",
              substitution: "Over 256 byte frequencies in 2048 bytes",
              result: "H = 7.84 bits per byte"
            },
            {
              label: "Printable ASCII ratio",
              formula: "ratio = printable_bytes / total_bytes",
              substitution: "82 / 2048",
              result: "0.04 (threshold 0.70)"
            }
          ],
          byte_ranges: [{ start: 0, end: 2048, role: "unverified" }],
          consequence: "Identified as high-entropy data (compressed, encrypted, or pseudo-random). No guessing attempted."
        },
        {
          id: "log_report",
          title: "Report Audit Entry",
          icon: "📝",
          status: "ok",
          plain: "Logged fingerprint metrics directly to report.json as 'unrecognized'. Execution completed safely with exit code 0.",
          math: [
            {
              label: "Recovery ratio",
              formula: "r = verified_bytes / declared_bytes",
              substitution: "0 / 2048",
              result: "0.0000 (0.0%)"
            }
          ],
          byte_ranges: [{ start: 0, end: 2048, role: "unverified" }],
          consequence: "No invented records produced. Status logged as unrecognized."
        }
      ]
    }
  }
];

export const MOCK_REPORT = {
  tool_version: "2.0.0",
  run_timestamp: "2026-10-16T14:30:00Z",
  files: [
    { file: "lab_run_07.dat", format: "EXAMPLE-LOG", status: "partial", records: 3, damage: 3 },
    { file: "telemetry_core_01.dat", format: "LABLOG", status: "ok", records: 4, damage: 0 },
    { file: "unknown_memory_dump.bin", format: "UNKNOWN", status: "unrecognized", records: 0, damage: 1 }
  ],
  totals: {
    ok: 1,
    partial: 1,
    unrecognized: 1,
    unsupported: 0,
    failed: 0,
    total_files: 3
  }
};
