# Salvage Frontend Architecture & Implementation Plan

**Project:** Genesis 2.0 · PS 02 — Legacy File Recovery  
**Target:** 100% Offline, Zero-Dependency Web Frontend & Python Standard-Library Local Bridge  
**Design:** Dedicated Light Theme (Clean, calm, high-contrast, WCAG AA compliant)  
**Reference:** Antigravity Brief: Salvage Frontend (14-page specification)

---

## 1. Architectural Principles & Non-Negotiables

1. **100% Offline & Zero External Assets:**
   - No external fonts (Google Fonts, etc.) — styled with a native high-quality system font stack (`system-ui`, `-apple-system`, `Segoe UI`, `Roboto`, `Consolas`, `ui-monospace`).
   - Zero CDNs, zero third-party script tags, zero telemetry, zero AI/LLM API calls.
   - Plain HTML5, Modern Vanilla CSS (CSS variables, Flexbox/Grid), and ES Modules with **no build step required**.
2. **Dedicated Pure Light Theme:**
   - Designed strictly around a clean, calm, professional light theme palette (crisp whites, subtle slate borders, high-contrast typography, carefully tuned status chips).
   - No theme toggling — single, cohesive, distraction-free visual design.
3. **Data Integrity & Honesty:**
   - Real Mode: Every figure, status, and byte offset comes directly from the backend.
   - Mock Mode: Clear, unmistakable **`MOCK DATA`** ribbon/badge visible whenever mock fixtures are displayed.
   - Never mark any field as verified unless the backend explicitly declares it verified.
   - Plain language damage wording: `Probable cause` and `Detected symptom` (strictly never infer real-world hardware causes like failing disk).
4. **In-Memory File Safety:**
   - Uploaded files are processed in-memory or streamed directly to the ephemeral job directory on `127.0.0.1`.
   - Never write file contents to `localStorage`, `IndexedDB`, or cookies.
   - "Clear session" wipes all browser state and issues `DELETE /api/jobs/{id}` to clean up backend temp files.
5. **No Hard-Coded Formats:**
   - The frontend reads supported formats dynamically from the backend (`GET /api/formats`).

---

## 2. Page Structure & Component Breakdown

```
+--------------------------------------------------------------------------------------------------+
| HEADER STRIP (Light Theme)                                                                       |
| [Genesis 2.0 · Salvage]  [🛡️ Offline: Runs on this computer]  [Mode: Real/Mock]  [Clear session] |
+-------------------------------------------------+------------------------------------------------+
| BLOCK 1: Recover your files (~45%)              | BLOCK 2: Inside the machine (~55%)             |
|                                                 |                                                |
| 1. Upload & Drag-Drop Zone                      | 1. Interactive Pipeline Stepper                |
|    - Browse / Drop zone (25MB/file, 50 max)     |    - Step nodes with icons & status            |
|    - [Recover files] button + progress bar      |    - [⏮ Prev] [▶ Play / ⏸ Pause] [⏭ Next]      |
|                                                 |                                                |
| 2. Results List (1 row per file)                | 2. Step Detail Panel (4 Parts)                 |
|    - Name, size, detected format, status chip   |    (1) What happened (plain explanation)       |
|    - Verified vs. unverified field metrics      |    (2) Math computation card (formula, values) |
|    - Recovery progress bar                      |    (3) Active byte map with highlighted roles  |
|                                                 |    (4) Output consequence / excluded bytes     |
| 3. Expanded Row View                            |                                                |
|    - Byte Map (verified, unverified, damage)    | 3. Final Outcome Card                          |
|    - Damage Table (range, cause, symptom, etc.) |    - Recovery ratio equation:                  |
|    - Lightweight Syntax-Colored JSON Preview    |      r = verified_bytes / declared_bytes       |
|    - Download Links (JSON, Damage TXT, ZIP)     |                                                |
+-------------------------------------------------+------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### A. Header & Global State
- **Brand Title:** `Genesis 2.0 · Salvage` with subtitle `Legacy Binary Record Recovery`.
- **Offline Indicator Badge:** Clean badge reading `"Runs on this computer. Your files never leave it."`
- **Session Controls:**
  - `Clear session` button (resets memory state and triggers backend cleanup).
  - Mode selector (`Real Server (127.0.0.1)` vs `Interactive Mock Mode` with visible `MOCK DATA` ribbon).
  - Theme: Fixed clean light theme (neutral slates, crisp whites, and distinct accent colors).

### B. Block 1: File Recovery & Results
- **Drop Zone:**
  - Drag-over active states, keyboard accessible file selector.
  - Limits clearly displayed: `Max 25 MB per file` and `50 files per job`.
  - Batch action: `Recover files` with aggregate and per-file progress indicators.
- **Results Table / Card Rows:**
  - File name, file size (formatted KB/MB), detected format (or `"Not recognised"`).
  - Status chip combining icon + text (WCAG AA compliant):
    - `Complete` (Checkmark icon)
    - `Partial` (Warning triangle icon)
    - `Not recognised` (Search/Question icon)
    - `Could not process` (Shield/Error icon)
  - Recovery ratio mini-bar & counts of `Verified` vs `Unverified` fields.
- **Row Expansion (Selected File):**
  - **Byte Map:** Proportional horizontal strip mapped to declared size with segments color-coded by role:
    - Verified (Emerald green `#059669`)
    - Unverified (Amber orange `#d97706`)
    - Damaged (Crimson red `#dc2626`)
    - Missing / Truncated (Slate dashed `#94a3b8`)
  - **Damage Table:**
    - Columns: `#`, `Byte range [start, end)`, `Length`, `Probable cause`, `Detected symptom`, `Outcome`.
    - Bi-directional interactivity: Hovering or clicking a table row highlights the corresponding segment in the byte map, and hovering a byte map segment highlights the table row.
  - **Decoded JSON Inspector:**
    - Custom lightweight syntax highlighting (brackets, keys, strings, numbers, booleans) without external libraries.
    - Verified / Unverified badge next to each record field.
    - Copy JSON to clipboard button.
  - **Action Downloads:**
    - File level: `Result (JSON)`, `Damage Log (JSON)`, `Damage Log (TXT)`. (Shows `"No damage found"` if 0 damage).
    - Job level: `report.json` and `Download everything (ZIP)`.

### C. Block 2: Inside the Machine (Inspection & Step Math)
- **Trace Stepper Pipeline:**
  - Nodes dynamically generated from the trace (`magic`, `fingerprint`, `header`, `index`, `decompress`, `deobfuscate`, `decode_fields`, `validate`, `outcome`).
  - Node status badges: `ok`, `warn`, `fail`, `skipped`.
  - Step player: `Previous`, `Play / Pause` (with 2-second auto-advance loop), `Next`.
  - Respects `prefers-reduced-motion` media query (disables smooth animations and instantly jumps between steps).
- **Step Detail Cards:**
  1. **What Happened:** Clear, concise 1-2 sentence description.
  2. **The Math Card:** Monospace typography with Unicode symbols (`∑`, `⊕`, `·`, `≤`) and HTML `<sub>`/`<sup>`:
     - Label, general formula, concrete substitution with real file numbers, and evaluated result.
  3. **Step Byte Map:** Visualizing the specific byte span touched or evaluated by this step.
  4. **Output Consequence:** Explicit impact on output (e.g., `Block 2 rejected, 120 bytes excluded`).
- **Unrecognised File Flow:**
  - Shows explicit branching: Magic comparison fails -> Fingerprinting (Shannon Entropy $H = -\sum p(b)\log_2 p(b)$ and readable text ratio) -> Logged to `report.json` -> Decoding halted safely.
- **Outcome Card:**
  - Displays canonical recovery ratio formula: $r = \frac{\text{bytes\_verified}}{\text{declared\_bytes}} = \dots\%$.

---

## 4. Mock Scenarios & Fixtures (from Brief Page 9 & 10)

1. **`lab_run_07.dat` (Partial with Damage & Truncation):**
   - Format: `EXAMPLE-LOG`, Declared: 1024 bytes, Actual: 640 bytes. Header: 64 bytes, 8 blocks of 120 bytes.
   - Header `[0, 64)`: verified.
   - Block 0 `[64, 184)` & Block 1 `[184, 304)`: verified.
   - Block 2 `[304, 424)`: damaged, `CHECKSUM_MISMATCH` (stored `0x31C3`, computed `0x21E2`).
   - Block 3 `[424, 544)`: verified (resynchronised after corrupt block).
   - Block 4 `[544, 640)`: 96 of 120 bytes present, `BLOCK_TRUNCATED`.
   - `[640, 1024)`: missing, `FILE_TRUNCATED`, 384 bytes.
2. **`telemetry_core_01.dat` (Complete):**
   - 100% verified, 0 damage, valid checksums.
3. **`unknown_memory_dump.bin` (Not Recognised):**
   - Magic comparison fails, Shannon Entropy $H = 7.82$ bits/byte, logged in `report.json`.

---

## 5. Local Bridge Server (`server.py`) Specification

A lightweight, zero-dependency Python script using `http.server`, `urllib`, and `subprocess`:
- **Host & Port:** `127.0.0.1:8000` (strictly localhost).
- **Safety Measures:**
  - Path traversal defense: validates file names via `os.path.basename`.
  - Max limits enforced: 25 MB per file, 50 files per job.
  - Ephemeral isolation: Temp directory per job (`tempfile.mkdtemp(prefix="salvage_job_")`).
  - Automatic cleanup on `DELETE /api/jobs/{id}` and age timeout (> 1 hour).
- **Endpoints:**
  - `GET /` & static assets: Serves `index.html`, `styles.css`, `app.js`, etc.
  - `GET /api/health` -> `{"status": "ok", "offline": true, "version": "1.0.0"}`
  - `GET /api/formats` -> returns formats dynamically discovered from `salvage.formats` registry.
  - `POST /api/jobs` -> multipart/form-data upload, invokes CLI via `python -m salvage <in_dir> <out_dir>`, generates trace & report.
  - `GET /api/jobs/{id}` -> status summary per file.
  - `GET /api/jobs/{id}/files/{name}/result` -> JSON result.
  - `GET /api/jobs/{id}/files/{name}/damage.json` & `.txt` -> damage log.
  - `GET /api/jobs/{id}/files/{name}/trace` -> detailed step trace for Block 2.
  - `GET /api/jobs/{id}/report.json` & `/download.zip` -> full job package.
  - `DELETE /api/jobs/{id}` -> deletes temp job folder and returns `204 No Content`.

---

## 6. Implementation Phases

- **Phase 1: Foundation & Scaffold:**
  - Create project folder structure (`frontend/`).
  - Implement light theme design tokens in `styles.css` (color scales, typography, WCAG AA contrast).
  - Implement mock data fixtures (`mock-data.js`).
- **Phase 2: Block 1 UI (File Recovery & Results):**
  - Drag-and-drop file upload with limits and validation.
  - File results table with status chips, progress bars, and metrics.
  - Row expansion: Interactive Byte Map, Damage Table with cross-hover highlighting, and Syntax-highlighted JSON viewer.
- **Phase 3: Block 2 UI (Inside the Machine):**
  - Pipeline trace stepper with Play/Pause animation engine.
  - 4-part step detail panel (plain description, math computation cards, active byte span, consequence).
  - Special flow for unrecognised files (entropy branch).
  - Recovery ratio outcome equation card.
- **Phase 4: Python Local Bridge (`server.py`):**
  - Implement standard-library HTTP server with all proposed REST routes.
  - Execute `python -m salvage` with isolated temporary folders.
  - Generate full trace metadata for real decoded files.
  - Add ZIP bundling using `zipfile`.
- **Phase 5: Verification & Accessibility Pass:**
  - Verify keyboard accessibility (tab navigation, aria attributes, focus rings).
  - Verify reduced-motion support.
  - Test real runs with actual files from `real-samples/samples` through the bridge.
  - Test completely offline in the browser.
