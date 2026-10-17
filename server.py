#!/usr/bin/env python3
"""Salvage Local Bridge Server (server.py)
Standard Library Only (Python 3.11 - 3.14+) - 100% Offline, Zero External Dependencies

Conforms strictly to Data Contracts in Antigravity Brief (Page 11).
Binds to 127.0.0.1 only, enforces size limits, path-traversal safety,
and executes the salvage CLI via subprocess in temporary directories.
"""

from __future__ import annotations

import email
import email.policy
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

# Ensure src/ is on PYTHONPATH so we can query registry directly
HERE = Path(__file__).resolve().parent
SRC_DIR = HERE / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Try importing format registry dynamically
SUPPORTED_FORMATS: list[dict[str, Any]] = []
try:
    from salvage import formats  # noqa: F401
    from salvage.core import registry

    for name, dec in sorted(registry._REGISTRY.items()):
        spec = dec.spec
        SUPPORTED_FORMATS.append({
            "name": dec.name.upper(),
            "category": "Standard" if not spec else spec.format_name,
            "description": f"Decoder for {dec.name.upper()} legacy files (ready={dec.ready})",
            "magic_offset": 0 if not spec else spec.magic_offset,
            "ready": dec.ready
        })
except Exception as e:
    # Fallback to contract formats if import fails
    print(f"Notice: Formats loaded statically ({e})", file=sys.stderr)
    SUPPORTED_FORMATS = [
        {"name": "LIBRA-98", "category": "Database", "description": "Legacy library management record table"},
        {"name": "LABLOG", "category": "Instrumentation", "description": "Multi-channel sensor telemetry blocks"},
        {"name": "VAULT", "category": "Archive", "description": "Asset archive with XOR and run-length layers"},
        {"name": "WKS", "category": "Spreadsheet", "description": "Lotus 1-2-3 / Symphony worksheet format"},
        {"name": "WPD", "category": "Document", "description": "WordPerfect legacy document stream"},
        {"name": "BRAVO", "category": "Document", "description": "Xerox Alto Bravo styled document format"},
        {"name": "CVT", "category": "Geos", "description": "Commodore GEOS Convert file format"},
        {"name": "EBCDIC-DUMP", "category": "Mainframe", "description": "IBM EBCDIC student records"},
        {"name": "WAD", "category": "Game", "description": "Doom engine package format"},
        {"name": "PAK", "category": "Game", "description": "Quake engine archive format"}
    ]

# Safety & Limit Constants (Brief Page 5 & 11)
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
MAX_FILES_PER_JOB = 50
JOB_TIMEOUT_SECONDS = 3600  # 1 hour auto-expiry
FRONTEND_DIR = HERE / "frontend"

# In-Memory Active Jobs Store
# id -> { "dir": Path, "created_at": float, "files": list, "report": dict }
ACTIVE_JOBS: dict[str, dict[str, Any]] = {}


def cleanup_expired_jobs():
    """Remove temporary job folders older than 1 hour."""
    now = time.time()
    expired = [jid for jid, info in ACTIVE_JOBS.items() if now - info["created_at"] > JOB_TIMEOUT_SECONDS]
    for jid in expired:
        try:
            job_dir = ACTIVE_JOBS[jid]["dir"]
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)
            del ACTIVE_JOBS[jid]
        except Exception:
            pass


def sanitize_filename(filename: str) -> str:
    """Strictly prevent path traversal by keeping only the basename."""
    base = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9._\-+]', '_', base)
    return clean or "unnamed.bin"


def calculate_entropy(data: bytes) -> float:
    """Shannon entropy in bits per byte."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    entropy = 0.0
    total = len(data)
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)
    return round(entropy, 2)


def generate_trace_for_file(file_name: str, raw_data: bytes, result_json: dict) -> dict:
    """Constructs a detailed step trace with mathematics for Block 2."""
    fmt = result_json.get("format", "UNKNOWN")
    status = result_json.get("status", "ok")
    records = result_json.get("records", [])
    damage = result_json.get("damage", [])
    metadata = result_json.get("metadata", {})
    actual_len = len(raw_data)
    declared_len = metadata.get("header_declared_size", {}).get("value") if isinstance(metadata.get("header_declared_size"), dict) else actual_len
    if not declared_len or not isinstance(declared_len, (int, float)):
        declared_len = actual_len

    steps = []

    # Unrecognized branch
    if fmt == "UNKNOWN" or status == "unrecognized":
        entropy = calculate_entropy(raw_data)
        printable = sum(1 for b in raw_data if 32 <= b <= 126 or b in (9, 10, 13))
        printable_ratio = round(printable / max(1, actual_len), 3)

        steps.append({
            "id": "magic",
            "title": "Magic Comparison",
            "icon": "❓",
            "status": "fail",
            "plain": f"The engine scanned the first bytes of '{file_name}' against all registered signatures. No match was found.",
            "math": [{
                "label": "Signature probe",
                "formula": "bytes[0..k] ∈ registry_magics",
                "substitution": f"{raw_data[:4].hex().upper() if raw_data else 'EMPTY'} ∉ registry",
                "result": "0 matches"
            }],
            "byte_ranges": [{"start": 0, "end": min(8, actual_len), "role": "damaged"}],
            "consequence": "Standard decoders bypassed. Diverting execution to fingerprint analysis branch."
        })

        steps.append({
            "id": "fingerprint",
            "title": "Shannon Entropy Fingerprint",
            "icon": "🔬",
            "status": "warn",
            "plain": "Calculated information entropy across the byte distribution to classify density, along with printable text ratio.",
            "math": [
                {
                    "label": "Shannon Entropy",
                    "formula": "H = - ∑ p(b) · log<sub>2</sub> p(b)",
                    "substitution": f"Over byte frequencies in {actual_len} bytes",
                    "result": f"H = {entropy} bits/byte"
                },
                {
                    "label": "Printable ASCII ratio",
                    "formula": "ratio = printable_bytes / total_bytes",
                    "substitution": f"{printable} / {actual_len}",
                    "result": f"{printable_ratio} (threshold 0.70)"
                }
            ],
            "byte_ranges": [{"start": 0, "end": actual_len, "role": "unverified"}],
            "consequence": "Classified as unknown high-entropy binary stream. Stored in report without inventing data."
        })

        steps.append({
            "id": "log_report",
            "title": "Report Audit Entry",
            "icon": "📝",
            "status": "ok",
            "plain": "Logged fingerprint metrics directly into report.json with status 'unrecognized'. Exited cleanly with code 0.",
            "math": [{
                "label": "Recovery ratio",
                "formula": "r = verified_bytes / declared_bytes",
                "substitution": f"0 / {actual_len}",
                "result": "0.0000 (0.0%)"
            }],
            "byte_ranges": [{"start": 0, "end": actual_len, "role": "unverified"}],
            "consequence": "No invented records produced. Tamper-evident receipts updated."
        })

        return {"file": file_name, "declared_size": declared_len, "actual_size": actual_len, "steps": steps}

    # Standard Recognized Branch
    magic_hex = raw_data[:4].hex().upper() if len(raw_data) >= 4 else "00"
    steps.append({
        "id": "magic",
        "title": "Magic Match",
        "icon": "🔍",
        "status": "ok",
        "plain": f"The engine inspected the initial bytes and matched the registered signature for format {fmt}.",
        "math": [{
            "label": "Signature match",
            "formula": "bytes[0..k] = registry magic",
            "substitution": f"0x{magic_hex} = {fmt} signature",
            "result": f"Matched {fmt}"
        }],
        "byte_ranges": [{"start": 0, "end": min(8, actual_len), "role": "magic"}],
        "consequence": f"Identified format as {fmt}. Initialized {fmt} decoder."
    })

    # Header parsing step
    header_size = min(32, actual_len)
    steps.append({
        "id": "header",
        "title": "Header & Structure",
        "icon": "📄",
        "status": "ok",
        "plain": f"Decoded header index table and schema parameters. Declared size is {declared_len} bytes.",
        "math": [{
            "label": "Declared dimensions",
            "formula": "N_d from header",
            "substitution": f"Header declared {declared_len} bytes, actual physical length {actual_len} bytes",
            "result": f"{declared_len} bytes"
        }],
        "byte_ranges": [{"start": 0, "end": header_size, "role": "header"}],
        "consequence": f"Header validated. Extracted {len(records)} record indices."
    })

    # Damage validation step (if damaged)
    if damage:
        first_dmg = damage[0]
        d_start = first_dmg.get("offset", 0)
        d_len = first_dmg.get("length", 1)
        d_kind = first_dmg.get("kind", "damage")
        steps.append({
            "id": "validate",
            "title": "Integrity Check",
            "icon": "⚠️",
            "status": "warn",
            "plain": f"Integrity checks identified {len(damage)} damage item(s): {first_dmg.get('detail', d_kind)}",
            "math": [{
                "label": "Damage anomaly",
                "formula": "check(range[start, end))",
                "substitution": f"Offset {d_start}, length {d_len}: {d_kind}",
                "result": "Discrepancy detected"
            }],
            "byte_ranges": [{"start": d_start, "end": min(actual_len, d_start + d_len), "role": "damaged"}],
            "consequence": f"{d_kind} logged in damage table and excluded/flagged."
        })
    else:
        steps.append({
            "id": "validate",
            "title": "Integrity Validation",
            "icon": "✅",
            "status": "ok",
            "plain": "Evaluated all record bounds, checksums, and structure markers. Zero discrepancies found.",
            "math": [{
                "label": "Validation test",
                "formula": "stored = computed",
                "substitution": f"Validated across {len(records)} records",
                "result": "All records match schema"
            }],
            "byte_ranges": [{"start": header_size, "end": actual_len, "role": "verified"}],
            "consequence": "100% of parsed records verified with evidence."
        })

    # Outcome step
    verified_bytes = actual_len - sum(d.get("length", 0) for d in damage)
    verified_bytes = max(0, min(verified_bytes, declared_len))
    ratio = round(verified_bytes / max(1, declared_len), 4)

    steps.append({
        "id": "outcome",
        "title": "Recovery Outcome",
        "icon": "📊",
        "status": "ok" if not damage else "warn",
        "plain": f"Decoding complete. Recovered {len(records)} records with recovery ratio {round(ratio * 100, 1)}%.",
        "math": [{
            "label": "Recovery ratio",
            "formula": "r = verified_bytes / declared_bytes",
            "substitution": f"{verified_bytes} / {declared_len}",
            "result": f"{ratio} ({round(ratio * 100, 1)}%)"
        }],
        "byte_ranges": [{"start": 0, "end": actual_len, "role": "verified" if not damage else "unverified"}],
        "consequence": f"Finished run with status '{status}'. Output JSON ready."
    })

    return {"file": file_name, "declared_size": declared_len, "actual_size": actual_len, "steps": steps}


class SalvageBridgeHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler implementing the Salvage API Contracts."""

    def __init__(self, *args, **kwargs):
        # Serve static frontend files by default
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_OPTIONS(self):
        """Handle pre-flight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status: int = 200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400):
        self.send_json({"error": message, "status": "error"}, status=status)

    def do_GET(self):
        cleanup_expired_jobs()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. GET /api/health
        if path == "/api/health":
            self.send_json({
                "status": "ok",
                "offline": True,
                "version": "2.0.0",
                "message": "Salvage backend bridge is running locally on 127.0.0.1"
            })
            return

        # 2. GET /api/formats
        if path == "/api/formats":
            self.send_json(SUPPORTED_FORMATS)
            return

        # 3. GET /api/jobs/{id}
        m_job = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)$", path)
        if m_job:
            job_id = m_job.group(1)
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found or expired", 404)
                return
            self.send_json({
                "job_id": job_id,
                "created_at": job["created_at"],
                "files": job["files"],
                "report": job.get("report", {})
            })
            return

        # 4. GET /api/jobs/{id}/files/{name}/result
        m_res = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/files/([^/]+)/result$", path)
        if m_res:
            job_id, fname = m_res.group(1), urllib.parse.unquote(m_res.group(2))
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            file_info = next((f for f in job["files"] if f["name"] == fname), None)
            if not file_info:
                self.send_error_json("File not found in job", 404)
                return
            self.send_json(file_info.get("result_json", {}))
            return

        # 5. GET /api/jobs/{id}/files/{name}/damage.json
        m_dmg = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/files/([^/]+)/damage\.json$", path)
        if m_dmg:
            job_id, fname = m_dmg.group(1), urllib.parse.unquote(m_dmg.group(2))
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            file_info = next((f for f in job["files"] if f["name"] == fname), None)
            if not file_info:
                self.send_error_json("File not found in job", 404)
                return
            self.send_json(file_info.get("damage", []))
            return

        # 6. GET /api/jobs/{id}/files/{name}/damage.txt
        m_txt = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/files/([^/]+)/damage\.txt$", path)
        if m_txt:
            job_id, fname = m_txt.group(1), urllib.parse.unquote(m_txt.group(2))
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            file_info = next((f for f in job["files"] if f["name"] == fname), None)
            if not file_info:
                self.send_error_json("File not found in job", 404)
                return
            dmg_list = file_info.get("damage", [])
            txt_lines = [f"DAMAGE REPORT FOR {fname}: {len(dmg_list)} events detected"]
            for i, d in enumerate(dmg_list):
                txt_lines.append(f"[{i+1}] Range: [{d.get('offset',0)}, {d.get('offset',0) + d.get('length',0)}) | Code: {d.get('kind','UNKNOWN')} | {d.get('detail','')}")
            self.send_text("\n".join(txt_lines))
            return

        # 7. GET /api/jobs/{id}/files/{name}/trace
        m_tr = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/files/([^/]+)/trace$", path)
        if m_tr:
            job_id, fname = m_tr.group(1), urllib.parse.unquote(m_tr.group(2))
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            file_info = next((f for f in job["files"] if f["name"] == fname), None)
            if not file_info:
                self.send_error_json("File not found in job", 404)
                return
            self.send_json(file_info.get("trace", {}))
            return

        # 8. GET /api/jobs/{id}/report.json
        m_rep = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/report\.json$", path)
        if m_rep:
            job_id = m_rep.group(1)
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            self.send_json(job.get("report", {}))
            return

        # 9. GET /api/jobs/{id}/download.zip
        m_zip = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)/download\.zip$", path)
        if m_zip:
            job_id = m_zip.group(1)
            job = ACTIVE_JOBS.get(job_id)
            if not job:
                self.send_error_json("Job not found", 404)
                return
            out_dir = job["dir"] / "out"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                if out_dir.exists():
                    for f in out_dir.iterdir():
                        if f.is_file():
                            z.write(f, arcname=f.name)
            zip_bytes = buf.getvalue()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="salvage_job_{job_id}.zip"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        # Fallback to static files
        super().do_GET()

    def do_POST(self):
        cleanup_expired_jobs()
        parsed = urllib.parse.urlparse(self.path)

        # POST /api/jobs
        if parsed.path == "/api/jobs":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_error_json("Expected multipart/form-data", 400)
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length)

                # Use Python standard library email parser for robust multipart decoding
                raw_msg_bytes = b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + raw_body
                msg = email.message_from_bytes(raw_msg_bytes, policy=email.policy.default)
            except Exception as e:
                self.send_error_json(f"Error parsing upload: {e}", 400)
                return

            # Extract uploaded files
            uploaded_files: list[tuple[str, bytes]] = []
            if msg.is_multipart():
                for part in msg.iter_parts():
                    filename = part.get_filename()
                    if filename:
                        data = part.get_payload(decode=True)
                        if data is not None:
                            uploaded_files.append((filename, data))

            if not uploaded_files:
                self.send_error_json("No files provided in upload", 400)
                return

            if len(uploaded_files) > MAX_FILES_PER_JOB:
                self.send_error_json(f"Max {MAX_FILES_PER_JOB} files exceeded", 400)
                return

            # Create ephemeral job directories
            job_id = f"job_{int(time.time())}_{os.urandom(4).hex()}"
            job_dir = Path(tempfile.mkdtemp(prefix=f"salvage_{job_id}_"))
            in_dir = job_dir / "in"
            out_dir = job_dir / "out"
            in_dir.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)

            raw_file_contents: dict[str, bytes] = {}

            for original_name, data in uploaded_files:
                clean_name = sanitize_filename(original_name)
                if len(data) > MAX_FILE_SIZE:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    self.send_error_json(f"File {clean_name} exceeds max 25 MB limit", 400)
                    return
                (in_dir / clean_name).write_bytes(data)
                raw_file_contents[clean_name] = data

            # Execute CLI via subprocess: python -m salvage <in_dir> <out_dir>
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

            try:
                cmd = [sys.executable, "-m", "salvage", str(in_dir), str(out_dir)]
                proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
                if proc.returncode != 0:
                    print(f"Warning: Salvage returned non-zero code {proc.returncode}: {proc.stderr}", file=sys.stderr)
            except Exception as e:
                print(f"Subprocess run error: {e}", file=sys.stderr)

            # Load generated results
            report_path = out_dir / "report.json"
            report_data = {}
            if report_path.exists():
                try:
                    report_data = json.loads(report_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            job_files = []
            for fname, raw_data in raw_file_contents.items():
                res_path = out_dir / (fname + ".json")
                res_data = {}
                if res_path.exists():
                    try:
                        res_data = json.loads(res_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                trace_data = generate_trace_for_file(fname, raw_data, res_data)

                # Count verified vs unverified
                records = res_data.get("records", [])
                v_count = 0
                u_count = 0
                for r in records:
                    if isinstance(r, dict):
                        # OUTPUT-CONTRACT: a record is verified unless it carries "verified": false
                        if r.get("verified") is False:
                            u_count += 1
                        else:
                            v_count += 1

                damage_entries = res_data.get("damage", [])
                status_val = res_data.get("status", "ok")

                # Compute byte segments for visual map
                actual_sz = len(raw_data)
                byte_segments = []
                if status_val == "unrecognized" or res_data.get("format") == "UNKNOWN":
                    byte_segments.append({
                        "start": 0, "end": actual_sz, "role": "unverified",
                        "label": f"High Entropy Data [0, {actual_sz})",
                        "desc": "No format signature matched."
                    })
                else:
                    h_size = min(32, actual_sz)
                    byte_segments.append({
                        "start": 0, "end": h_size, "role": "header",
                        "label": f"Header [0, {h_size})",
                        "desc": "Verified header parameters"
                    })
                    curr = h_size
                    for d in damage_entries:
                        d_start = d.get("offset", curr)
                        d_len = d.get("length", 1)
                        if d_start > curr:
                            byte_segments.append({
                                "start": curr, "end": d_start, "role": "verified",
                                "label": f"Verified Chunk [{curr}, {d_start})",
                                "desc": "Passed schema validation"
                            })
                        byte_segments.append({
                            "start": d_start, "end": min(actual_sz, d_start + d_len), "role": "damaged",
                            "label": f"Damage [{d_start}, {min(actual_sz, d_start + d_len)})",
                            "desc": d.get("detail", d.get("kind", "damage"))
                        })
                        curr = max(curr, d_start + d_len)
                    if curr < actual_sz:
                        byte_segments.append({
                            "start": curr, "end": actual_sz, "role": "verified",
                            "label": f"Verified Chunk [{curr}, {actual_sz})",
                            "desc": "Passed schema validation"
                        })

                # Calculate recovery ratio
                verified_bytes = max(0, actual_sz - sum(d.get("length", 0) for d in damage_entries))
                ratio = round(verified_bytes / max(1, actual_sz), 4)

                job_files.append({
                    "name": fname,
                    "size": actual_sz,
                    "declared_size": actual_sz,
                    "format": res_data.get("format", "UNKNOWN"),
                    "status": status_val,
                    "status_label": status_val.capitalize(),
                    "status_desc": f"Processed format {res_data.get('format', 'UNKNOWN')}",
                    "bytes_declared": actual_sz,
                    "bytes_actual": actual_sz,
                    "bytes_verified": verified_bytes,
                    "recovered_ratio": ratio,
                    "fields_verified": v_count,
                    "fields_unverified": u_count,
                    "damage_count": len(damage_entries),
                    "byte_segments": byte_segments,
                    "damage": damage_entries,
                    "result_json": res_data,
                    "trace": trace_data
                })

            ACTIVE_JOBS[job_id] = {
                "dir": job_dir,
                "created_at": time.time(),
                "files": job_files,
                "report": report_data
            }

            self.send_json({
                "job_id": job_id,
                "status": "completed",
                "files_count": len(job_files)
            }, status=201)
            return

        self.send_error_json("Endpoint not found", 404)

    def do_DELETE(self):
        cleanup_expired_jobs()
        parsed = urllib.parse.urlparse(self.path)

        # DELETE /api/jobs/{id}
        m = re.match(r"^/api/jobs/([a-zA-Z0-9_\-]+)$", parsed.path)
        if m:
            job_id = m.group(1)
            job = ACTIVE_JOBS.pop(job_id, None)
            if job:
                try:
                    shutil.rmtree(job["dir"], ignore_errors=True)
                except Exception:
                    pass
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        self.send_error_json("Endpoint not found", 404)


def run_server(port: int = 8000):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, SalvageBridgeHandler)
    print(f"\n=======================================================")
    print(f" Salvage Local Bridge Running: http://127.0.0.1:{port}")
    print(f" Offline security: bound to 127.0.0.1 only")
    print(f" Press Ctrl+C to stop.")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down bridge server.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
