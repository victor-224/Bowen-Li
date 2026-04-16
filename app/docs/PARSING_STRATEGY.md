# Parsing Strategy (Milestone 1)

This first milestone is **structure-first**. It defines merge behavior and uncertainty handling without implementing full BIM extraction.

## Inputs

Expected user uploads:

1. Excel equipment list (required)
2. 2D layout PDF (optional but recommended)
3. Additional source file(s) can be attached later (not yet hard-coded in parser)

## Non-Negotiable Data Priority

1. **Excel is source-of-truth** for:
   - equipment `tag`
   - `size` / dimensions
   - `orientation`
2. **2D PDF contributes approximate position only** (`x`, `y`, optionally `rotationDeg`)
3. **No exact coordinate guessing**
   - if position extraction is weak/missing, keep `x/y/rotationDeg = null`
   - mark `status = unresolved` and confidence near `0`

## Merge Procedure

1. Parse Excel rows into normalized equipment records.
2. Parse PDF into a coarse `tag -> approximate position` map.
3. Merge by `tag`:
   - always keep Excel identity + dimensions + orientation
   - attach PDF position with `status` + `confidence`
4. Validate merged output with `zod` schema.
5. In `/viewer`, allow manual correction of `x/y/rotationDeg`.
6. Export corrected JSON for downstream handoff.

## Confidence Policy

- `resolved`: 0.85 - 1.00
- `approximate`: 0.30 - 0.84
- `unresolved`: 0.00 - 0.29

In Milestone 1, PDF-derived data defaults to approximate unless manually corrected.
