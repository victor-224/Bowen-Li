# Industrial Digital Twin System

**AI-enhanced local industrial digital twin platform** that converts plans, documents, and equipment data into interactive layouts, relation graphs, and a Three.js scene—with an optional local LLM / vision layer. Everything runs on your machine; no cloud dependency for core workflows.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-API-000000?logo=flask&logoColor=white)
![Three.js](https://img.shields.io/badge/Three.js-3D-000000?logo=threedotjs&logoColor=white)
![OCR](https://img.shields.io/badge/OCR-EasyOCR-2ea44f)
![Local AI](https://img.shields.io/badge/Local%20AI-LM%20Studio-6366f1)
![LM Studio](https://img.shields.io/badge/LM%20Studio-OpenAI%20compatible-8b5cf6)
![Async Pipeline](https://img.shields.io/badge/Async-Pipeline-1f6feb)

---

## Demo preview

Screenshots can be dropped into `docs/images/` (or repo root) when available.

| Placeholder | Suggested capture |
|---------------|-------------------|
| **Dashboard UI** | `TODO: docs/images/dashboard.png` — main layout with status + scene |
| **Upload workflow** | `TODO: docs/images/upload.png` — unified dropzone + file tags |
| **Scene viewer** | `TODO: docs/images/scene.png` — Three.js equipment view |
| **AI Copilot** | `TODO: docs/images/copilot.png` — sidebar + response |

```markdown
<!-- Example when files exist:
![Dashboard](docs/images/dashboard.png)
-->
```

---

## Key features

- **Unified multi-file upload** — Drag-and-drop or browse; smart tags (layout, equipment list, supporting docs); optional manual overrides.
- **OCR + layout parsing** — Plan PDF/PNG/JPEG → layout processing and spatial tag detection where supported.
- **Equipment extraction from Excel** — `Equipment_list` sheet → structured equipment rows fused with layout/OCR.
- **Graph relationship generation** — Layout graph (nodes, edges, zones, constraints) plus spatial relations.
- **Scene rendering / visualization** — Three.js viewer with equipment meshes and selection details.
- **Async task engine** — `POST /api/upload` returns immediately with a `task_id`; background pipeline with structured states.
- **Structured error handling** — API errors with codes, messages, and stage context; UI maps common failures to readable text.
- **Deterministic cache** — Single-signature cache for identical pipeline inputs (demo stability).
- **Runtime asset contract** — Validated lifecycle for key assets (e.g. plan image) with clear missing/corrupted errors.
- **Local AI Copilot (optional)** — `POST /api/copilot` uses LM Studio (OpenAI-compatible chat); UI fails gracefully when offline; answers can include **project context** (equipment, graph, scene, vision, last task error) when data is loaded.
- **Optional vision enrichment** — Set `ENABLE_VISION=true` to attach a normalized vision payload to the pipeline output when a local VLM is available (`qwen2.5-vl-7b-instruct` path in backend).
- **Fully local-first** — Flask API + static frontend + local models only; no required external SaaS.

---

## System architecture

```text
Frontend UI (HTML / CSS / JS + Three.js)
        │
        ▼
   Flask REST API
        │
        ▼
 Async pipeline (upload → validate → OCR → layout → graph → scene → finalize)
        │
        ├── OCR / PDF / Excel parsing
        ├── Walls / relations / layout graph
        └── Scene document generation
        │
        ▼ (optional)
 Local LLM / VLM (LM Studio) — Copilot chat + optional vision on pipeline payload
```

---

## Quick start

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

Use Python 3.10+ recommended (match your environment).

### 2. Run the backend

```bash
python run.py
```

The API listens on **http://localhost:5000** (no Flask reloader in this entry point for stable local runs).

### 3. Open the frontend

From another terminal, in the repository root:

```bash
python -m http.server 3000 -d frontend
```

Open **http://localhost:3000** in your browser.

**Windows one-liner (optional):** double-click `start_demo.bat` — starts backend, static server on 3000, and opens the browser.

### 4. Optional — LM Studio (Copilot + vision)

1. Install [LM Studio](https://lmstudio.ai/) and start the local server (default chat port `1234`).
2. Load a compatible chat model (see **AI models** below). Copilot uses the text API; vision uses multimodal models when `ENABLE_VISION` is enabled.
3. If LM Studio is off, the app still runs; Copilot shows an offline notice.

### 5. Upload and process

Use **Load & process** after adding at least a layout file (PDF/PNG/JPEG) and/or equipment `.xlsx` as required by your demo data. The UI shows pipeline status, progress, and errors in plain language.

**Health check:** `GET http://localhost:5000/health`

---

## AI models (optional)

The system **does not require** local LLMs. When enabled, typical compatible models include:

| Model | Role |
|--------|------|
| **Qwen2.5-VL 7B** | Vision / layout-style questions (optional `ENABLE_VISION`) |
| **InternVL3.5 8B** | Vision fallback in adapter chain |
| **DeepSeek R1 Distill Qwen 8B** | General reasoning (adapter list) |
| **Qwen3 8B** | Default **Copilot** chat backend |

Exact model IDs match your LM Studio download names. Copilot and vision are **best-effort**; the industrial pipeline remains the source of truth.

---

## Use cases

- **Factory layout digitization** — Turn PDF/plan raster + equipment lists into a navigable scene and graph.
- **Equipment mapping** — Correlate tags from drawings with Excel attributes.
- **Engineering demo platform** — Local-only demo for stakeholders without deploying cloud infra.
- **AI-assisted plant review** — Copilot summarizes loaded data, risks, or failures using **project context** when available.
- **Portfolio / student project** — Shows full-stack + async + optional AI integration in one repo.

---

## Roadmap (near-term)

- Better CAD / vector drawing ingestion
- Smarter layout risk hints (rules + optional model)
- Report export (PDF/HTML)
- Bilingual UI (EN/CN parity in chrome)
- Multi-project / workspace management in UI

---

## What this project demonstrates (recruiter-friendly)

- **Full-stack engineering** — Flask API, async tasks, static SPA-style frontend, Three.js integration.
- **Async backend systems** — Non-blocking upload, polling, bounded task store, structured lifecycle.
- **AI integration** — Optional LM Studio chat with **data-aware** prompts; optional vision enrichment behind a flag.
- **Computer vision / OCR workflow** — Layout → detection → fusion with tabular data.
- **Product-oriented UX** — Unified upload, readable pipeline states, Copilot panel with offline-safe behavior.

---

## API snapshot (non-exhaustive)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/api/upload` | Multipart upload; returns `task_id` immediately |
| `GET` | `/api/task/<id>` | Task status, progress, structured errors |
| `GET` | `/api/pipeline` | Unified scene + relations + walls + graph + phase_c (+ optional `vision`) |
| `GET` | `/api/equipment` | Equipment dict from Excel |
| `POST` | `/api/copilot` | Local LLM chat (JSON body: `message`, optional `project_context`) |

See `backend/api.py` for the full route list (`/api/layout_graph`, `/api/observability`, etc.).

---

## Contributing

Issues and PRs are welcome—especially around OCR robustness, layout graph semantics, and UX clarity. Keep changes aligned with the project’s **local-first** and **stability-first** goals.

---

## License / author

License file: add a `LICENSE` to the repository if you need a formal terms (e.g. MIT); until then, treat usage as **all rights reserved** by the repository owner unless stated otherwise in the GitHub **About** section.
