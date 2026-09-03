// Local Document Number Extractor - Frontend Client Application
// 100% Client-side vanilla JS, zero external dependencies

const state = {
  templates: [],
  selectedTemplate: "electricity_bill",
  selectedFiles: [],
  documents: [],
  activeReviewDoc: null,
  calibCoords: { x_min: 0, y_min: 0, x_max: 0, y_max: 0 },
  calibImg: null
};

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupUploadZone();
  setupCalibration();
  await loadHealth();
  await loadTemplates();
  await loadDashboard();
  await loadDocuments();
  await loadBenchmark();
});

// -------------------------------------------------------------
// Navigation
// -------------------------------------------------------------
function setupNavigation() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const tabId = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
      const activePane = document.getElementById(`tab-${tabId}`);
      if (activePane) activePane.classList.add("active");

      document.getElementById("pageTitle").textContent = btn.innerText.trim();

      if (tabId === "dashboard") loadDashboard();
      if (tabId === "results") loadDocuments();
      if (tabId === "review") loadReviewQueue();
      if (tabId === "templates") renderTemplatesList();
    });
  });
}

// -------------------------------------------------------------
// Health & Stats
// -------------------------------------------------------------
async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const hw = document.getElementById("hardwareStatus");
    if (hw) {
      hw.textContent = `Device: ${data.device.toUpperCase()} ? 100% Local & Offline`;
    }
  } catch (e) {
    console.error("Health check failed:", e);
  }
}

async function loadTemplates() {
  try {
    const res = await fetch("/api/templates");
    state.templates = await res.json();

    const select = document.getElementById("processTemplateSelect");
    if (select) {
      select.innerHTML = state.templates.map(t => 
        `<option value="${t.id}">${t.name} (${t.id})</option>`
      ).join("");
    }
  } catch (e) {
    console.error("Error loading templates:", e);
  }
}

async function loadDashboard() {
  try {
    const [docsRes, runsRes] = await Promise.all([
      fetch("/api/documents"),
      fetch("/api/runs")
    ]);
    const docs = await docsRes.json();
    const runs = await runsRes.json();

    state.documents = docs;

    const good = docs.filter(d => d.status === "Good").length;
    const review = docs.filter(d => d.status === "Review").length;
    const failed = docs.filter(d => d.status === "Failed").length;

    document.getElementById("statTotal").textContent = docs.length;
    document.getElementById("statGood").textContent = good;
    document.getElementById("statReview").textContent = review;
    document.getElementById("statFailed").textContent = failed;

    // Populate runs table
    const tbody = document.querySelector("#runsTable tbody");
    if (tbody) {
      if (runs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">No runs recorded yet.</td></tr>`;
      } else {
        tbody.innerHTML = runs.map(r => `
          <tr>
            <td><code>${r.id}</code></td>
            <td>${r.template_id}</td>
            <td>${r.total_files}</td>
            <td><span class="badge badge-good">${r.successful}</span></td>
            <td><span class="badge badge-review">${r.needs_review}</span></td>
            <td><span class="badge badge-failed">${r.failed}</span></td>
            <td>${(r.avg_confidence * 100).toFixed(1)}%</td>
            <td>${r.start_time ? new Date(r.start_time).toLocaleTimeString() : "--"}</td>
          </tr>
        `).join("");
      }
    }
  } catch (e) {
    console.error("Dashboard load failed:", e);
  }
}

async function loadBenchmark() {
  try {
    const res = await fetch("/api/benchmark/report");
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("bmFieldAcc").textContent = (data.overall_field_accuracy_pct || 0) + "%";
    document.getElementById("bmCharAcc").textContent = (data.character_accuracy_pct || 0) + "%";
    document.getElementById("bmDocAcc").textContent = (data.document_accuracy_pct || 0) + "%";
    document.getElementById("bmFalseExt").textContent = (data.false_extraction_rate_pct || 0) + "%";
  } catch (e) {
    console.log("Benchmark not yet loaded:", e);
  }
}

document.getElementById("btnRefreshBenchmark")?.addEventListener("click", loadBenchmark);

// -------------------------------------------------------------
// Document Upload & Batch Processing
// -------------------------------------------------------------
function setupUploadZone() {
  const zone = document.getElementById("uploadZone");
  const picker = document.getElementById("filePicker");
  if (!zone || !picker) return;

  zone.addEventListener("click", () => picker.click());
  picker.addEventListener("change", (e) => {
    state.selectedFiles = Array.from(e.target.files);
    updateSelectedCount();
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
      state.selectedFiles = Array.from(e.dataTransfer.files);
      updateSelectedCount();
    }
  });

  document.getElementById("btnStartBatch")?.addEventListener("click", handleStartBatch);
  document.getElementById("btnTestSynthetic")?.addEventListener("click", handleRunSynthetic);
}

function updateSelectedCount() {
  const el = document.getElementById("fileSelectedCount");
  if (el) {
    el.textContent = `${state.selectedFiles.length} file(s) selected`;
  }
}

async function handleStartBatch() {
  if (state.selectedFiles.length === 0) {
    alert("Please select at least one document image first.");
    return;
  }

  const templateId = document.getElementById("processTemplateSelect").value;
  const workers = document.getElementById("processWorkers").value || 2;
  const progressSec = document.getElementById("progressSection");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");

  progressSec.style.display = "block";
  progressBar.style.width = "30%";
  progressText.textContent = `Uploading and processing ${state.selectedFiles.length} images...`;

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
    const summary = await res.json();
    progressBar.style.width = "100%";
    progressText.textContent = `Processing Complete! (Run ID: ${summary.run_id})`;

    setTimeout(async () => {
      progressSec.style.display = "none";
      await loadDocuments();
      await loadDashboard();
      // Switch to results tab
      document.querySelector('[data-tab="results"]').click();
    }, 1200);
  } catch (err) {
    alert("Batch processing error: " + err);
    progressSec.style.display = "none";
  }
}

async function handleRunSynthetic() {
  const templateId = document.getElementById("processTemplateSelect").value;
  const progressSec = document.getElementById("progressSection");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");

  progressSec.style.display = "block";
  progressBar.style.width = "40%";
  progressText.textContent = "Running synthetic ground-truth benchmark...";

  const formData = new FormData();
  formData.append("template_id", templateId);
  formData.append("workers", "2");

  try {
    const res = await fetch("/api/batch/process_synthetic", {
      method: "POST",
      body: formData
    });
    const summary = await res.json();
    progressBar.style.width = "100%";
    progressText.textContent = `Benchmark Complete! (${summary.total_files} files processed)`;

    setTimeout(async () => {
      progressSec.style.display = "none";
      await loadDocuments();
      await loadDashboard();
      document.querySelector('[data-tab="results"]').click();
    }, 1000);
  } catch (err) {
    alert("Synthetic run failed: " + err);
    progressSec.style.display = "none";
  }
}

// -------------------------------------------------------------
// Results Table
// -------------------------------------------------------------
async function loadDocuments() {
  try {
    const res = await fetch("/api/documents");
    state.documents = await res.json();
    renderDocumentsTable();
  } catch (e) {
    console.error("Failed to load documents:", e);
  }
}

function renderDocumentsTable() {
  const tbody = document.getElementById("docTableBody");
  const search = document.getElementById("searchDocs")?.value.toLowerCase() || "";
  const filter = document.getElementById("filterStatus")?.value || "";

  if (!tbody) return;

  const filtered = state.documents.filter(d => {
    const matchesSearch = d.filename.toLowerCase().includes(search);
    const matchesStatus = filter ? d.status === filter : true;
    return matchesSearch && matchesStatus;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No matching documents.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    let badgeClass = "badge-good";
    if (d.status === "Review") badgeClass = "badge-review";
    if (d.status === "Failed") badgeClass = "badge-failed";

    return `
      <tr>
        <td><strong>${d.filename}</strong></td>
        <td><span class="badge ${badgeClass}">${d.status}</span></td>
        <td>${(d.overall_confidence * 100).toFixed(1)}%</td>
        <td>${d.blur_score ? d.blur_score.toFixed(1) : "--"}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.8rem;" onclick="openDebugModal('${d.id}')">Inspect / Debug</button>
        </td>
      </tr>
    `;
  }).join("");
}

document.getElementById("searchDocs")?.addEventListener("input", renderDocumentsTable);
document.getElementById("filterStatus")?.addEventListener("change", renderDocumentsTable);

// -------------------------------------------------------------
// Exports
// -------------------------------------------------------------
document.getElementById("btnExportExcel")?.addEventListener("click", () => {
  const tplId = state.selectedTemplate || "electricity_bill";
  window.open(`/api/export/excel/${tplId}`, "_blank");
});

document.getElementById("btnExportCSV")?.addEventListener("click", () => {
  const tplId = state.selectedTemplate || "electricity_bill";
  alert("Exporting CSV for current batch...");
  window.open(`/api/export/excel/${tplId}`, "_blank");
});

// -------------------------------------------------------------
// Debug Inspector Modal
// -------------------------------------------------------------
window.openDebugModal = async function(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    const doc = await res.json();

    const modal = document.getElementById("debugModal");
    const title = document.getElementById("debugModalTitle");
    const content = document.getElementById("debugModalContent");

    title.textContent = `Inspector: ${doc.filename} (Status: ${doc.status})`;

    content.innerHTML = `
      <div style="background: var(--bg-main); padding: 14px; border-radius: 8px; border: 1px solid var(--border);">
        <strong>Quality Report:</strong> Blur: ${doc.blur_score?.toFixed(1) || 0} | Brightness: ${doc.brightness?.toFixed(1) || 0} | Contrast: ${doc.contrast?.toFixed(1) || 0}
        <br><span style="color: var(--text-muted); font-size: 0.85rem;">File Hash: ${doc.file_hash}</span>
      </div>

      <h4 style="font-size: 0.95rem; margin-top: 10px;">Extracted Fields & Extraction Candidates</h4>
      <div style="display: flex; flex-direction: column; gap: 12px;">
        ${doc.extractions.map(ext => `
          <div style="background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-weight: 600; color: var(--accent);">${ext.field_name}</span>
              <span><strong>Value:</strong> ${ext.numeric_value !== null ? ext.numeric_value : ext.value}</span>
              <span class="badge ${ext.is_valid ? 'badge-good' : 'badge-review'}">Confidence: ${(ext.confidence * 100).toFixed(1)}%</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              <strong>Method:</strong> ${ext.method || "N/A"} | <strong>Raw Value:</strong> '${ext.raw_value}'
              ${ext.is_manual ? ' | <span class="badge badge-manual">MANUAL CORRECTION</span>' : ''}
            </div>
            ${ext.candidates && ext.candidates.length > 0 ? `
              <div style="margin-top: 8px; border-top: 1px solid var(--border); padding-top: 6px; font-size: 0.78rem;">
                <strong>Evaluated Candidates (${ext.candidates.length}):</strong>
                <ul style="padding-left: 20px; margin-top: 4px; color: var(--text-secondary);">
                  ${ext.candidates.map(c => `
                    <li>Value: <code>${c.normalized_value}</code> | Score: ${(c.field_confidence * 100).toFixed(1)}% | Method: ${c.method} ${c.rejection_reason ? `(Rejected: ${c.rejection_reason})` : ''}</li>
                  `).join('')}
                </ul>
              </div>
            ` : ''}
          </div>
        `).join('')}
      </div>
    `;

    modal.classList.add("show");
  } catch (err) {
    alert("Error loading inspector: " + err);
  }
};

// -------------------------------------------------------------
// Manual Review Queue
// -------------------------------------------------------------
async function loadReviewQueue() {
  const container = document.getElementById("reviewItemsList");
  if (!container) return;

  const reviewDocs = state.documents.filter(d => d.status === "Review" || d.status === "Failed");

  if (reviewDocs.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem;">No items currently in review queue.</p>`;
    return;
  }

  container.innerHTML = reviewDocs.map(d => `
    <div style="padding: 10px 12px; border-radius: 8px; background: var(--bg-main); border: 1px solid var(--border); cursor: pointer;" onclick="selectReviewDocument('${d.id}')">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.88rem; font-weight: 500;">${d.filename}</span>
        <span class="badge ${d.status === 'Review' ? 'badge-review' : 'badge-failed'}">${d.status}</span>
      </div>
      <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">Conf: ${(d.overall_confidence * 100).toFixed(1)}%</div>
    </div>
  `).join("");

  if (reviewDocs.length > 0 && !state.activeReviewDoc) {
    selectReviewDocument(reviewDocs[0].id);
  }
}

window.selectReviewDocument = async function(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    const doc = await res.json();
    state.activeReviewDoc = doc;

    document.getElementById("reviewActiveTitle").textContent = doc.filename;
    document.getElementById("reviewActiveSubtitle").textContent = `Blur: ${doc.blur_score?.toFixed(1) || 0} ? Confidence: ${(doc.overall_confidence * 100).toFixed(1)}%`;
    document.getElementById("reviewBadgeContainer").innerHTML = `<span class="badge ${doc.status === 'Review' ? 'badge-review' : 'badge-failed'}">${doc.status}</span>`;

    // Render Canvas & bounding box overlays
    const canvas = document.getElementById("reviewCanvas");
    const ctx = canvas.getContext("2d");
    const img = new Image();
    
    // Choose original or synthetic path
    const cleanFilename = doc.filename;
    img.src = `/static/synthetic/${cleanFilename}`;
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Draw bounding box overlays
      doc.extractions.forEach(ext => {
        if (ext.bbox && ext.bbox.length === 4) {
          const [x, y, w, h] = ext.bbox;
          ctx.strokeStyle = ext.is_valid ? "#10b981" : "#f59e0b";
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, w, h);

          ctx.fillStyle = ext.is_valid ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)";
          ctx.fillRect(x, y, w, h);

          // Label text
          ctx.fillStyle = "#fff";
          ctx.font = "bold 14px sans-serif";
          ctx.fillText(ext.field_name, x, Math.max(16, y - 6));
        }
      });
    };

    // Render editable field form
    const formContainer = document.getElementById("reviewFieldsForm");
    formContainer.innerHTML = doc.extractions.map(ext => {
      const val = ext.numeric_value !== null ? ext.numeric_value : (ext.value || "");
      return `
        <div style="background: var(--bg-main); padding: 12px; border-radius: 8px; border: 1px solid var(--border);">
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <label style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);">${ext.field_name}</label>
            <span style="font-size: 0.75rem; color: ${ext.is_valid ? 'var(--success)' : 'var(--warning)'};">${(ext.confidence * 100).toFixed(0)}%</span>
          </div>
          <div style="display: flex; gap: 8px;">
            <input type="text" id="field_val_${ext.field_name.replace(/\s+/g, '_')}" value="${val}" style="flex: 1; padding: 8px 10px; border-radius: 6px; background: var(--bg-card); border: 1px solid var(--border); color: #fff;">
            <button class="btn btn-primary" style="padding: 6px 12px; font-size: 0.8rem;" onclick="saveFieldCorrection('${doc.id}', '${ext.field_name}')">Save</button>
          </div>
          ${ext.is_manual ? '<div style="margin-top: 4px;"><span class="badge badge-manual">MANUAL</span></div>' : ''}
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error selecting review doc:", err);
  }
};

window.saveFieldCorrection = async function(docId, fieldName) {
  const inputId = `field_val_${fieldName.replace(/\s+/g, '_')}`;
  const input = document.getElementById(inputId);
  if (!input) return;

  const newVal = input.value;
  try {
    const res = await fetch(`/api/documents/${docId}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        field_name: fieldName,
        corrected_value: newVal,
        notes: "Operator verified correction"
      })
    });
    const data = await res.json();
    alert(`Saved manual correction for ${fieldName}: ${newVal}`);
    await selectReviewDocument(docId);
    await loadDocuments();
  } catch (e) {
    alert("Failed to save correction: " + e);
  }
};

// -------------------------------------------------------------
// Visual Template Calibration Tool
// -------------------------------------------------------------
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

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(59, 130, 246, 0.25)";
    ctx.fillRect(x, y, w, h);

    // Update normalized coords
    const xMin = Math.round((x / canvas.width) * 1000) / 1000;
    const yMin = Math.round((y / canvas.height) * 1000) / 1000;
    const xMax = Math.round(((x + w) / canvas.width) * 1000) / 1000;
    const yMax = Math.round(((y + h) / canvas.height) * 1000) / 1000;

    state.calibCoords = { x_min: xMin, y_min: yMin, x_max: xMax, y_max: yMax };
    document.getElementById("calibXMin").textContent = xMin.toFixed(3);
    document.getElementById("calibYMin").textContent = yMin.toFixed(3);
    document.getElementById("calibXMax").textContent = xMax.toFixed(3);
    document.getElementById("calibYMax").textContent = yMax.toFixed(3);
  });

  canvas.addEventListener("mouseup", () => {
    isDrawing = false;
  });

  document.getElementById("btnApplyCalibration")?.addEventListener("click", () => {
    const fieldName = document.getElementById("calibFieldName").value;
    if (!fieldName) {
      alert("Please enter a field name.");
      return;
    }
    alert(`Region calibrated for '${fieldName}': [${state.calibCoords.x_min}, ${state.calibCoords.y_min}, ${state.calibCoords.x_max}, ${state.calibCoords.y_max}]. Ready to add to template.`);
  });
}

// -------------------------------------------------------------
// Templates Tab
// -------------------------------------------------------------
function renderTemplatesList() {
  const container = document.getElementById("templatesListContainer");
  if (!container) return;

  container.innerHTML = state.templates.map(t => `
    <div style="background: var(--bg-main); border: 1px solid var(--border); border-radius: 10px; padding: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h4 style="font-size: 1.05rem; font-weight: 600;">${t.name} (<code>${t.id}</code>)</h4>
        <span class="badge badge-good">${t.fields.length} Fields</span>
      </div>
      <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 14px;">${t.description}</p>
      
      <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        ${t.fields.map(f => `
          <span style="background: var(--bg-card); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; font-size: 0.8rem;">
            ${f.name} <code style="color: var(--text-muted);">(${f.type})</code>
          </span>
        `).join("")}
      </div>
    </div>
  `).join("");
}
