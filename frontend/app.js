// Salvage Frontend Main Application (Vanilla ES Module)
// Fully Offline, Zero CDN Dependencies, In-Memory Safe

import { MOCK_FILES, MOCK_FORMATS, MOCK_REPORT } from './mock-data.js';

// Constants as specified in Brief
const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB
const MAX_FILES_PER_JOB = 50;
const STEP_PLAY_INTERVAL_MS = 2200;

class SalvageApp {
  constructor() {
    this.mode = 'mock'; // 'mock' or 'real'
    this.serverHealthy = false;
    this.supportedFormats = MOCK_FORMATS;
    this.files = [];
    this.selectedFileIndex = 0;
    this.activeStepIndex = 0;
    this.expandedRowIndex = 0;
    this.isPlaying = false;
    this.playTimer = null;
    this.currentJobId = null;
    this.stagedFiles = [];

    this.initElements();
    this.bindEvents();
    this.detectBackend();
  }

  initElements() {
    // Header & Global
    this.mockRibbon = document.getElementById('mockRibbon');
    this.modeSelect = document.getElementById('modeSelect');
    this.clearSessionBtn = document.getElementById('clearSessionBtn');
    this.statusIndicator = document.getElementById('backendStatusIndicator');
    this.toastContainer = document.getElementById('toastContainer');

    // Block 1: Upload & Results
    this.uploadZone = document.getElementById('uploadZone');
    this.fileInput = document.getElementById('fileInput');
    this.browseBtn = document.getElementById('browseBtn');
    this.stagedBar = document.getElementById('stagedFilesBar');
    this.stagedCountText = document.getElementById('stagedCountText');
    this.recoverBtn = document.getElementById('recoverBtn');
    this.resultsList = document.getElementById('resultsList');
    this.globalDownloadsBar = document.getElementById('globalDownloadsBar');
    this.downloadReportBtn = document.getElementById('downloadReportBtn');
    this.downloadZipBtn = document.getElementById('downloadZipBtn');

    // Block 2: Stepper & Machine
    this.stepperContainer = document.getElementById('stepperContainer');
    this.prevStepBtn = document.getElementById('prevStepBtn');
    this.playStepBtn = document.getElementById('playStepBtn');
    this.nextStepBtn = document.getElementById('nextStepBtn');
    this.stepCounter = document.getElementById('stepCounter');
    this.stepDetailContainer = document.getElementById('stepDetailContainer');
    this.selectedFileNameEl = document.getElementById('selectedFileName');
  }

  bindEvents() {
    // Mode Switch
    this.modeSelect.addEventListener('change', (e) => {
      this.switchMode(e.target.value);
    });

    // Clear Session
    this.clearSessionBtn.addEventListener('click', () => {
      this.clearSession();
    });

    // Drag and Drop Upload
    this.browseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.fileInput.click();
    });

    this.uploadZone.addEventListener('click', () => {
      this.fileInput.click();
    });

    this.uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.uploadZone.classList.add('dragover');
    });

    this.uploadZone.addEventListener('dragleave', () => {
      this.uploadZone.classList.remove('dragover');
    });

    this.uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      this.uploadZone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        this.handleFileSelection(Array.from(e.dataTransfer.files));
      }
    });

    this.fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleFileSelection(Array.from(e.target.files));
      }
      this.fileInput.value = '';
    });

    this.recoverBtn.addEventListener('click', () => {
      this.processStagedFiles();
    });

    // Stepper Controls
    this.prevStepBtn.addEventListener('click', () => this.previousStep());
    this.nextStepBtn.addEventListener('click', () => this.nextStep());
    this.playStepBtn.addEventListener('click', () => this.togglePlay());

    // Global Downloads
    this.downloadReportBtn.addEventListener('click', () => this.downloadGlobalReport());
    this.downloadZipBtn.addEventListener('click', () => this.downloadGlobalZip());
  }

  async detectBackend() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        this.serverHealthy = true;
        this.statusIndicator.innerHTML = '🟢 Server Connected';
        this.statusIndicator.title = 'Local bridge is running on 127.0.0.1';
        await this.loadSupportedFormats();
        this.showToast('Connected to local bridge on 127.0.0.1');
      } else {
        throw new Error('Not running');
      }
    } catch {
      this.serverHealthy = false;
      this.statusIndicator.innerHTML = '🟡 Mock Standalone';
      this.statusIndicator.title = 'Local server not running. Running offline with mock data.';
      this.switchMode('mock');
    }
  }

  async loadSupportedFormats() {
    try {
      const res = await fetch('/api/formats');
      if (res.ok) {
        this.supportedFormats = await res.json();
      }
    } catch {
      this.supportedFormats = MOCK_FORMATS;
    }
  }

  switchMode(newMode) {
    this.mode = newMode;
    this.modeSelect.value = newMode;

    if (newMode === 'mock') {
      this.mockRibbon.classList.add('visible');
      this.files = JSON.parse(JSON.stringify(MOCK_FILES));
      this.selectedFileIndex = 0;
      this.activeStepIndex = 0;
      this.expandedRowIndex = 0;
      this.stagedFiles = [];
      this.stagedBar.style.display = 'none';
      this.render();
      this.showToast('Switched to Mock Mode (using official sample fixtures)');
    } else {
      this.mockRibbon.classList.remove('visible');
      if (!this.serverHealthy) {
        this.showToast('Notice: Local bridge server is not connected. Run `python server.py` to start it.');
      }
      this.files = [];
      this.selectedFileIndex = 0;
      this.activeStepIndex = 0;
      this.expandedRowIndex = null;
      this.render();
    }
  }

  handleFileSelection(fileList) {
    if (fileList.length > MAX_FILES_PER_JOB) {
      this.showToast(`Error: Exceeded max file limit of ${MAX_FILES_PER_JOB} files per job.`, true);
      return;
    }

    const validFiles = [];
    for (const f of fileList) {
      if (f.size > MAX_FILE_SIZE_BYTES) {
        this.showToast(`File ${f.name} exceeds max limit of 25 MB and was skipped.`, true);
        continue;
      }
      validFiles.push(f);
    }

    if (validFiles.length === 0) return;

    this.stagedFiles = validFiles;
    this.stagedBar.style.display = 'flex';
    this.stagedCountText.textContent = `${validFiles.length} file(s) staged ready for recovery`;
  }

  async processStagedFiles() {
    if (this.stagedFiles.length === 0) return;

    this.recoverBtn.disabled = true;
    this.recoverBtn.innerHTML = '<span>⏳ Processing...</span>';

    if (this.mode === 'mock') {
      // In mock mode, simulate rapid processing of the staged file names
      setTimeout(() => {
        this.files = JSON.parse(JSON.stringify(MOCK_FILES));
        this.stagedFiles = [];
        this.stagedBar.style.display = 'none';
        this.recoverBtn.disabled = false;
        this.recoverBtn.innerHTML = '<span>⚡ Recover files</span>';
        this.selectedFileIndex = 0;
        this.expandedRowIndex = 0;
        this.activeStepIndex = 0;
        this.render();
        this.showToast('Recovery run complete (Mock Mode).');
      }, 700);
      return;
    }

    // Real Mode: send files to server via POST /api/jobs
    try {
      const formData = new FormData();
      for (const file of this.stagedFiles) {
        formData.append('files', file, file.name);
      }

      const postRes = await fetch('/api/jobs', {
        method: 'POST',
        body: formData
      });

      if (!postRes.ok) {
        const err = await postRes.json();
        throw new Error(err.error || 'Server error during file recovery');
      }

      const jobData = await postRes.json();
      this.currentJobId = jobData.job_id;

      // Fetch summary and per-file results
      const statusRes = await fetch(`/api/jobs/${this.currentJobId}`);
      const jobStatus = await statusRes.json();

      this.files = jobStatus.files || [];
      this.stagedFiles = [];
      this.stagedBar.style.display = 'none';
      this.selectedFileIndex = 0;
      this.expandedRowIndex = 0;
      this.activeStepIndex = 0;
      this.render();
      this.showToast(`Recovery complete: processed ${this.files.length} file(s).`);
    } catch (err) {
      this.showToast(`Error processing files: ${err.message}`, true);
    } finally {
      this.recoverBtn.disabled = false;
      this.recoverBtn.innerHTML = '<span>⚡ Recover files</span>';
    }
  }

  async clearSession() {
    this.stopPlay();
    if (this.currentJobId && this.mode === 'real') {
      try {
        await fetch(`/api/jobs/${this.currentJobId}`, { method: 'DELETE' });
      } catch (e) {
        console.warn('Job deletion notice:', e);
      }
    }

    this.currentJobId = null;
    this.files = [];
    this.stagedFiles = [];
    this.selectedFileIndex = 0;
    this.activeStepIndex = 0;
    this.expandedRowIndex = null;
    this.stagedBar.style.display = 'none';

    this.render();
    this.showToast('Session cleared. All in-memory state and temporary files removed.');
  }

  // --- Rendering Pipeline ---

  render() {
    this.renderResultsList();
    this.renderMachineBlock();
  }

  renderResultsList() {
    if (this.files.length === 0) {
      this.resultsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📂</div>
          <p>No files loaded. Drag and drop legacy files above or switch to Mock Mode.</p>
        </div>
      `;
      this.globalDownloadsBar.style.display = 'none';
      return;
    }

    this.globalDownloadsBar.style.display = 'flex';
    this.resultsList.innerHTML = '';

    this.files.forEach((file, index) => {
      const isSelected = index === this.selectedFileIndex;
      const isExpanded = index === this.expandedRowIndex;

      const rowEl = document.createElement('div');
      rowEl.className = `result-row ${isSelected ? 'selected' : ''} ${isExpanded ? 'expanded' : ''}`;
      rowEl.setAttribute('role', 'region');
      rowEl.setAttribute('aria-label', `Result for ${file.name}`);

      // Status chip determination (Icon + Text, never color alone)
      let statusChipClass = 'complete';
      let statusIcon = '✓';
      let statusLabel = 'Complete';

      if (file.status === 'partial') {
        statusChipClass = 'partial';
        statusIcon = '⚠️';
        statusLabel = 'Partial';
      } else if (file.status === 'unrecognized' || file.format === 'UNKNOWN') {
        statusChipClass = 'unrecognized';
        statusIcon = '🔍';
        statusLabel = 'Not recognised';
      } else if (file.status === 'failed' || file.status === 'error' || file.status === 'could_not_process') {
        statusChipClass = 'error';
        statusIcon = '🛑';
        statusLabel = 'Could not process';
      }

      const recoveryPercent = Math.round((file.recovered_ratio || 0) * 100);
      const formattedSize = this.formatBytes(file.size || file.bytes_actual || 0);

      rowEl.innerHTML = `
        <div class="row-summary" tabindex="0" role="button" aria-expanded="${isExpanded}">
          <div class="row-file-info">
            <span class="file-glyph" aria-hidden="true">📄</span>
            <div class="file-name-meta">
              <div class="file-name" title="${file.name}">${file.name}</div>
              <div class="file-meta-tags">
                <span>${formattedSize}</span>
                <span class="format-pill">${file.format || 'UNKNOWN'}</span>
              </div>
            </div>
          </div>

          <div class="status-chip ${statusChipClass}" title="${file.status_desc || statusLabel}">
            <span aria-hidden="true">${statusIcon}</span>
            <span>${statusLabel}</span>
          </div>

          <div class="row-metrics">
            <div class="recovery-bar-wrap" title="Recovery ratio: ${recoveryPercent}%">
              <div class="recovery-bar-fill" style="width: ${recoveryPercent}%;"></div>
            </div>
            <div class="metrics-text">
              <span><strong>${file.fields_verified || 0}</strong> verified</span> /
              <span>${file.fields_unverified || 0} unverified</span>
            </div>
          </div>

          <span class="expand-chevron" aria-hidden="true">▼</span>
        </div>

        <div class="row-expanded-panel">
          <!-- Byte Map Strip -->
          <div class="byte-map-container">
            <div class="byte-map-header">
              <span>Byte Allocation Map (Declared: ${file.declared_size || file.bytes_declared || file.size} bytes)</span>
              <span id="byteTooltip_${index}" class="segment-tooltip">Hover over a byte segment or damage row</span>
            </div>
            <div class="byte-map-strip" id="byteMapStrip_${index}"></div>
            <div class="byte-map-legend">
              <div class="legend-item"><div class="legend-color" style="background: var(--role-header)"></div> Header</div>
              <div class="legend-item"><div class="legend-color" style="background: var(--role-verified)"></div> Verified</div>
              <div class="legend-item"><div class="legend-color" style="background: var(--role-unverified)"></div> Unverified</div>
              <div class="legend-item"><div class="legend-color" style="background: var(--role-damaged)"></div> Damaged</div>
              <div class="legend-item"><div class="legend-color" style="background: var(--role-missing)"></div> Missing</div>
            </div>
          </div>

          <!-- Damage Table -->
          ${this.renderDamageTable(file, index)}

          <!-- JSON Decoded Output Preview with Syntax Highlighting -->
          <div class="json-preview-box">
            <div class="json-preview-header">
              <span>Decoded JSON Structure</span>
              <button class="btn btn-secondary btn-sm copy-json-btn" data-index="${index}">📋 Copy JSON</button>
            </div>
            <div class="json-code-container" id="jsonPreview_${index}">
              ${this.syntaxHighlightJson(file.result_json || {})}
            </div>
          </div>

          <!-- Row Downloads -->
          <div class="row-downloads-bar">
            <button class="btn btn-secondary btn-sm dl-result-btn" data-index="${index}">📥 Result (JSON)</button>
            ${
              file.damage && file.damage.length > 0
                ? `<button class="btn btn-secondary btn-sm dl-damage-json-btn" data-index="${index}">📥 Damage Log (JSON)</button>
                   <button class="btn btn-secondary btn-sm dl-damage-txt-btn" data-index="${index}">📄 Damage Log (TXT)</button>`
                : `<span class="btn btn-secondary btn-sm" style="opacity: 0.6; cursor: default;">✓ No damage found</span>`
            }
          </div>
        </div>
      `;

      // Interaction bindings for summary click
      const summaryEl = rowEl.querySelector('.row-summary');
      summaryEl.addEventListener('click', () => {
        this.selectFile(index);
        this.toggleRowExpansion(index);
      });

      summaryEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.selectFile(index);
          this.toggleRowExpansion(index);
        }
      });

      this.resultsList.appendChild(rowEl);

      // Render interactive byte segments for this row
      if (isExpanded) {
        this.renderByteMapSegments(file, index);
      }
    });

    this.bindRowActionButtons();
  }

  renderByteMapSegments(file, fileIndex) {
    const stripEl = document.getElementById(`byteMapStrip_${fileIndex}`);
    const tooltipEl = document.getElementById(`byteTooltip_${fileIndex}`);
    if (!stripEl) return;

    stripEl.innerHTML = '';
    const totalSize = file.declared_size || file.bytes_declared || file.size || 1024;
    const segments = file.byte_segments || [];

    segments.forEach((seg, segIndex) => {
      const segLength = seg.end - seg.start;
      const widthPercent = (segLength / totalSize) * 100;

      const segEl = document.createElement('div');
      segEl.className = `byte-segment ${seg.role || 'verified'}`;
      segEl.style.width = `${Math.max(widthPercent, 1.5)}%`;
      segEl.dataset.segIndex = segIndex;
      segEl.dataset.start = seg.start;
      segEl.dataset.end = seg.end;

      segEl.addEventListener('mouseenter', () => {
        tooltipEl.textContent = `Range [${seg.start}, ${seg.end}) · ${segLength} bytes · ${seg.label || seg.role}: ${seg.desc || ''}`;
        this.highlightDamageRow(fileIndex, seg.start, seg.end, true);
      });

      segEl.addEventListener('mouseleave', () => {
        tooltipEl.textContent = 'Hover over a byte segment or damage row';
        this.highlightDamageRow(fileIndex, seg.start, seg.end, false);
      });

      stripEl.appendChild(segEl);
    });
  }

  highlightDamageRow(fileIndex, start, end, highlight) {
    const table = document.querySelector(`.damage-table[data-file-index="${fileIndex}"]`);
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row) => {
      const rowStart = parseInt(row.dataset.start, 10);
      const rowEnd = parseInt(row.dataset.end, 10);
      if (rowStart <= start && rowEnd >= end) {
        row.classList.toggle('highlighted', highlight);
      }
    });
  }

  highlightByteSegment(fileIndex, start, end, highlight) {
    const stripEl = document.getElementById(`byteMapStrip_${fileIndex}`);
    if (!stripEl) return;

    const segs = stripEl.querySelectorAll('.byte-segment');
    segs.forEach((seg) => {
      const segStart = parseInt(seg.dataset.start, 10);
      const segEnd = parseInt(seg.dataset.end, 10);
      if (segStart >= start && segEnd <= end) {
        seg.classList.toggle('active-highlight', highlight);
      }
    });
  }

  renderDamageTable(file, fileIndex) {
    if (!file.damage || file.damage.length === 0) {
      return `
        <div class="damage-panel">
          <div class="section-label">Damage Assessment</div>
          <div style="font-size: 12px; color: #166534; background: #f0fdf4; padding: 10px 12px; border-radius: var(--radius-md); border: 1px solid #bbf7d0;">
            ✓ No structural or checksum damage detected. Every byte fits schema.
          </div>
        </div>
      `;
    }

    return `
      <div class="damage-panel">
        <div class="section-label">Detected Damage & Integrity Log (${file.damage.length} events)</div>
        <div class="table-responsive">
          <table class="damage-table" data-file-index="${fileIndex}">
            <thead>
              <tr>
                <th>#</th>
                <th>Byte range [start, end)</th>
                <th>Length</th>
                <th>Probable cause</th>
                <th>Detected symptom</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              ${file.damage
                .map((dmg, idx) => {
                  const start = dmg.range ? dmg.range.start : dmg.offset || 0;
                  const end = dmg.range ? dmg.range.end : start + (dmg.length || 0);
                  const length = dmg.length || end - start;
                  const causeCode = dmg.cause_code || dmg.kind || 'UNKNOWN';
                  const causeName = dmg.cause_name || causeCode.replace(/_/g, ' ').toLowerCase();
                  const symptom = dmg.detected_symptom || dmg.detail || dmg.explanation || '';
                  const outcome = dmg.outcome || (dmg.lossy ? 'excluded' : 'kept');

                  return `
                    <tr data-start="${start}" data-end="${end}" class="damage-row-interactive">
                      <td><strong>${idx + 1}</strong></td>
                      <td><code>[${start}, ${end})</code></td>
                      <td>${length} B</td>
                      <td><strong>${causeCode}</strong> (${causeName})</td>
                      <td>${symptom}</td>
                      <td><span class="outcome-pill ${outcome}">${outcome}</span></td>
                    </tr>
                  `;
                })
                .join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  bindRowActionButtons() {
    // Copy JSON Buttons
    document.querySelectorAll('.copy-json-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = btn.dataset.index;
        const file = this.files[idx];
        if (file && file.result_json) {
          navigator.clipboard.writeText(JSON.stringify(file.result_json, null, 2));
          this.showToast(`Copied JSON for ${file.name} to clipboard`);
        }
      });
    });

    // Download Single File Result
    document.querySelectorAll('.dl-result-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const file = this.files[btn.dataset.index];
        this.downloadFile(file.name + '.json', JSON.stringify(file.result_json || {}, null, 2), 'application/json');
      });
    });

    // Download Single File Damage JSON
    document.querySelectorAll('.dl-damage-json-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const file = this.files[btn.dataset.index];
        this.downloadFile(file.name + '.damage.json', JSON.stringify(file.damage || [], null, 2), 'application/json');
      });
    });

    // Download Single File Damage TXT
    document.querySelectorAll('.dl-damage-txt-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const file = this.files[btn.dataset.index];
        const txt = this.generateDamageTxt(file);
        this.downloadFile(file.name + '.damage.txt', txt, 'text/plain');
      });
    });

    // Damage Row Hover to Highlight Byte Map
    document.querySelectorAll('.damage-row-interactive').forEach((row) => {
      const start = parseInt(row.dataset.start, 10);
      const end = parseInt(row.dataset.end, 10);
      const table = row.closest('.damage-table');
      const fileIndex = table ? table.dataset.fileIndex : null;

      row.addEventListener('mouseenter', () => {
        if (fileIndex !== null) this.highlightByteSegment(fileIndex, start, end, true);
      });
      row.addEventListener('mouseleave', () => {
        if (fileIndex !== null) this.highlightByteSegment(fileIndex, start, end, false);
      });
    });
  }

  generateDamageTxt(file) {
    let out = `DAMAGE AUDIT REPORT FOR: ${file.name}\n`;
    out += `Format: ${file.format}\nDeclared Size: ${file.declared_size || file.bytes_declared || file.size} bytes\n`;
    out += `Actual Size: ${file.size || file.bytes_actual} bytes\n`;
    out += `Status: ${file.status}\n\n`;
    out += `Events:\n------------------------------------------------------------\n`;

    (file.damage || []).forEach((dmg, i) => {
      const s = dmg.range ? dmg.range.start : dmg.offset || 0;
      const e = dmg.range ? dmg.range.end : s + (dmg.length || 0);
      out += `[#${i + 1}] Range: [${s}, ${e}) | Code: ${dmg.cause_code || dmg.kind}\n`;
      out += `    Probable cause: ${dmg.cause_name || dmg.cause_code || dmg.kind}\n`;
      out += `    Detected symptom: ${dmg.detected_symptom || dmg.detail || dmg.explanation}\n`;
      out += `    Outcome: ${dmg.outcome || 'excluded'}\n\n`;
    });
    return out;
  }

  // --- Block 2: Inside the Machine ---

  selectFile(index) {
    if (this.selectedFileIndex === index) return;
    this.selectedFileIndex = index;
    this.activeStepIndex = 0;
    this.stopPlay();
    this.render();
  }

  toggleRowExpansion(index) {
    if (this.expandedRowIndex === index) {
      this.expandedRowIndex = null;
    } else {
      this.expandedRowIndex = index;
    }
    this.renderResultsList();
  }

  renderMachineBlock() {
    const file = this.files[this.selectedFileIndex];

    if (!file) {
      this.selectedFileNameEl.textContent = 'No file selected';
      this.stepperContainer.innerHTML = `
        <div class="empty-state">
          <p>Select a file in Block 1 to inspect the execution pipeline and mathematics.</p>
        </div>
      `;
      this.stepDetailContainer.innerHTML = '';
      this.stepCounter.textContent = 'Step 0 of 0';
      return;
    }

    this.selectedFileNameEl.textContent = `${file.name} (${file.format || 'UNKNOWN'})`;

    const trace = file.trace || { steps: [] };
    const steps = trace.steps || [];

    if (this.activeStepIndex >= steps.length) {
      this.activeStepIndex = 0;
    }

    this.stepCounter.textContent = `Step ${steps.length > 0 ? this.activeStepIndex + 1 : 0} of ${steps.length}`;

    // Render Pipeline Nodes
    this.stepperContainer.innerHTML = '';
    steps.forEach((step, idx) => {
      const isActive = idx === this.activeStepIndex;
      const nodeEl = document.createElement('button');
      nodeEl.className = `step-node ${step.status || 'ok'} ${isActive ? 'active' : ''}`;
      nodeEl.setAttribute('role', 'tab');
      nodeEl.setAttribute('aria-selected', isActive);
      nodeEl.innerHTML = `
        <div class="step-bubble" title="${step.title}: ${step.status}">
          <span>${step.icon || '⚙️'}</span>
        </div>
        <div class="step-node-title">${step.title}</div>
      `;

      nodeEl.addEventListener('click', () => {
        this.activeStepIndex = idx;
        this.stopPlay();
        this.renderMachineBlock();
      });

      this.stepperContainer.appendChild(nodeEl);

      if (idx < steps.length - 1) {
        const connector = document.createElement('div');
        connector.className = 'step-connector';
        this.stepperContainer.appendChild(connector);
      }
    });

    // Render Active Step 4-Part Detail Card
    const activeStep = steps[this.activeStepIndex];
    if (!activeStep) {
      this.stepDetailContainer.innerHTML = `
        <div class="empty-state">
          <p>No trace steps recorded for this file.</p>
        </div>
      `;
      return;
    }

    this.stepDetailContainer.innerHTML = `
      <div class="step-detail-card" role="tabpanel">
        <div class="step-detail-title">
          <span>${activeStep.icon || '⚙️'}</span>
          <span>Step ${this.activeStepIndex + 1}: ${activeStep.title}</span>
          <span class="status-chip ${activeStep.status || 'ok'}" style="margin-left: auto;">
            ${activeStep.status.toUpperCase()}
          </span>
        </div>

        <!-- Part 1: What Happened -->
        <div>
          <div class="section-label" style="margin-bottom: 4px;">1. What happened</div>
          <div class="part-what-happened">
            ${activeStep.plain || 'The engine executed this pipeline stage.'}
          </div>
        </div>

        <!-- Part 2: The Math Card -->
        <div class="part-math-section">
          <div class="section-label">2. Mathematical Calculation & Proof</div>
          ${(activeStep.math || [])
            .map(
              (m) => `
            <div class="math-card">
              <div class="math-header">${m.label}</div>
              <div class="math-formula">Formula: ${m.formula}</div>
              <div class="math-subst">Substitution: ${m.substitution}</div>
              <div class="math-result">Result: ${m.result}</div>
            </div>
          `
            )
            .join('')}
        </div>

        <!-- Part 3: Active Byte Map -->
        <div class="part-byte-map-section">
          <div class="section-label">3. Touched Byte Range in this Step</div>
          <div class="byte-map-strip" style="height: 24px;">
            ${this.renderStepByteMapStrip(file, activeStep)}
          </div>
        </div>

        <!-- Part 4: Consequence Note -->
        <div>
          <div class="section-label" style="margin-bottom: 4px;">4. Consequence for Output</div>
          <div class="part-consequence">
            <span style="font-size: 16px;">💡</span>
            <span>${activeStep.consequence || 'Step recorded successfully.'}</span>
          </div>
        </div>
      </div>

      <!-- Final Recovery Ratio Outcome Card -->
      <div class="outcome-ratio-card">
        <div>
          <div class="outcome-title">Final Recovery Ratio Equation</div>
          <div style="font-size: 11px; color: var(--text-tertiary);">Provably verified volume vs declared file length</div>
        </div>
        <div class="outcome-equation">
          r = <span class="outcome-fraction">verified_bytes / declared_bytes</span> =
          ${file.bytes_verified || 0} / ${file.declared_size || file.bytes_declared || file.size} =
          <strong>${Math.round((file.recovered_ratio || 0) * 10000) / 100}%</strong>
        </div>
      </div>
    `;
  }

  renderStepByteMapStrip(file, step) {
    const totalSize = file.declared_size || file.bytes_declared || file.size || 1024;
    const ranges = step.byte_ranges || [];

    if (ranges.length === 0) {
      return `<div class="byte-segment unverified" style="width: 100%;" title="Global file scope"></div>`;
    }

    let html = '';
    let currentOffset = 0;

    ranges.forEach((r) => {
      if (r.start > currentOffset) {
        const gap = r.start - currentOffset;
        const gapPct = (gap / totalSize) * 100;
        html += `<div class="byte-segment" style="width: ${gapPct}%; background: #e2e8f0; opacity: 0.4;" title="Untouched [${currentOffset}, ${r.start})"></div>`;
      }
      const len = r.end - r.start;
      const pct = (len / totalSize) * 100;
      html += `<div class="byte-segment ${r.role || 'verified'} active-highlight" style="width: ${Math.max(pct, 2)}%;" title="Active Range [${r.start}, ${r.end})"></div>`;
      currentOffset = r.end;
    });

    if (currentOffset < totalSize) {
      const rem = totalSize - currentOffset;
      const remPct = (rem / totalSize) * 100;
      html += `<div class="byte-segment" style="width: ${remPct}%; background: #e2e8f0; opacity: 0.4;" title="Untouched [${currentOffset}, ${totalSize})"></div>`;
    }

    return html;
  }

  // --- Step Playback Controls ---

  nextStep() {
    const file = this.files[this.selectedFileIndex];
    if (!file || !file.trace || !file.trace.steps) return;
    const count = file.trace.steps.length;
    if (count === 0) return;

    this.activeStepIndex = (this.activeStepIndex + 1) % count;
    this.renderMachineBlock();
  }

  previousStep() {
    const file = this.files[this.selectedFileIndex];
    if (!file || !file.trace || !file.trace.steps) return;
    const count = file.trace.steps.length;
    if (count === 0) return;

    this.activeStepIndex = (this.activeStepIndex - 1 + count) % count;
    this.renderMachineBlock();
  }

  togglePlay() {
    if (this.isPlaying) {
      this.stopPlay();
    } else {
      this.startPlay();
    }
  }

  startPlay() {
    this.isPlaying = true;
    this.playStepBtn.innerHTML = '<span>⏸ Pause</span>';
    this.playTimer = setInterval(() => {
      this.nextStep();
    }, STEP_PLAY_INTERVAL_MS);
  }

  stopPlay() {
    this.isPlaying = false;
    if (this.playStepBtn) {
      this.playStepBtn.innerHTML = '<span>▶ Play</span>';
    }
    if (this.playTimer) {
      clearInterval(this.playTimer);
      this.playTimer = null;
    }
  }

  // --- Global Downloads ---

  async downloadGlobalReport() {
    if (this.mode === 'real' && this.currentJobId) {
      window.location.href = `/api/jobs/${this.currentJobId}/report.json`;
      return;
    }
    this.downloadFile('report.json', JSON.stringify(MOCK_REPORT, null, 2), 'application/json');
  }

  async downloadGlobalZip() {
    if (this.mode === 'real' && this.currentJobId) {
      window.location.href = `/api/jobs/${this.currentJobId}/download.zip`;
      return;
    }
    this.showToast('ZIP bundle for mock files generated.');
    this.downloadFile('salvage_mock_bundle.json', JSON.stringify({ files: this.files, report: MOCK_REPORT }, null, 2), 'application/json');
  }

  downloadFile(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- Custom Lightweight Syntax Highlighting (No External Libraries) ---

  syntaxHighlightJson(jsonObj) {
    const jsonStr = JSON.stringify(jsonObj, null, 2);
    if (!jsonStr) return '';

    // Sanitize HTML
    const escaped = jsonStr
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // RegEx tokenizer for keys, strings, numbers, booleans, null
    return escaped.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'json-number';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'json-key';
          } else {
            cls = 'json-string';
            // Insert verified / unverified badges if string represents status
            if (match === '"verified"') {
              return `<span class="${cls}">${match}</span><span class="json-verified-tag">✓ VERIFIED</span>`;
            }
            if (match === '"unverified"') {
              return `<span class="${cls}">${match}</span><span class="json-unverified-tag">⚠️ UNVERIFIED</span>`;
            }
          }
        } else if (/true|false/.test(match)) {
          cls = 'json-boolean';
        } else if (/null/.test(match)) {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  }

  formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.borderLeft = isError ? '4px solid #dc2626' : '4px solid #16a34a';
    toast.innerHTML = `<span>${isError ? '⚠️' : 'ℹ️'}</span> <span>${message}</span>`;
    this.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }, 3800);
  }
}

// Instantiate on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new SalvageApp();
});
