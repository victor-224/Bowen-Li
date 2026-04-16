# Parsing and Merge Strategy (Scaffold)

This first iteration intentionally focuses on transparent data handling, not full BIM placement.

## Source Priorities

1. **Excel is authoritative** for:
   - `tag`
   - `size`
   - `orientation`
2. **2D PDF is approximate only** for:
   - `x`
   - `y`
   - `rotationDeg`

If no reliable 2D marker exists, position remains unresolved (`x/y/rotationDeg = null`).

## Geometry Proxy Mapping (Simplified)

- Vertical tank/drum -> `verticalCylinder`
- Horizontal drum/exchanger -> `horizontalCylinder`
- Compressor -> `box`
- Pump -> `pumpProxy`

## Merge Pipeline

1. Parse Excel rows into normalized equipment records.
2. Parse 2D PDF markers into approximate coordinate candidates.
3. Merge by equipment tag:
   - Always keep Excel values for identity and physical attributes.
   - Attach PDF coordinates as `positionStatus = approximate` with low confidence.
4. Explicitly mark unresolved positions:
   - `positionStatus = unresolved`
   - `confidence = 0`
   - `unresolvedReason` populated
5. Manual correction in Viewer:
   - user edits x/y/rotation
   - status becomes `corrected` when all fields are filled
6. Export corrected JSON for downstream use.

## Confidence Guidance

- `0.00`: unresolved
- `0.20 - 0.50`: approximate from 2D overlays
- `>= 0.90`: manually corrected
