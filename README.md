# Equipment Demo Scaffold (React + Vite)

This repository contains the first iteration of a web demo with:

- `/viewer` (Three.js + OrbitControls scaffold)
- `/presentation` (Reveal.js slide deck scaffold)

## Current Scope (Intentionally Limited)

This iteration only establishes:

1. Project structure
2. Parsing + merge strategy
3. Merged output schema

It does **not** implement full BIM extraction or accurate placement logic.

## Non-Negotiable Data Rules

- Excel is the source of truth for **tag**, **size**, and **orientation**.
- 2D PDF provides **approximate position hints only**.
- Exact coordinates are never guessed.
- Uncertain items are explicitly marked with:
  - `positionStatus` (`approximate` or `unresolved`)
  - `confidence` (`0.0` to `1.0`)
- Viewer supports manual x/y/rotation edits and corrected JSON export.

## Quick Start

```bash
npm install
npm run dev
```

Then open:

- `http://localhost:5173/viewer`
- `http://localhost:5173/presentation`

## Key Files

- `src/features/merge/parsingStrategy.js` - merge policy implementation
- `src/features/merge/mergedSchema.js` - schema object used by app code
- `src/features/merge/merged-equipment.schema.json` - JSON schema artifact
- `src/pages/ViewerPage.jsx` - viewer UI scaffold and export workflow
- `src/pages/PresentationPage.jsx` - Reveal.js slides
- `docs/parsing-strategy.md` - strategy notes and confidence policy
