const API_BASE = "http://127.0.0.1:5000";

const statusEl = document.getElementById("status");
const listEl = document.getElementById("equipment-list");
const sceneMetaEl = document.getElementById("scene-meta");

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

async function main() {
  try {
    const [equipment, scene] = await Promise.all([
      fetchJson("/api/equipment"),
      fetchJson("/api/scene"),
    ]);

    renderEquipment(equipment);

    const meta = scene.meta || {};
    sceneMetaEl.textContent = `project: ${meta.project ?? "—"} · equipment items: ${(scene.equipment || []).length} · walls: ${(scene.walls || []).length}`;

    setStatus("Connected to API.");
  } catch (e) {
    setStatus(`Failed to load API (${API_BASE}). Start the Flask server on port 5000. ${e.message}`, true);
  }
}

main();
