import { validateMergedModel } from '../schema/mergedEquipmentSchema'
import { classifyPosition, inferGeometryPrimitive } from './parseStrategy'

function mapType(rawType) {
  const normalized = String(rawType ?? '')
    .trim()
    .toLowerCase()

  if (normalized.includes('vertical') && normalized.includes('tank')) {
    return 'vertical-tank'
  }

  if (normalized.includes('vertical') && normalized.includes('drum')) {
    return 'vertical-drum'
  }

  if (normalized.includes('horizontal') && normalized.includes('drum')) {
    return 'horizontal-drum'
  }

  if (normalized.includes('exchanger')) {
    return 'exchanger'
  }

  if (normalized.includes('compressor')) {
    return 'compressor'
  }

  if (normalized.includes('pump')) {
    return 'pump'
  }

  return 'unknown'
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function buildApproximatePosition(pdfMatch) {
  if (!pdfMatch) {
    return {
      x: null,
      y: null,
      z: 0,
      rotationDeg: null,
      status: 'unresolved',
      confidence: 0,
      note: 'No reliable 2D match. Manual placement required.',
    }
  }

  const confidence = Math.max(0, Math.min(1, Number(pdfMatch.confidence ?? 0.4)))
  const status = classifyPosition(confidence)

  return {
    x: toNumberOrNull(pdfMatch.x),
    y: toNumberOrNull(pdfMatch.y),
    z: 0,
    rotationDeg: toNumberOrNull(pdfMatch.rotationDeg),
    status,
    confidence,
    note:
      status === 'resolved'
        ? 'Position extracted from PDF with high confidence.'
        : 'Position from 2D PDF is approximate and should be reviewed.',
  }
}

export function mergeEquipmentData({
  excelRows,
  pdfPositionsByTag,
  projectName = 'Uploaded Equipment Model',
}) {
  const equipment = excelRows.map((row, index) => {
    const tag = String(row.tag ?? '').trim()
    const type = mapType(row.type)
    const pdfMatch = pdfPositionsByTag[tag] ?? null

    return {
      id: `eq-${index + 1}`,
      tag: tag || `UNNAMED-${index + 1}`,
      type,
      geometryPrimitive: inferGeometryPrimitive(type),
      dimensions: {
        diameterM: toNumberOrNull(row.diameterM),
        lengthM: toNumberOrNull(row.lengthM),
        widthM: toNumberOrNull(row.widthM),
        heightM: toNumberOrNull(row.heightM),
      },
      orientationDeg: Number(row.orientationDeg ?? 0),
      position: buildApproximatePosition(pdfMatch),
      sourcePriority: {
        tag: 'excel',
        size: 'excel',
        orientation: 'excel',
        position: 'pdf-2d-approx',
      },
      sourceTrace: {
        excel: {
          fileName: String(row.excelFileName ?? 'equipment.xlsx'),
          rowRef: String(row.rowRef ?? `row-${index + 2}`),
        },
        pdf2d: pdfMatch
          ? {
              fileName: String(pdfMatch.pdfFileName ?? 'layout.pdf'),
              pageRef: String(pdfMatch.pageRef ?? 'p1'),
              annotationRef: String(pdfMatch.annotationRef ?? `ann-${index + 1}`),
            }
          : null,
      },
      manualCorrection: {
        isEdited: false,
        editedAtIso: null,
        reason: null,
      },
    }
  })

  return validateMergedModel({
    generatedAtIso: new Date().toISOString(),
    projectName,
    assumptions: [
      'Excel values control tag, dimensions, and orientation.',
      '2D PDF coordinates are approximate only.',
      'Missing/low confidence positions remain unresolved and require manual correction.',
    ],
    equipment,
  })
}
