# Merged Schema (Milestone 1)

Schema is implemented in:

- `src/schema/mergedEquipmentSchema.js`

Top-level shape:

```json
{
  "generatedAtIso": "2026-04-16T00:00:00.000Z",
  "projectName": "Uploaded Equipment Model",
  "assumptions": [
    "Excel values control tag, dimensions, and orientation.",
    "2D PDF coordinates are approximate only."
  ],
  "equipment": []
}
```

Each equipment record includes:

- identity: `id`, `tag`, `type`
- geometry mapping: `geometryPrimitive`
- dimensions: `diameterM`, `lengthM`, `widthM`, `heightM`
- orientation: `orientationDeg` (Excel authority)
- position object:
  - `x`, `y`, `z`
  - `rotationDeg`
  - `status`: `resolved | approximate | unresolved`
  - `confidence`: `0..1`
  - `note`
- source metadata:
  - `sourcePriority` (hard-coded to encode business rule)
  - `sourceTrace` (excel and optional pdf references)
- manual corrections:
  - `isEdited`
  - `editedAtIso`
  - `reason`

## Geometry Mapping (simplified)

- vertical tank/drum -> `vertical-cylinder`
- horizontal drum/exchanger -> `horizontal-cylinder`
- compressor -> `box`
- pump -> `proxy`
