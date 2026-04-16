# Equipment Viewer + Presentation (React + Vite)

This project is the **first milestone** scaffold for a demo with two routes:

- `/viewer` - Three.js scene + list/search/select + unresolved panel + manual correction + JSON export
- `/presentation` - Reveal.js slides for stakeholder walkthrough

## Core Rule Set

- Excel is source-of-truth for **tag**, **size**, and **orientation**.
- 2D PDF provides **approximate** position only.
- Do not guess exact coordinates from uncertain 2D input.
- Any uncertain item must carry status + confidence.
- Manual correction (`x`, `y`, `rotationDeg`) is supported and exportable.

## Milestone Scope

Implemented now:

- Project structure and routing
- Merged schema with validation (`zod`)
- Parsing/merge strategy modules
- Placeholder source adapters for Excel + PDF
- Viewer controls and presentation deck

Deferred:

- Full production-grade PDF geometry extraction / BIM logic

## Run

```bash
npm install
npm run dev
```

## Docs

- `docs/PARSING_STRATEGY.md`
- `docs/MERGED_SCHEMA.md`

## Source Files

Upload files directly in `/viewer`:

- Excel (`.xlsx`, `.xls`) required
- PDF (`.pdf`) optional

If PDF matching is missing or weak, positions remain unresolved until manual edits are provided.
