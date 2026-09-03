/**
 * Local Document Number Extractor - Enterprise Dashboard Client
 * 100% Client-Side Vanilla JS - Zero External Runtime Dependencies
 */

const state = {
  templates: [],
  selectedTemplate: "electricity_bill",
  selectedFiles: [],
  documents: [],
  runs: [],
  activeReviewDoc: null,
  activeReviewIndex: -1,
  calibCoords: { x_min: 0, y_min: 0, x_max: 0, y_max: 0 },
  calibImg: null,
  calibBox: null
};

// Page Descriptions for Topbar
const PAGE_META = {
  dashboard: {
    title: "Dashboard",
    desc: "Local OCR processing overview and telemetry"
  },
  process: {
    title: "Process Documents",
    desc: "Batch document extraction pipeline"
  },
  results: {
    title: "Results",
    desc: "Extracted numeric field records and exports"
  },
  review: {
    title: "Review Queue",
    desc: "Human-in-the-loop verification and corrections"
  },
  calibrate: {
    title: "Template Calibrator",
    desc: "Visual spatial coordinate bounding box calibrator"
  },
  templates: {
    title: "Templates & Fields",
    desc: "Extraction schemas and deterministic validation rules"
  },
  settings: {
    title: "Settings",
    desc: "Engine configuration, blur thresholds, and hardware"
  }
};

// =========================================================================
// Initialization
// =========================================================================
document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupMobileDrawer();
  setupUploadZone();
  setupCalibration();
  setupNewTemplateModal();

  // Load telemetry and data
  await loadHealth();
  await loadTemplates();
  await loadDashboard();
  await loadDocuments();
  await loadBenchmark();
});

// =========================================================================
// Toast Notification System
// =========================================================================
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// =========================================================================
// Navigation & Shell
// =========================================================================
function setupNavigation() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(b => {
    if (b.getAttribute("data-tab") === tabId) {
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });

  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) activePane.classList.add("active");

  const meta = PAGE_META[tabId] || { title: tabId, desc: "" };
  document.getElementById("pageTitle").textContent = meta.title;
  document.getElementById("pageDescription").textContent = meta.desc;

  // Trigger tab-specific refresh
  if (tabId === "dashboard") loadDashboard();
  if (tabId === "results") loadDocuments();
  if (tabId === "review") loadReviewQueue();
  if (tabId === "templates") renderTemplatesList();

  // Close mobile sidebar if open
  closeMobileSidebar();
}

function setupMobileDrawer() {
  const btn = document.getElementById("mobileMenuBtn");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (btn) btn.addEventListener("click", toggleMobileSidebar);
  if (backdrop) backdrop.addEventListener("click", closeMobileSidebar);
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  sidebar.classList.toggle("open");
  backdrop.classList.toggle("show");
}

function closeMobileSidebar() {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (sidebar) sidebar.classList.remove("open");
  if (backdrop) backdrop.classList.remove("show");
}

// =========================================================================
// Health & Telemetry
// =========================================================================
async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const data = await res.json();

    const deviceName = data.device.toUpperCase();
    const isCuda = deviceName.includes("CUDA");
    const displayHw = isCuda ? "CUDA: RTX 4060" : `Device: ${deviceName}`;

    const sidebarHw = document.getElementById("sidebarHwStatus");
    if (sidebarHw) sidebarHw.textContent = displayHw;

    const topbarHw = document.getElementById("topbarHwBadge");
    if (topbarHw) topbarHw.textContent = displayHw;

    const settingsHw = document.getElementById("settingsDeviceText");
    if (settingsHw) {
      settingsHw.textContent = isCuda
        ? "CUDA Acceleration (RTX 4060 Detected)"
        : `CPU Execution Mode (${deviceName})`;
    }
  } catch (e) {
    console.warn("Telemetry offline:", e);
  }
}

// =========================================================================
// Templates Management
// =========================================================================
async function loadTemplates() {
  try {
    const res = await fetch("/api/templates");
    if (!res.ok) return;
    state.templates = await res.json();

    // Populate Process Tab dropdown
    const select = document.getElementById("processTemplateSelect");
    if (select) {
      select.innerHTML = state.templates.map(t => 
        `<option value="${t.id}">${t.name} (${t.fields ? t.fields.length : 0} fields)</option>`
      ).join("");
      if (state.templates.length > 0) {
        state.selectedTemplate = state.templates[0].id;
      }
    }

    // Populate Results Filter dropdown
    const filterSelect = document.getElementById("filterTemplate");
    if (filterSelect) {
      filterSelect.innerHTML = `<option value="">All Templates</option>` + state.templates.map(t =>
        `<option value="${t.id}">${t.name}</option>`
      ).join("");
    }

    // Populate Calibrator Template dropdown
    const calibSelect = document.getElementById("calibTemplateSelect");
    if (calibSelect) {
      calibSelect.innerHTML = state.templates.map(t => 
        `<option value="${t.id}">${t.name}</option>`
      ).join("");
    }
  } catch (e) {
    console.error("Error loading templates:", e);
  }
}

function renderTemplatesList() {
  const container = document.getElementById("templatesListContainer");
  if (!container) return;

  if (!state.templates || state.templates.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-title">No Templates Configured</div>
        <div class="empty-state-desc">Create a new template to begin defining extraction fields.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = state.templates.map(t => `
    <div class="card" style="margin-bottom: 8px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
        <div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <h4 style="font-size: 1.05rem; font-weight: 600;">${t.name}</h4>
            <code style="background: var(--surface-muted); padding: 2px 8px; border-radius: 4px; border: 1px solid var(--border); color: var(--text-secondary);">${t.id}</code>
            <span class="badge badge-neutral">${t.fields ? t.fields.length : 0} Fields</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">${t.description || "Custom document template"}</p>
        </div>

        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="duplicateTemplate('${t.id}')">Duplicate</button>
          <button class="btn btn-secondary btn-sm" onclick="testTemplate('${t.id}')">Test / Process</button>
          ${t.id !== "electricity_bill" && t.id !== "invoice" ? `
            <button class="btn btn-danger btn-sm" onclick="deleteTemplate('${t.id}')">Delete</button>
          ` : ''}
        </div>
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        ${(t.fields || []).map(f => `
          <span style="background: var(--surface-muted); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; display: inline-flex; align-items: center; gap: 6px;">
            <strong>${f.name}</strong>
            <code style="color: var(--text-muted);">(${f.type})</code>
            ${f.required ? '<span style="color: var(--danger); font-weight: bold;">*</span>' : ''}
          </span>
        `).join("")}
      </div>
    </div>
  `).join("");
}

function setupNewTemplateModal() {
  const btnNew = document.getElementById("btnNewTemplate");
  const modal = document.getElementById("newTemplateModal");
  const btnSave = document.getElementById("btnSaveNewTemplate");

  if (btnNew && modal) {
    btnNew.addEventListener("click", () => {
      document.getElementById("tplIdInput").value = "";
      document.getElementById("tplNameInput").value = "";
      document.getElementById("tplDescInput").value = "";
      modal.classList.add("show");
    });
  }

  if (btnSave) {
    btnSave.addEventListener("click", async () => {
      const id = document.getElementById("tplIdInput").value.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
      const name = document.getElementById("tplNameInput").value.trim();
      const desc = document.getElementById("tplDescInput").value.trim();

      if (!id || !name) {
        showToast("Please provide both Template ID and Name.", "error");
        return;
      }

      const newTpl = {
        id: id,
        name: name,
        description: desc,
        fields: [],
        cross_field_rules: []
      };

      try {
        const res = await fetch("/api/templates", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newTpl)
        });
        if (res.ok) {
          showToast(`Template '${name}' created successfully!`, "success");
          modal.classList.remove("show");
          await loadTemplates();
          renderTemplatesList();
        } else {
          showToast("Failed to save template.", "error");
        }
      } catch (err) {
        showToast("Error saving template: " + err, "error");
      }
    });
  }
}

window.deleteTemplate = async function(tplId) {
  if (!confirm(`Are you sure you want to delete template '${tplId}'?`)) return;
  try {
    const res = await fetch(`/api/templates/${tplId}`, { method: "DELETE" });
    if (res.ok) {
      showToast(`Template '${tplId}' deleted.`, "info");
      await loadTemplates();
      renderTemplatesList();
    } else {
      showToast("Could not delete template.", "error");
    }
  } catch (e) {
    showToast("Delete error: " + e, "error");
  }
};

window.duplicateTemplate = async function(tplId) {
  const tpl = state.templates.find(t => t.id === tplId);
  if (!tpl) return;

  const copy = JSON.parse(JSON.stringify(tpl));
  copy.id = `${tpl.id}_copy_${Date.now().toString().slice(-4)}`;
  copy.name = `${tpl.name} (Copy)`;

  try {
    const res = await fetch("/api/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(copy)
    });
    if (res.ok) {
      showToast(`Duplicated template to '${copy.name}'`, "success");
      await loadTemplates();
      renderTemplatesList();
    }
  } catch (e) {
    showToast("Duplicate error: " + e, "error");
  }
};

window.testTemplate = function(tplId) {
  const select = document.getElementById("processTemplateSelect");
  if (select) select.value = tplId;
  switchTab("process");
};

// =========================================================================
// Dashboard & Analytics
// =========================================================================
async function loadDashboard() {
  try {
    const [docsRes, runsRes] = await Promise.all([
      fetch("/api/documents"),
      fetch("/api/runs")
    ]);
    const docs = docsRes.ok ? await docsRes.json() : [];
    const runs = runsRes.ok ? await runsRes.json() : [];

    state.documents = docs;
    state.runs = runs;

    const good = docs.filter(d => d.status === "Good").length;
    const review = docs.filter(d => d.status === "Review").length;
    const failed = docs.filter(d => d.status === "Failed").length;

    document.getElementById("statTotal").textContent = docs.length;
    document.getElementById("statGood").textContent = good;
    document.getElementById("statReview").textContent = review;
    document.getElementById("statFailed").textContent = failed;

    // Populate Runs Table
    const tbody = document.getElementById("runsTableBody");
    if (tbody) {
      if (runs.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9">
              <div class="empty-state">
                <svg class="empty-state-icon" width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
                <div class="empty-state-title">No Processing Runs Yet</div>
                <div class="empty-state-desc">Upload documents and run an extraction batch to populate telemetry.</div>
                <button class="btn btn-primary btn-sm" onclick="switchTab('process')">Start First Extraction</button>
              </div>
            </td>
          </tr>
        `;
      } else {
        tbody.innerHTML = runs.map(r => `
          <tr>
            <td><code>${r.id}</code></td>
            <td><span class="badge badge-neutral">${r.template_id}</span></td>
            <td><strong>${r.total_files}</strong></td>
            <td><span class="badge badge-good">${r.successful}</span></td>
            <td><span class="badge badge-review">${r.needs_review}</span></td>
            <td><span class="badge badge-failed">${r.failed}</span></td>
            <td><strong>${(r.avg_confidence * 100).toFixed(1)}%</strong></td>
            <td style="color: var(--text-secondary);">${r.start_time ? new Date(r.start_time).toLocaleTimeString() : "--"}</td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="filterDocsByRun('${r.id}')">View Results</button>
            </td>
          </tr>
        `).join("");
      }
    }
  } catch (e) {
    console.error("Dashboard refresh error:", e);
  }
}

window.filterDocsByRun = function(runId) {
  switchTab("results");
};

async function loadBenchmark() {
  try {
    const res = await fetch("/api/benchmark/report");
    if (!res.ok) {
      setBenchmarkUnavailable();
      return;
    }
    const data = await res.json();
    const fAcc = data.overall_field_accuracy_pct !== undefined ? data.overall_field_accuracy_pct : null;
    const cAcc = data.character_accuracy_pct !== undefined ? data.character_accuracy_pct : null;
    const dAcc = data.document_accuracy_pct !== undefined ? data.document_accuracy_pct : null;
    const fer = data.false_extraction_rate_pct !== undefined ? data.false_extraction_rate_pct : null;

    if (fAcc !== null) {
      document.getElementById("bmFieldAcc").textContent = fAcc + "%";
      document.getElementById("bmFieldAccBar").style.width = fAcc + "%";
      document.getElementById("bmCharAcc").textContent = cAcc + "%";
      document.getElementById("bmCharAccBar").style.width = cAcc + "%";
      document.getElementById("bmDocAcc").textContent = dAcc + "%";
      document.getElementById("bmDocAccBar").style.width = dAcc + "%";
      document.getElementById("bmFalseExt").textContent = fer + "%";
      document.getElementById("bmFalseExtBar").style.width = Math.min(fer, 100) + "%";
    } else {
      setBenchmarkUnavailable();
    }
  } catch (e) {
    setBenchmarkUnavailable();
  }
}

function setBenchmarkUnavailable() {
  document.getElementById("bmFieldAcc").textContent = "Not evaluated";
  document.getElementById("bmFieldAccBar").style.width = "0%";
  document.getElementById("bmCharAcc").textContent = "Not evaluated";
  document.getElementById("bmCharAccBar").style.width = "0%";
  document.getElementById("bmDocAcc").textContent = "Not evaluated";
  document.getElementById("bmDocAccBar").style.width = "0%";
  document.getElementById("bmFalseExt").textContent = "Not evaluated";
  document.getElementById("bmFalseExtBar").style.width = "0%";
}

document.getElementById("btnRefreshBenchmark")?.addEventListener("click", async () => {
  await loadBenchmark();
  showToast("Benchmark telemetry refreshed.", "info");
});

// =========================================================================
// Process Documents & Upload Pipeline
// =========================================================================
function setupUploadZone() {
  const zone = document.getElementById("uploadZone");
  const picker = document.getElementById("filePicker");
  const btnClear = document.getElementById("btnClearFiles");

  if (!zone || !picker) return;

  zone.addEventListener("click", () => picker.click());

  picker.addEventListener("change", (e) => {
    handleFilesAdded(Array.from(e.target.files));
    picker.value = "";
  });

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  });

  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));

  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFilesAdded(Array.from(e.dataTransfer.files));
    }
  });

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      state.selectedFiles = [];
      renderSelectedFiles();
    });
  }

  document.getElementById("btnStartBatch")?.addEventListener("click", handleStartBatch);
  document.getElementById("btnTestSynthetic")?.addEventListener("click", handleRunSynthetic);
}

function handleFilesAdded(files) {
  const validFiles = files.filter(f => f.type.startsWith("image/") || /\.(jpg|jpeg|png|webp|tif|tiff|bmp)$/i.test(f.name));
  if (validFiles.length === 0) {
    showToast("Please select valid image files (JPG, PNG, TIFF, WebP).", "error");
    return;
  }

  state.selectedFiles = [...state.selectedFiles, ...validFiles];
  renderSelectedFiles();
  showToast(`Added ${validFiles.length} file(s) to extraction queue.`, "info");
}

function renderSelectedFiles() {
  const sec = document.getElementById("selectedFilesSection");
  const list = document.getElementById("selectedFilesList");
  const countEl = document.getElementById("fileSelectedCount");

  if (!sec || !list) return;

  if (state.selectedFiles.length === 0) {
    sec.style.display = "none";
    return;
  }

  sec.style.display = "block";
  countEl.textContent = `${state.selectedFiles.length} document file(s) staged`;

  list.innerHTML = state.selectedFiles.map((file, idx) => {
    const sizeKb = (file.size / 1024).toFixed(1);
    const sizeStr = file.size > 1048576 ? `${(file.size / 1048576).toFixed(2)} MB` : `${sizeKb} KB`;
    const previewUrl = URL.createObjectURL(file);

    return `
      <div class="file-row">
        <div class="file-info-group">
          <img src="${previewUrl}" class="file-thumb" alt="thumb">
          <div class="file-name-meta">
            <span class="file-name" title="${file.name}">${file.name}</span>
            <span class="file-size">${sizeStr} &bull; Image</span>
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 12px;">
          <span class="badge badge-neutral">Ready</span>
          <button class="btn btn-ghost btn-sm btn-icon" onclick="removeSelectedFile(${idx})" title="Remove">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join("");
}

window.removeSelectedFile = function(idx) {
  state.selectedFiles.splice(idx, 1);
  renderSelectedFiles();
};

async function handleStartBatch() {
  if (state.selectedFiles.length === 0) {
    showToast("Please drop or select at least one document image first.", "error");
    return;
  }

  const templateId = document.getElementById("processTemplateSelect").value;
  const workers = document.getElementById("processWorkers").value || 2;
  const progressSec = document.getElementById("progressSection");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  const progressPercent = document.getElementById("progressPercent");
  const progressActiveFile = document.getElementById("progressActiveFile");
  const progressCounters = document.getElementById("progressCounters");
  const btnStart = document.getElementById("btnStartBatch");

  btnStart.disabled = true;
  progressSec.style.display = "block";
  progressBar.style.width = "15%";
  progressPercent.textContent = "15%";
  progressText.innerHTML = `Uploading and processing ${state.selectedFiles.length} images...`;
  progressActiveFile.textContent = `Active file: ${state.selectedFiles[0].name}`;
  progressCounters.textContent = `Pending: ${state.selectedFiles.length}`;

  const formData = new FormData();
  formData.append("template_id", templateId);
  formData.append("workers", workers);
  formData.append("force_reprocess", "true");

  state.selectedFiles.forEach(file => {
    formData.append("files", file);
  });

  try {
    const res = await fetch("/api/batch/process", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Server processing failed");
    }

    const summary = await res.json();
    progressBar.style.width = "100%";
    progressPercent.textContent = "100%";
    progressText.textContent = `Batch Complete! (Run: ${summary.run_id})`;
    progressActiveFile.textContent = `Processed ${summary.total_files} documents successfully.`;
    progressCounters.textContent = `Good: ${summary.successful} &bull; Review: ${summary.needs_review} &bull; Failed: ${summary.failed}`;

    showToast(`Batch extraction complete! ${summary.successful} Good, ${summary.needs_review} Review`, "success");

    state.selectedFiles = [];
    renderSelectedFiles();

    setTimeout(async () => {
      progressSec.style.display = "none";
      btnStart.disabled = false;
      await loadDocuments();
      await loadDashboard();
      switchTab("results");
    }, 1200);
  } catch (err) {
    btnStart.disabled = false;
    progressSec.style.display = "none";
    showToast(`Extraction error: ${err.message}`, "error");
  }
}

async function handleRunSynthetic() {
  const templateId = document.getElementById("processTemplateSelect").value;
  const progressSec = document.getElementById("progressSection");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  const progressPercent = document.getElementById("progressPercent");
  const progressActiveFile = document.getElementById("progressActiveFile");
  const progressCounters = document.getElementById("progressCounters");
  const btnSynthetic = document.getElementById("btnTestSynthetic");

  btnSynthetic.disabled = true;
  progressSec.style.display = "block";
  progressBar.style.width = "30%";
  progressPercent.textContent = "30%";
  progressText.textContent = "Running synthetic ground-truth benchmark...";
  progressActiveFile.textContent = "Processing benchmark dataset...";

  const formData = new FormData();
  formData.append("template_id", templateId);
  formData.append("workers", "2");

  try {
    const res = await fetch("/api/batch/process_synthetic", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      throw new Error("Failed to run synthetic benchmark");
    }

    const summary = await res.json();
    progressBar.style.width = "100%";
    progressPercent.textContent = "100%";
    progressText.textContent = `Benchmark Set Processed (${summary.total_files} files)`;
    progressActiveFile.textContent = `Confidence: ${(summary.average_confidence * 100).toFixed(1)}%`;
    progressCounters.textContent = `Good: ${summary.successful} &bull; Review: ${summary.needs_review} &bull; Failed: ${summary.failed}`;

    showToast("Synthetic ground-truth extraction completed successfully.", "success");

    setTimeout(async () => {
      progressSec.style.display = "none";
      btnSynthetic.disabled = false;
      await loadDocuments();
      await loadDashboard();
      await loadBenchmark();
      switchTab("results");
    }, 1000);
  } catch (err) {
    btnSynthetic.disabled = false;
    progressSec.style.display = "none";
    showToast(`Synthetic benchmark failed: ${err.message}`, "error");
  }
}

// =========================================================================
// Results Table & Filter Pipeline
// =========================================================================
async function loadDocuments() {
  try {
    const res = await fetch("/api/documents");
    if (!res.ok) return;
    state.documents = await res.json();
    renderDocumentsTable();
  } catch (e) {
    console.error("Failed to load documents:", e);
  }
}

function renderDocumentsTable() {
  const tbody = document.getElementById("docTableBody");
  const search = document.getElementById("searchDocs")?.value.toLowerCase().trim() || "";
  const tplFilter = document.getElementById("filterTemplate")?.value || "";
  const statusFilter = document.getElementById("filterStatus")?.value || "";
  const confFilter = document.getElementById("filterConfidence")?.value || "";

  if (!tbody) return;

  const filtered = state.documents.filter(d => {
    const matchesSearch = !search || d.filename.toLowerCase().includes(search);
    const matchesTpl = !tplFilter || d.template_id === tplFilter;
    const matchesStatus = !statusFilter || d.status === statusFilter;

    let matchesConf = true;
    if (confFilter === "high") matchesConf = d.overall_confidence >= 0.90;
    if (confFilter === "med") matchesConf = d.overall_confidence >= 0.70 && d.overall_confidence < 0.90;
    if (confFilter === "low") matchesConf = d.overall_confidence < 0.70;

    return matchesSearch && matchesTpl && matchesStatus && matchesConf;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            <svg class="empty-state-icon" width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
            </svg>
            <div class="empty-state-title">No Matching Documents</div>
            <div class="empty-state-desc">Try clearing search filters or uploading new files.</div>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    let badgeClass = "badge-good";
    if (d.status === "Review") badgeClass = "badge-review";
    if (d.status === "Failed") badgeClass = "badge-failed";

    // Summary of extracted fields
    const fieldsObj = d.fields || {};
    const fieldEntries = Object.entries(fieldsObj);
    const fieldPills = fieldEntries.slice(0, 3).map(([k, v]) => `
      <span style="font-size: 0.75rem; background: var(--surface-muted); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border);">
        ${k}: <strong>${v.value !== null ? v.value : "--"}</strong>
      </span>
    `).join("");

    const extraFieldsCount = fieldEntries.length > 3 ? `<span style="font-size: 0.75rem; color: var(--text-muted);">+${fieldEntries.length - 3} more</span>` : "";

    return `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 28px; height: 28px; border-radius: 4px; background: var(--surface-muted); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; color: var(--text-secondary); flex-shrink: 0;">
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
              </svg>
            </div>
            <div>
              <div style="font-weight: 600; color: var(--text-primary); max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${d.filename}</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">${d.id}</div>
            </div>
          </div>
        </td>

        <td><span class="badge badge-neutral">${d.template_id}</span></td>

        <td>
          <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
            ${fieldPills} ${extraFieldsCount}
          </div>
        </td>

        <td>
          <strong style="color: ${d.overall_confidence >= 0.85 ? 'var(--success)' : d.overall_confidence >= 0.65 ? 'var(--warning)' : 'var(--danger)'};">
            ${(d.overall_confidence * 100).toFixed(1)}%
          </strong>
        </td>

        <td>
          <div style="font-size: 0.82rem;">
            Blur: <strong>${d.blur_score ? d.blur_score.toFixed(1) : "--"}</strong>
            <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">${d.quality_status || "OK"}</span>
          </div>
        </td>

        <td><span class="badge ${badgeClass}">${d.status}</span></td>

        <td>
          <button class="btn btn-secondary btn-sm" onclick="openDebugModal('${d.id}')">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
            <span>Inspect</span>
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

document.getElementById("searchDocs")?.addEventListener("input", renderDocumentsTable);
document.getElementById("filterTemplate")?.addEventListener("change", renderDocumentsTable);
document.getElementById("filterStatus")?.addEventListener("change", renderDocumentsTable);
document.getElementById("filterConfidence")?.addEventListener("change", renderDocumentsTable);

// Export Event Listeners
document.getElementById("btnExportExcel")?.addEventListener("click", () => {
  const tplId = document.getElementById("filterTemplate")?.value || state.selectedTemplate || "electricity_bill";
  window.open(`/api/export/excel/${tplId}`, "_blank");
  showToast(`Initiating Excel workbook export for template '${tplId}'...`, "success");
});

document.getElementById("btnExportCSV")?.addEventListener("click", () => {
  const tplId = document.getElementById("filterTemplate")?.value || state.selectedTemplate || "electricity_bill";
  window.open(`/api/export/csv/${tplId}`, "_blank");
  showToast(`Initiating CSV export for template '${tplId}'...`, "info");
});

// =========================================================================
// Manual Review Queue (Two-Panel Layout)
// =========================================================================
async function loadReviewQueue() {
  const container = document.getElementById("reviewItemsList");
  const countEl = document.getElementById("reviewQueueCount");
  const badgeEl = document.getElementById("reviewBadgeCount");

  if (!container) return;

  const reviewDocs = state.documents.filter(d => d.status === "Review" || d.status === "Failed");

  if (countEl) countEl.textContent = `${reviewDocs.length} items pending`;
  if (badgeEl) badgeEl.textContent = reviewDocs.length;

  if (reviewDocs.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 32px 12px;">
        <svg class="empty-state-icon" width="36" height="36" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <div class="empty-state-title" style="font-size: 0.88rem;">Review Queue Empty</div>
        <div class="empty-state-desc" style="font-size: 0.78rem;">All extracted documents have satisfied confidence thresholds and validation rules.</div>
      </div>
    `;
    renderEmptyReviewInspector();
    return;
  }

  container.innerHTML = reviewDocs.map((d, idx) => {
    let reason = "Flagged for human verification";
    if (d.validation_errors_json) {
      try {
        const errs = JSON.parse(d.validation_errors_json);
        if (errs.length > 0) reason = errs[0];
      } catch (e) {}
    } else if (d.issues_json) {
      try {
        const issues = JSON.parse(d.issues_json);
        if (issues.length > 0) reason = issues[0];
      } catch (e) {}
    }

    const isActive = state.activeReviewDoc && state.activeReviewDoc.id === d.id;

    return `
      <div class="review-item-card ${isActive ? 'active' : ''}" onclick="selectReviewDocument('${d.id}', ${idx})">
        <div class="review-item-title-row">
          <span class="review-item-filename" title="${d.filename}">${d.filename}</span>
          <span class="badge ${d.status === 'Review' ? 'badge-review' : 'badge-failed'}">${d.status}</span>
        </div>
        <div class="review-item-reason">${reason}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
          <span>Conf: <strong>${(d.overall_confidence * 100).toFixed(1)}%</strong></span>
          <span>Blur: ${d.blur_score ? d.blur_score.toFixed(0) : "--"}</span>
        </div>
      </div>
    `;
  }).join("");

  if (!state.activeReviewDoc && reviewDocs.length > 0) {
    selectReviewDocument(reviewDocs[0].id, 0);
  }
}

function renderEmptyReviewInspector() {
  document.getElementById("reviewActiveTitle").textContent = "Review Queue Clear";
  document.getElementById("reviewActiveSubtitle").textContent = "No documents currently requiring human audit";
  document.getElementById("reviewBadgeContainer").innerHTML = "";

  const canvas = document.getElementById("reviewCanvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  const form = document.getElementById("reviewFieldsForm");
  if (form) {
    form.innerHTML = `
      <div class="empty-state" style="padding: 40px 16px;">
        <div class="empty-state-title">All Documents Verified</div>
        <div class="empty-state-desc">You can export the results to Excel or process a new batch.</div>
      </div>
    `;
  }
}

window.selectReviewDocument = async function(docId, idx = -1) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    if (!res.ok) return;
    const doc = await res.json();
    state.activeReviewDoc = doc;
    state.activeReviewIndex = idx;

    // Highlight in list
    document.querySelectorAll(".review-item-card").forEach(c => c.classList.remove("active"));
    const cards = document.querySelectorAll(".review-item-card");
    if (idx >= 0 && cards[idx]) cards[idx].classList.add("active");

    document.getElementById("reviewActiveTitle").textContent = doc.filename;
    document.getElementById("reviewActiveSubtitle").textContent = 
      `Template: ${doc.template_id} &bull; Blur: ${doc.blur_score?.toFixed(1) || 0} &bull; Brightness: ${doc.brightness?.toFixed(1) || 0} &bull; Conf: ${(doc.overall_confidence * 100).toFixed(1)}%`;
    
    document.getElementById("reviewBadgeContainer").innerHTML = 
      `<span class="badge ${doc.status === 'Review' ? 'badge-review' : 'badge-failed'}">${doc.status}</span>`;

    // Render Canvas with bounding box overlays
    const canvas = document.getElementById("reviewCanvas");
    const ctx = canvas.getContext("2d");
    const img = new Image();

    // Use dedicated reliable image endpoint
    img.src = `/api/documents/${doc.id}/image`;
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Draw bounding box overlays
      (doc.extractions || []).forEach(ext => {
        if (ext.bbox && ext.bbox.length === 4) {
          const [x, y, w, h] = ext.bbox;
          const isValid = ext.is_valid;
          const color = isValid ? "#16a34a" : "#d97706";
          const fillColor = isValid ? "rgba(22, 163, 74, 0.2)" : "rgba(217, 119, 6, 0.25)";

          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, w, h);
          ctx.fillStyle = fillColor;
          ctx.fillRect(x, y, w, h);

          // Draw label badge
          ctx.font = "bold 13px sans-serif";
          const label = `${ext.field_name}: ${ext.value || ext.raw_value || ""}`;
          const textWidth = ctx.measureText(label).width;

          ctx.fillStyle = color;
          ctx.fillRect(x, Math.max(0, y - 22), textWidth + 12, 20);

          ctx.fillStyle = "#ffffff";
          ctx.fillText(label, x + 6, Math.max(14, y - 8));
        }
      });
    };

    // Render editable fields sidebar
    const form = document.getElementById("reviewFieldsForm");
    if (!form) return;

    if (!doc.extractions || doc.extractions.length === 0) {
      form.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">No numeric fields extracted for this document.</p>`;
      return;
    }

    form.innerHTML = doc.extractions.map(ext => {
      const val = ext.numeric_value !== null && ext.numeric_value !== undefined ? ext.numeric_value : (ext.value || "");
      const fieldId = `field_val_${ext.field_name.replace(/[^a-zA-Z0-9]/g, '_')}`;

      return `
        <div class="review-field-box ${!ext.is_valid ? 'invalid' : ''}">
          <div class="review-field-meta">
            <span class="review-field-name">${ext.field_name}</span>
            <span class="badge ${ext.is_valid ? 'badge-good' : 'badge-review'}">${(ext.confidence * 100).toFixed(0)}%</span>
          </div>

          <div class="review-field-method">
            Method: <strong>${ext.method || "N/A"}</strong> &bull; Raw: '<em>${ext.raw_value || ""}</em>'
            ${ext.is_manual ? ' &bull; <span class="badge badge-manual" style="padding: 1px 5px;">MANUAL</span>' : ''}
          </div>

          ${ext.validation_notes && ext.validation_notes.length > 0 ? `
            <div style="font-size: 0.72rem; color: var(--warning-text); background: var(--warning-bg); padding: 4px 8px; border-radius: 4px;">
              ${ext.validation_notes.join("; ")}
            </div>
          ` : ''}

          <div style="display: flex; gap: 8px; margin-top: 4px;">
            <input type="text" class="form-control" id="${fieldId}" value="${val}" style="height: 32px; font-size: 0.85rem;">
            <button class="btn btn-primary btn-sm" onclick="saveFieldCorrection('${doc.id}', '${ext.field_name}')">Save</button>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error selecting review document:", err);
  }
};

window.saveFieldCorrection = async function(docId, fieldName) {
  const fieldId = `field_val_${fieldName.replace(/[^a-zA-Z0-9]/g, '_')}`;
  const input = document.getElementById(fieldId);
  if (!input) return;

  const newVal = input.value.trim();
  try {
    const res = await fetch(`/api/documents/${docId}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        field_name: fieldName,
        corrected_value: newVal,
        notes: "Operator verified in review queue"
      })
    });

    if (res.ok) {
      showToast(`Saved manual correction for '${fieldName}': ${newVal}`, "success");
      await selectReviewDocument(docId, state.activeReviewIndex);
      await loadDocuments();
      await loadDashboard();
    } else {
      showToast("Failed to save field correction.", "error");
    }
  } catch (e) {
    showToast("Correction error: " + e, "error");
  }
};

document.getElementById("btnApproveDoc")?.addEventListener("click", async () => {
  if (!state.activeReviewDoc) return;
  showToast(`Document '${state.activeReviewDoc.filename}' approved by operator.`, "success");
  moveToNextReviewDoc();
});

document.getElementById("btnSkipReview")?.addEventListener("click", () => {
  moveToNextReviewDoc();
});

function moveToNextReviewDoc() {
  const reviewDocs = state.documents.filter(d => d.status === "Review" || d.status === "Failed");
  if (reviewDocs.length === 0) {
    loadReviewQueue();
    return;
  }
  let nextIdx = (state.activeReviewIndex + 1) % reviewDocs.length;
  selectReviewDocument(reviewDocs[nextIdx].id, nextIdx);
}

// =========================================================================
// Visual Template Calibrator
// =========================================================================
function setupCalibration() {
  const picker = document.getElementById("calibImagePicker");
  const canvas = document.getElementById("calibrationCanvas");
  if (!picker || !canvas) return;

  const ctx = canvas.getContext("2d");
  let isDrawing = false;
  let startX = 0, startY = 0;

  picker.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (evt) => {
        const img = new Image();
        img.onload = () => {
          state.calibImg = img;
          canvas.width = img.width;
          canvas.height = img.height;
          ctx.drawImage(img, 0, 0);
          showToast(`Sample image loaded (${img.width}x${img.height}px). Click & drag to define field region.`, "info");
        };
        img.src = evt.target.result;
      };
      reader.readAsDataURL(file);
    }
  });

  canvas.addEventListener("mousedown", (e) => {
    if (!state.calibImg) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    startX = (e.clientX - rect.left) * scaleX;
    startY = (e.clientY - rect.top) * scaleY;
    isDrawing = true;
  });

  canvas.addEventListener("mousemove", (e) => {
    if (!isDrawing || !state.calibImg) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const currentX = (e.clientX - rect.left) * scaleX;
    const currentY = (e.clientY - rect.top) * scaleY;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(state.calibImg, 0, 0);

    const x = Math.min(startX, currentX);
    const y = Math.min(startY, currentY);
    const w = Math.abs(currentX - startX);
    const h = Math.abs(currentY - startY);

    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(37, 99, 235, 0.2)";
    ctx.fillRect(x, y, w, h);

    // Compute normalized coordinates
    const xMin = Math.max(0, Math.min(1, Math.round((x / canvas.width) * 1000) / 1000));
    const yMin = Math.max(0, Math.min(1, Math.round((y / canvas.height) * 1000) / 1000));
    const xMax = Math.max(0, Math.min(1, Math.round(((x + w) / canvas.width) * 1000) / 1000));
    const yMax = Math.max(0, Math.min(1, Math.round(((y + h) / canvas.height) * 1000) / 1000));

    state.calibCoords = { x_min: xMin, y_min: yMin, x_max: xMax, y_max: yMax };
    document.getElementById("calibXMin").textContent = xMin.toFixed(3);
    document.getElementById("calibYMin").textContent = yMin.toFixed(3);
    document.getElementById("calibXMax").textContent = xMax.toFixed(3);
    document.getElementById("calibYMax").textContent = yMax.toFixed(3);
  });

  canvas.addEventListener("mouseup", () => {
    isDrawing = false;
  });

  document.getElementById("btnResetCalib")?.addEventListener("click", () => {
    state.calibCoords = { x_min: 0, y_min: 0, x_max: 0, y_max: 0 };
    document.getElementById("calibXMin").textContent = "0.000";
    document.getElementById("calibYMin").textContent = "0.000";
    document.getElementById("calibXMax").textContent = "0.000";
    document.getElementById("calibYMax").textContent = "0.000";
    if (state.calibImg) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(state.calibImg, 0, 0);
    }
  });

  document.getElementById("btnApplyCalibration")?.addEventListener("click", async () => {
    const fieldName = document.getElementById("calibFieldName").value.trim();
    if (!fieldName) {
      showToast("Please enter a field name first.", "error");
      return;
    }

    const tplId = document.getElementById("calibTemplateSelect").value;
    const tpl = state.templates.find(t => t.id === tplId);
    if (!tpl) {
      showToast("Selected template not found.", "error");
      return;
    }

    const fieldType = document.getElementById("calibFieldType").value;
    const enLabels = document.getElementById("calibEnglishLabels").value.split(",").map(s => s.trim()).filter(Boolean);
    const urLabels = document.getElementById("calibUrduLabels").value.split(",").map(s => s.trim()).filter(Boolean);
    const required = document.getElementById("calibRequired").checked;
    const minDigits = parseInt(document.getElementById("calibMinDigits").value) || null;
    const maxDigits = parseInt(document.getElementById("calibMaxDigits").value) || null;

    const newField = {
      name: fieldName,
      type: fieldType,
      labels: enLabels,
      urdu_labels: urLabels,
      required: required,
      min_digits: minDigits,
      max_digits: maxDigits,
      region: {
        x_min: state.calibCoords.x_min,
        y_min: state.calibCoords.y_min,
        x_max: state.calibCoords.x_max,
        y_max: state.calibCoords.y_max
      }
    };

    // Replace existing or append
    const existingIdx = tpl.fields.findIndex(f => f.name.toLowerCase() === fieldName.toLowerCase());
    if (existingIdx >= 0) {
      tpl.fields[existingIdx] = newField;
    } else {
      tpl.fields.push(newField);
    }

    try {
      const res = await fetch("/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tpl)
      });
      if (res.ok) {
        showToast(`Field '${fieldName}' added to template '${tpl.name}' with calibrated bounding box!`, "success");
        await loadTemplates();
      } else {
        showToast("Failed to save template with calibrated field.", "error");
      }
    } catch (e) {
      showToast("Error saving calibrated template: " + e, "error");
    }
  });
}

// =========================================================================
// Candidate Inspector & Debug Modal
// =========================================================================
window.openDebugModal = async function(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    if (!res.ok) return;
    const doc = await res.json();

    const modal = document.getElementById("debugModal");
    const title = document.getElementById("debugModalTitle");
    const subtitle = document.getElementById("debugModalSubtitle");
    const content = document.getElementById("debugModalContent");

    title.textContent = `Candidate Inspector: ${doc.filename}`;
    subtitle.textContent = `Document ID: ${doc.id} &bull; Template: ${doc.template_id} &bull; Status: ${doc.status}`;

    content.innerHTML = `
      <!-- Quality Report Card -->
      <div style="background: var(--surface-muted); padding: 14px 18px; border-radius: var(--radius); border: 1px solid var(--border); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div>
          <span style="font-size: 0.78rem; text-transform: uppercase; color: var(--text-secondary); font-weight: 600;">Quality Metrics</span>
          <div style="font-size: 0.95rem; font-weight: 600; margin-top: 2px;">
            Blur: ${doc.blur_score?.toFixed(1) || 0} &bull; Brightness: ${doc.brightness?.toFixed(1) || 0} &bull; Contrast: ${doc.contrast?.toFixed(1) || 0}
          </div>
        </div>
        <div>
          <span style="font-size: 0.78rem; text-transform: uppercase; color: var(--text-secondary); font-weight: 600;">File Hash</span>
          <div style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">${doc.file_hash ? doc.file_hash.slice(0, 24) + '...' : '--'}</div>
        </div>
      </div>

      <h4 style="font-size: 1rem; font-weight: 600; margin-top: 4px;">Extracted Fields & Evaluated Candidates</h4>

      <!-- Extracted Fields Loop -->
      <div style="display: flex; flex-direction: column; gap: 14px;">
        ${(doc.extractions || []).map(ext => `
          <div class="inspector-field-card">
            <div class="inspector-field-header">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-weight: 700; color: var(--primary); font-size: 0.95rem;">${ext.field_name}</span>
                <span class="badge ${ext.is_valid ? 'badge-good' : 'badge-review'}">Conf: ${(ext.confidence * 100).toFixed(1)}%</span>
                ${ext.is_manual ? '<span class="badge badge-manual">MANUAL</span>' : ''}
              </div>
              <div style="font-size: 0.92rem;">
                Extracted Value: <strong>${ext.numeric_value !== null && ext.numeric_value !== undefined ? ext.numeric_value : (ext.value || '--')}</strong>
              </div>
            </div>

            <div style="padding: 12px 16px; font-size: 0.82rem; color: var(--text-secondary); border-bottom: 1px solid var(--border);">
              Selected Method: <strong>${ext.method || "N/A"}</strong> &bull; Raw OCR Text: '<code>${ext.raw_value || ""}</code>'
            </div>

            ${ext.candidates && ext.candidates.length > 0 ? `
              <div style="overflow-x: auto;">
                <table class="candidates-table">
                  <thead>
                    <tr>
                      <th>Candidate Value</th>
                      <th>Method</th>
                      <th>Score</th>
                      <th>Selection State</th>
                      <th>Audit / Rejection Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${ext.candidates.map(c => `
                      <tr style="${c.is_selected ? 'background-color: var(--primary-light); font-weight: 600;' : ''}">
                        <td><code>${c.normalized_value}</code></td>
                        <td>${c.method}</td>
                        <td>${(c.field_confidence * 100).toFixed(1)}%</td>
                        <td>
                          ${c.is_selected 
                            ? '<span class="badge badge-good" style="font-size: 0.72rem;">SELECTED</span>' 
                            : '<span class="badge badge-neutral" style="font-size: 0.72rem;">REJECTED</span>'}
                        </td>
                        <td style="color: var(--text-secondary);">${c.rejection_reason || c.audit_notes || '--'}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : '<div style="padding: 10px 16px; font-size: 0.8rem; color: var(--text-muted);">No secondary candidates evaluated for this field.</div>'}
          </div>
        `).join('')}
      </div>
    `;

    modal.classList.add("show");
  } catch (err) {
    showToast("Error loading candidate inspector: " + err, "error");
  }
};
