import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const API_BASE = "http://127.0.0.1:5000";
const MM = 0.001;

const statusEl = document.getElementById("status");
const listEl = document.getElementById("equipment-list");
const sceneMetaEl = document.getElementById("scene-meta");
const containerEl = document.getElementById("three-container");
const planFileInput = document.getElementById("plan-file-input");
const excelFileInput = document.getElementById("excel-file-input");
const uploadBtn = document.getElementById("load-project-btn");
const loadedNamesEl = document.getElementById("loaded-filenames");
const uploadMsgEl = document.getElementById("upload-feedback");

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.className = isError ? "error" : "";
}

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`${path} ${res.status}: ${errBody}`);
  }
  return res.json();
}

async function uploadProjectFiles(planFile, excelFile) {
  const form = new FormData();
  form.append("plan_file", planFile);
  form.append("excel_file", excelFile);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success !== true) {
    const reason = body.error || `HTTP ${res.status}`;
    throw new Error(`Upload failed: ${reason}`);
  }
  return body;
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

function updateSelectedNames() {
  const plan = planFileInput.files && planFileInput.files[0];
  const excel = excelFileInput.files && excelFileInput.files[0];
  const planName = plan ? plan.name : "未选择";
  const excelName = excel ? excel.name : "未选择";
  loadedNamesEl.textContent = `当前已加载：平面图（${planName}），Excel（${excelName}）`;
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
    return new THREE.Mesh(geom, makeMaterial(0.2));
  }

  if (gt === "Exchanger" || gt === "cylinder_horizontal") {
    const r = (d / 2) * MM;
    const barrel = (L || H) * MM;
    const geom = new THREE.CylinderGeometry(r, r, barrel, 24);
    const mesh = new THREE.Mesh(geom, makeMaterial(0.5));
    mesh.rotation.z = Math.PI / 2;
    return mesh;
  }

  const r = (d / 2) * MM;
  const h = (H || L) * MM;
  const geom = new THREE.CylinderGeometry(r, r, h, 24);
  return new THREE.Mesh(geom, makeMaterial(0.8));
}

function positionMeters(pm) {
  if (Array.isArray(pm) && pm.length >= 2) {
    return new THREE.Vector3(num(pm[0], 0) * MM, 0, num(pm[1], 0) * MM);
  }
  return new THREE.Vector3(
    num(pm?.x, 0) * MM,
    num(pm?.y, 0) * MM,
    num(pm?.z, 0) * MM
  );
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

  return { scene, camera, equipmentGroup, controls };
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

function populateEquipmentMeshes(equipmentGroup, items) {
  while (equipmentGroup.children.length) {
    const o = equipmentGroup.children[0];
    equipmentGroup.remove(o);
    disposeObject3D(o);
  }

  for (const row of items) {
    const gt = row.geometry_type || "cylinder";
    const mesh = buildMesh(gt, row);
    const base = positionMeters(row.position_mm);
    mesh.position.set(base.x, 0, base.z);
    mesh.userData.tag = row.tag;
    equipmentGroup.add(mesh);
    mesh.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(mesh);
    mesh.position.y = -box.min.y + base.y;
    mesh.updateMatrixWorld(true);
  }
}

const threeCtx = initThree();

async function refreshScene() {
  const [equipment, sceneDoc] = await Promise.all([
    fetchJson("/api/equipment"),
    fetchJson("/api/scene"),
  ]);

  renderEquipment(equipment);

  const meta = sceneDoc.meta || {};
  const items = sceneDoc.equipment || [];
  sceneMetaEl.textContent = `project: ${meta.project ?? "—"} · 3D items: ${items.length} · walls: ${(sceneDoc.walls || []).length}`;

  populateEquipmentMeshes(threeCtx.equipmentGroup, items);

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

async function handleUploadClick() {
  const plan = planFileInput.files && planFileInput.files[0];
  const excel = excelFileInput.files && excelFileInput.files[0];
  if (!plan || !excel) {
    setUploadMessage("请先选择平面图和 Excel 文件。", true);
    return;
  }
  uploadBtn.disabled = true;
  setUploadMessage("上传中...");
  try {
    await uploadProjectFiles(plan, excel);
    await refreshScene();
    setUploadMessage("success: 项目文件加载成功。");
    setStatus("Connected to API.");
  } catch (e) {
    setUploadMessage(String(e.message || e), true);
    setStatus(`Failed to load API (${API_BASE}). Start Flask on :5000. ${e.message}`, true);
  } finally {
    uploadBtn.disabled = false;
  }
}

async function main() {
  planFileInput.addEventListener("change", updateSelectedNames);
  excelFileInput.addEventListener("change", updateSelectedNames);
  uploadBtn.addEventListener("click", handleUploadClick);
  updateSelectedNames();
  try {
    await refreshScene();
    setStatus("Connected to API.");
  } catch (e) {
    setStatus(`Failed to load API (${API_BASE}). Start Flask on :5000. ${e.message}`, true);
  }
}

main();
