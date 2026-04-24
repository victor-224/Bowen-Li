import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const API_BASE = "http://localhost:5000";
const MM = 0.001;

const statusEl = document.getElementById("status");
const listEl = document.getElementById("equipment-list");
const sceneMetaEl = document.getElementById("scene-meta");
const containerEl = document.getElementById("three-container");
const fileInput = document.getElementById("project-files-input");
const fileDropzone = document.getElementById("file-dropzone");
const fileChips = document.getElementById("file-chips");
const uploadBtn = document.getElementById("load-project-btn");
const loadedNamesEl = document.getElementById("loaded-filenames");
const uploadMsgEl = document.getElementById("upload-feedback");
const processStatusEl = document.getElementById("process-status");
const logPanelEl = document.getElementById("log-panel");
const infoTagEl = document.getElementById("info-tag");
const infoServiceEl = document.getElementById("info-service");
const infoSizeEl = document.getElementById("info-size");
const infoPosEl = document.getElementById("info-pos");
const infoZoneEl = document.getElementById("info-zone");
const infoUpstreamEl = document.getElementById("info-upstream");
const infoDownstreamEl = document.getElementById("info-downstream");
const infoNearestEl = document.getElementById("info-nearest");
const cancelBtn = document.getElementById("cancel-task-btn");
const taskProgressEl = document.getElementById("task-progress");
const taskProgressWrap = document.getElementById("task-progress-wrap");
const copilotInput = document.getElementById("copilot-input");
const copilotOutput = document.getElementById("copilot-output");
const copilotSend = document.getElementById("copilot-send");

let activeTaskId = null;
let _entrySeq = 0;
/** @type {Array<{ id: string, file: File, role: 'layout' | 'equipment' | 'supporting' | 'other', manualOverride: boolean }>} */
let selectedFiles = [];
let lastUserError = "";

const BADGE = {
  layout: { className: "badge badge-layout", label: "Layout plan" },
  equipment: { className: "badge badge-eq", label: "Equipment list" },
  supporting: { className: "badge badge-supp", label: "Supporting docs" },
  other: { className: "badge badge-other", label: "Other" },
};

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.className = isError ? "error" : "";
}

function pushLog(message, level = "info") {
  const ts = new Date().toLocaleTimeString();
  const line = `[${ts}] [${level.toUpperCase()}] ${message}`;
  logPanelEl.textContent = `${line}\n${logPanelEl.textContent}`.slice(0, 16000);
}

function setProcessStatus(message, isError = false) {
  processStatusEl.textContent = message;
  processStatusEl.className = isError ? "error" : "";
}

function setTaskProgress(pct) {
  if (taskProgressEl == null) return;
  const n = Number(pct);
  if (!Number.isFinite(n)) {
    taskProgressEl.removeAttribute("value");
    if (taskProgressWrap) taskProgressWrap.classList.add("empty");
    return;
  }
  taskProgressEl.value = Math.max(0, Math.min(100, n));
  taskProgressEl.setAttribute("value", String(n));
  if (taskProgressWrap) taskProgressWrap.classList.remove("empty");
}

async function fetchJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const body = await res.json().catch(async () => ({ error: await res.text() }));
  if (!res.ok) {
    const structured = body?.error;
    if (structured && typeof structured === "object") {
      throw new Error(
        `${structured.code || "PIPELINE_ERROR"}: ${structured.message || JSON.stringify(structured)}`
      );
    }
    throw new Error(`${path} ${res.status}: ${body.error || JSON.stringify(body)}`);
  }
  return body;
}

function autoClassifyName(filename) {
  const l = filename.toLowerCase();
  if (l.endsWith(".xlsx")) return "equipment";
  if (l.match(/\.(ppt|pptx)$/)) return "supporting";
  const isDraw = l.match(/\.(pdf|png|jpg|jpeg)$/);
  if (isDraw) {
    if (/plan|layout|drawing|gad|floor|plot|iso|general|site|area/.test(l)) return "layout";
    return "supporting";
  }
  return "other";
}

function classifyFile(f) {
  if (f.manualOverride) return f;
  f.role = autoClassifyName(f.file.name);
  return f;
}

function addFilesFromList(fileList) {
  for (const file of fileList) {
    _entrySeq += 1;
    const entry = { id: `f_${_entrySeq}`, file, role: "supporting", manualOverride: false };
    classifyFile(entry);
    selectedFiles.push(entry);
  }
  renderFileChips();
  updateLoadedSummary();
}

function renderFileChips() {
  fileChips.innerHTML = "";
  for (const e of selectedFiles) {
    const li = document.createElement("li");
    li.className = "file-chip";
    li.dataset.id = e.id;
    const badge = BADGE[e.role] || BADGE.other;
    const select = document.createElement("select");
    select.className = "role-select";
    for (const r of ["layout", "equipment", "supporting", "other"]) {
      const o = document.createElement("option");
      o.value = r;
      o.textContent = BADGE[r].label;
      if (e.role === r) o.selected = true;
      select.appendChild(o);
    }
    select.addEventListener("change", () => {
      e.manualOverride = true;
      e.role = select.value;
      renderFileChips();
      updateLoadedSummary();
    });
    const name = document.createElement("span");
    name.className = "fname";
    name.textContent = e.file.name;
    const tag = document.createElement("span");
    tag.className = badge.className;
    tag.textContent = badge.label;
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "icon-btn";
    rm.setAttribute("aria-label", "Remove file");
    rm.textContent = "×";
    rm.addEventListener("click", () => {
      selectedFiles = selectedFiles.filter((x) => x.id !== e.id);
      renderFileChips();
      updateLoadedSummary();
    });
    li.appendChild(name);
    li.appendChild(tag);
    li.appendChild(select);
    li.appendChild(rm);
    fileChips.appendChild(li);
  }
}

function reclassifyAll() {
  for (const e of selectedFiles) {
    if (!e.manualOverride) classifyFile(e);
  }
  renderFileChips();
  updateLoadedSummary();
}

function pickPlanAndExcel() {
  const byLayout = selectedFiles.filter((e) => e.role === "layout" && e.file && !/\.xlsx$/i.test(e.file.name));
  const planEntry = byLayout[0] || selectedFiles.find(
    (e) => e.file && /\.(pdf|png|jpg|jpeg)$/i.test(e.file.name) && !/\.xlsx$/i.test(e.file.name)
  );
  const xlsx = selectedFiles.find((e) => e.file && e.file.name.toLowerCase().endsWith(".xlsx")) || null;
  return { plan: planEntry?.file || null, excel: xlsx?.file || null };
}

function buildUploadForm() {
  const form = new FormData();
  reclassifyAll();
  const { plan, excel } = pickPlanAndExcel();
  if (plan) form.append("plan_file", plan, plan.name);
  if (excel) form.append("excel_file", excel, excel.name);
  const used = new Set();
  if (plan) used.add(plan);
  if (excel) used.add(excel);
  let structureSent = false;
  for (const e of selectedFiles) {
    if (!e.file || used.has(e.file)) continue;
    const n = e.file.name.toLowerCase();
    if (/\.(png|jpg|jpeg)$/.test(n) && !structureSent) {
      form.append("structure_file", e.file, e.file.name);
      structureSent = true;
    } else {
      form.append("reference_file", e.file, e.file.name);
    }
    used.add(e.file);
  }
  return form;
}

function updateLoadedSummary() {
  const n = selectedFiles.length;
  const { plan, excel } = pickPlanAndExcel();
  loadedNamesEl.textContent = `${n} file(s) · Plan: ${plan ? plan.name : "—"} · Excel: ${excel ? excel.name : "—"}`;
}

async function uploadProjectFiles() {
  const form = buildUploadForm();
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success !== true) {
    const reason = body.error || `HTTP ${res.status}`;
    throw new Error(`Upload failed: ${reason}`);
  }
  return body;
}

function stageLabel(status) {
  const map = {
    queued: "Queued",
    validating: "Validating files",
    processing_ocr: "Reading documents",
    parsing_layout: "Parsing layout",
    building_graph: "Building relations",
    rendering_scene: "Rendering scene",
    finalizing: "Finalizing",
    done: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
  };
  return map[status] || status;
}

async function pollTaskUntilDone(taskId, timeoutMs = 180000, abortSignal) {
  const t0 = Date.now();
  let lastMessage = "Starting task";
  let delayMs = 500;
  while (Date.now() - t0 < timeoutMs) {
    if (abortSignal?.aborted) throw new Error("Polling aborted");
    const task = await fetchJson(`/api/task/${encodeURIComponent(taskId)}`);
    const label = stageLabel(task.status);
    const p = task.progress;
    if (p != null && taskProgressEl) setTaskProgress(p);
    lastMessage = `${label}: ${task.message || ""} (${p != null ? p : 0}%)`.trim();
    setProcessStatus(lastMessage);
    if (task.status === "done") {
      if (taskProgressEl) setTaskProgress(100);
      return task;
    }
    if (task.status === "cancelled") throw new Error("Task cancelled by user.");
    if (task.status === "failed") {
      if (taskProgressEl) setTaskProgress(task.progress);
      const detail = task.error;
      if (detail && typeof detail === "object") {
        throw new Error(
          `${detail.code || "PIPELINE_ERROR"}: ${detail.message || "Processing failed"}`
        );
      }
      throw new Error(String(detail || "Processing failed"));
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    delayMs = Math.min(4000, Math.floor(delayMs * 1.5));
  }
  throw new Error(`Processing timeout after ${Math.round(timeoutMs / 1000)}s (${lastMessage})`);
}

async function cancelTask(taskId) {
  const res = await fetch(`${API_BASE}/api/task/${encodeURIComponent(taskId)}/cancel`, { method: "POST" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success !== true) {
    throw new Error(body?.error?.message || body?.error || `Cancel failed (${res.status})`);
  }
  return body;
}

const COPILOT_PRESETS = {
  layout: "Explain the current plant layout: zones, main equipment flow, and what the 3D scene is showing (based on typical refinery or process plant context).",
  risks: "What are plausible safety or layout risk factors in an industrial P&ID-style floor plan (access, clearances, congestion)? Give general professional guidance, not as verified plant facts.",
  optimize: "What placement or routing optimizations are commonly considered for process equipment in plant layout, at a high level?",
  equipment: "Summarize how to read a typical equipment list in Excel (columns like tag, service, size) in this application context.",
  failed: "The user may have a pipeline or upload issue. If context below mentions an error, explain in plain language what it usually means and what to check next. Context:\n",
};

let copilotLoading = false;

function copilotAppend(text) {
  copilotOutput.textContent = text;
}

function copilotOffline() {
  copilotAppend("AI Copilot unavailable (local model offline).");
}

async function callCopilot(message) {
  const m = (message || "").trim();
  if (!m) return;
  if (copilotLoading) return;
  copilotLoading = true;
  copilotOutput.innerHTML = '<span class="copilot-loading">Thinking…</span>';
  try {
    const res = await fetch(`${API_BASE}/api/copilot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: m, context: "industrial-digital-twin" }),
    });
    const data = await res.json().catch(() => ({}));
    if (data && data.success && typeof data.content === "string" && data.content) {
      copilotAppend(data.content);
      return;
    }
    const err = (data && data.error) || "";
    if (String(err).toUpperCase().includes("LM_STUDIO") || res.status >= 500) {
      copilotOffline();
    } else {
      copilotAppend(String(data.error || "Unable to get a response. Check that the app server is running."));
    }
  } catch {
    copilotOffline();
  } finally {
    copilotLoading = false;
  }
}

function renderEquipment(equipment) {
  listEl.innerHTML = "";
  const entries = Object.entries(equipment);
  entries.sort(([a], [b]) => a.localeCompare(b));
  for (const [tag, row] of entries) {
    const li = document.createElement("li");
    const parts = [
      row.service != null ? String(row.service) : "—",
      row.position != null ? `position: ${row.position}` : null,
      row.diameter != null ? `Ø ${row.diameter}` : null,
      row.length != null ? `L ${row.length}` : null,
      row.height != null ? `H ${row.height}` : null,
    ].filter(Boolean);
    li.innerHTML = `<span class="tag">${escapeHtml(tag)}</span>${escapeHtml(parts.join(" · "))}`;
    listEl.appendChild(li);
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function setUploadMessage(text, isError = false) {
  uploadMsgEl.textContent = text;
  uploadMsgEl.className = isError ? "error" : "";
}

function num(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function makeMaterial(seed) {
  const h = (seed * 0.13) % 1;
  return new THREE.MeshStandardMaterial({
    color: new THREE.Color().setHSL(h, 0.45, 0.55),
    metalness: 0.2,
    roughness: 0.65,
  });
}

function hashCode(s) {
  let h = 0;
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

function materialByTag(tag) {
  const seed = (hashCode(String(tag || "")) % 1000) / 1000;
  return makeMaterial(seed);
}

function dims(row) {
  const d = row.dimensions || {};
  return {
    diameter: num(row.diameter ?? d.diameter, 2000),
    length: num(row.length ?? d.length, 3000),
    height: num(row.height ?? d.height, 2000),
  };
}

function buildMesh(geometryType, row) {
  const { diameter: d, length: L, height: H } = dims(row);
  const gt = geometryType || "cylinder";
  if (gt === "Compressor" || gt === "box") {
    const w = d * MM;
    const h = H * MM;
    const dep = L * MM;
    const geom = new THREE.BoxGeometry(w, h, dep);
    return new THREE.Mesh(geom, materialByTag(row.tag));
  }
  if (gt === "Exchanger" || gt === "cylinder_horizontal") {
    const r = (d / 2) * MM;
    const barrel = (L || H) * MM;
    const geom = new THREE.CylinderGeometry(r, r, barrel, 24);
    const mesh = new THREE.Mesh(geom, materialByTag(row.tag));
    mesh.rotation.z = Math.PI / 2;
    return mesh;
  }
  const r = (d / 2) * MM;
  const h = (H || L) * MM;
  const geom = new THREE.CylinderGeometry(r, r, h, 24);
  return new THREE.Mesh(geom, materialByTag(row.tag));
}

function positionMeters(row) {
  if (row && Number.isFinite(Number(row.x)) && Number.isFinite(Number(row.y))) {
    return new THREE.Vector3(num(row.x, 0), 0, num(row.y, 0));
  }
  const pm = row ? row.position_mm : null;
  if (Array.isArray(pm) && pm.length >= 2) {
    return new THREE.Vector3(num(pm[0], 0) * MM, 0, num(pm[1], 0) * MM);
  }
  return new THREE.Vector3(num(pm?.x, 0) * MM, num(pm?.y, 0) * MM, num(pm?.z, 0) * MM);
}

function createTagSprite(text) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgba(0,0,0,0.65)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 28px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(text), canvas.width / 2, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(3.2, 0.8, 1);
  return sprite;
}

function normalizeSceneItems(sceneDoc) {
  if (Array.isArray(sceneDoc)) return sceneDoc;
  if (sceneDoc && Array.isArray(sceneDoc.equipment)) return sceneDoc.equipment;
  if (sceneDoc && sceneDoc.scene && Array.isArray(sceneDoc.scene.equipment)) return sceneDoc.scene.equipment;
  return [];
}

function updateInfoPanel(row) {
  if (!row) {
    infoTagEl.textContent = "—";
    infoServiceEl.textContent = "—";
    infoSizeEl.textContent = "—";
    infoPosEl.textContent = "—";
    infoZoneEl.textContent = "—";
    infoUpstreamEl.textContent = "—";
    infoDownstreamEl.textContent = "—";
    infoNearestEl.textContent = "—";
    return;
  }
  const d = row.dimensions || {};
  infoTagEl.textContent = row.tag ?? "—";
  infoServiceEl.textContent = row.service ?? "—";
  infoSizeEl.textContent = `W ${num(row.width, d.diameter ?? row.diameter ?? 0)} · L ${num(
    row.length,
    d.length ?? 0
  )} · H ${num(row.height, d.height ?? 0)}`;
  const pos = positionMeters(row);
  infoPosEl.textContent = `x ${pos.x.toFixed(2)}, z ${pos.z.toFixed(2)}`;
  infoZoneEl.textContent = row.zone_id ?? "—";
  infoUpstreamEl.textContent = row.upstream ?? "—";
  infoDownstreamEl.textContent = row.downstream ?? "—";
  infoNearestEl.textContent = row.nearest ?? "—";
}

function initThree() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a1a);
  const camera = new THREE.PerspectiveCamera(
    50,
    containerEl.clientWidth / Math.max(containerEl.clientHeight, 1),
    0.1,
    5000
  );
  camera.position.set(80, 60, 80);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(containerEl.clientWidth, containerEl.clientHeight);
  containerEl.appendChild(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const sun = new THREE.DirectionalLight(0xffffff, 0.85);
  sun.position.set(50, 120, 40);
  scene.add(sun);
  const grid = new THREE.GridHelper(400, 40, 0x444444, 0x333333);
  scene.add(grid);
  const equipmentGroup = new THREE.Group();
  scene.add(equipmentGroup);
  const labelGroup = new THREE.Group();
  scene.add(labelGroup);
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  function onResize() {
    const w = containerEl.clientWidth;
    const h = containerEl.clientHeight;
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);
  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
  renderer.domElement.addEventListener("pointerdown", (ev) => {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(equipmentGroup.children, false);
    if (hits.length > 0) updateInfoPanel(hits[0].object.userData.row || null);
  });
  return { scene, camera, equipmentGroup, labelGroup, controls };
}

function disposeObject3D(obj) {
  obj.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
      else child.material.dispose();
    }
  });
}

function populateEquipmentMeshes(threeCtx, items) {
  const { equipmentGroup, labelGroup } = threeCtx;
  while (equipmentGroup.children.length) {
    const o = equipmentGroup.children[0];
    equipmentGroup.remove(o);
    disposeObject3D(o);
  }
  while (labelGroup.children.length) {
    const o = labelGroup.children[0];
    labelGroup.remove(o);
    disposeObject3D(o);
  }
  for (const row of items) {
    const gt = row.geometry_type || "cylinder";
    const mesh = buildMesh(gt, row);
    const base = positionMeters(row);
    mesh.position.set(base.x, 0, base.z);
    mesh.userData.tag = row.tag;
    mesh.userData.row = row;
    equipmentGroup.add(mesh);
    mesh.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(mesh);
    mesh.position.y = -box.min.y + base.y;
    mesh.updateMatrixWorld(true);
    const box2 = new THREE.Box3().setFromObject(mesh);
    const label = createTagSprite(row.tag ?? "N/A");
    label.position.set(base.x, box2.max.y + 0.8, base.z);
    labelGroup.add(label);
  }
}

const threeCtx = initThree();

async function refreshScene() {
  const [equipment, pipeline, statusDoc] = await Promise.all([
    fetchJson("/api/equipment"),
    fetchJson("/api/pipeline").catch(async () => {
      const scene = await fetchJson("/api/scene");
      return { scene, relations: {}, walls: { walls: [], rooms: [], center: [0, 0] } };
    }),
    fetchJson("/api/status").catch(() => ({ missing: [], files: {} })),
  ]);
  renderEquipment(equipment);
  const sceneDoc = pipeline.scene || pipeline;
  const wallsDoc = pipeline.walls || {};
  const relationsDoc = pipeline.relations || {};
  const meta = sceneDoc.meta || sceneDoc?.scene?.meta || {};
  const items = normalizeSceneItems(sceneDoc);
  const wallsCount = Array.isArray(wallsDoc.walls)
    ? wallsDoc.walls.length
    : Array.isArray(sceneDoc.walls)
      ? sceneDoc.walls.length
      : 0;
  const relCount = typeof relationsDoc === "object" ? Object.keys(relationsDoc).length : 0;
  sceneMetaEl.textContent = `Project: ${meta.project ?? "Industrial Digital Twin"} · 3D items: ${items.length} · walls: ${wallsCount} · relations: ${relCount} · missing: ${(statusDoc.missing || []).join(", ") || "none"}`;
  populateEquipmentMeshes(threeCtx, items);
  updateInfoPanel(items[0] || null);
  const box = new THREE.Box3().setFromObject(threeCtx.equipmentGroup);
  if (!box.isEmpty()) {
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const dist = Math.max(size.x, size.y, size.z) * 1.8;
    threeCtx.camera.position.set(center.x + dist * 0.6, center.y + dist * 0.45, center.z + dist * 0.6);
    threeCtx.camera.lookAt(center);
    threeCtx.controls.target.copy(center);
    threeCtx.controls.update();
  }
}

function wireFileUi() {
  if (!fileInput || !fileDropzone) return;
  fileDropzone.addEventListener("click", () => fileInput.click());
  fileDropzone.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length) addFilesFromList(fileInput.files);
    fileInput.value = "";
  });
  fileDropzone.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    fileDropzone.classList.add("dragover");
  });
  fileDropzone.addEventListener("dragleave", () => fileDropzone.classList.remove("dragover"));
  fileDropzone.addEventListener("drop", (ev) => {
    ev.preventDefault();
    fileDropzone.classList.remove("dragover");
    if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
      addFilesFromList(ev.dataTransfer.files);
    }
  });
}

async function handleUploadClick() {
  const { plan, excel } = pickPlanAndExcel();
  if (!plan && !excel) {
    setUploadMessage("Add at least one layout drawing (PDF/PNG) and/or an equipment .xlsx.", true);
    return;
  }
  uploadBtn.disabled = true;
  cancelBtn.disabled = true;
  setTaskProgress(0);
  setUploadMessage("Uploading…");
  setProcessStatus("Uploading…");
  try {
    const upload = await uploadProjectFiles();
    activeTaskId = upload.task_id || null;
    lastUserError = "";
    pushLog(`Upload accepted, task ${activeTaskId || "N/A"}`);
    if (activeTaskId) {
      cancelBtn.disabled = false;
      await pollTaskUntilDone(activeTaskId);
    }
    await refreshScene();
    setUploadMessage("Project files processed successfully.");
    setProcessStatus("Ready");
    setStatus("Connected to API.");
  } catch (e) {
    const msg = String(e.message || e);
    lastUserError = msg;
    let userMsg = msg;
    if (msg.includes("OCR_FAILED")) userMsg = "OCR failed: no equipment tags detected in layout.";
    else if (msg.includes("INVALID_EXCEL")) userMsg = "Excel format invalid: required sheet 'Equipment_list' not found.";
    else if (msg.includes("INVALID_LAYOUT")) userMsg = "No layout detected or unreadable plan image.";
    else if (msg.includes("UPLOAD_TOO_LARGE") || msg.includes("upload too large")) {
      userMsg = "Upload too large. Please use smaller files.";
    } else if (msg.includes("CANCELLED")) userMsg = "Task cancelled.";
    else if (msg.includes("PIPELINE_TIMEOUT")) userMsg = "Processing timeout.";
    else if (msg.toLowerCase().includes("sheet")) {
      userMsg = "Excel format invalid: required sheet 'Equipment_list' not found.";
    } else if (msg.toLowerCase().includes("excel not found")) {
      userMsg = "No Excel detected. Please upload a valid .xlsx file.";
    } else if (msg.toLowerCase().includes("plan image not found") || msg.includes("missing required")) {
      userMsg = "Add both a plan drawing and a valid .xlsx if the server reports missing files.";
    } else if (msg.toLowerCase().includes("timeout")) userMsg = `Processing timeout. ${msg}`;
    setUploadMessage(userMsg, true);
    setProcessStatus(userMsg, true);
    pushLog(userMsg, "error");
    setStatus(`Backend/API error (${API_BASE}): ${userMsg}`, true);
  } finally {
    uploadBtn.disabled = false;
    cancelBtn.disabled = true;
    activeTaskId = null;
  }
}

function wireCopilot() {
  document.getElementById("copilot-actions")?.addEventListener("click", (ev) => {
    const t = ev.target;
    if (t && t.getAttribute("data-copilot")) {
      const k = t.getAttribute("data-copilot");
      let p = COPILOT_PRESETS[k] || copilotInput.value;
      if (k === "failed") p = COPILOT_PRESETS.failed + (lastUserError || logPanelEl.textContent.slice(0, 1200) || "No error yet.");
      callCopilot(p);
    }
  });
  if (copilotSend) {
    copilotSend.addEventListener("click", () => callCopilot(copilotInput.value));
  }
}

async function main() {
  wireFileUi();
  wireCopilot();
  if (fileChips) {
    fileChips.innerHTML = "";
    updateLoadedSummary();
  }
  uploadBtn.addEventListener("click", handleUploadClick);
  cancelBtn.addEventListener("click", async () => {
    if (!activeTaskId) return;
    try {
      await cancelTask(activeTaskId);
      setProcessStatus("Cancelled");
      if (taskProgressEl) setTaskProgress(0);
      pushLog(`Task ${activeTaskId} cancelled`, "warn");
    } catch (e) {
      pushLog(`Cancel failed: ${e.message || e}`, "error");
    }
  });
  try {
    await refreshScene();
    setStatus("Connected to API.");
    setProcessStatus("Idle");
    if (taskProgressEl) {
      taskProgressEl.removeAttribute("value");
      if (taskProgressWrap) taskProgressWrap.classList.add("empty");
    }
    pushLog("Frontend initialized and connected");
  } catch (e) {
    setStatus(`Failed to load API (${API_BASE}). Start Flask on :5000. ${e.message}`, true);
    setProcessStatus("Backend offline", true);
    if (taskProgressEl) {
      taskProgressEl.removeAttribute("value");
    }
    pushLog(`Backend connection failed: ${e.message}`, "error");
  }
}

main();
