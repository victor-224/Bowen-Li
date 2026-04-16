const geometryByType = {
  tank: 'verticalCylinder',
  drum: 'verticalCylinder',
  exchanger: 'horizontalCylinder',
  compressor: 'box',
  pump: 'pumpProxy',
}

function normalizeType(typeValue = '') {
  return String(typeValue).trim().toLowerCase()
}

function normalizeOrientation(orientationValue = '') {
  const cleaned = String(orientationValue).trim().toLowerCase()
  if (cleaned.startsWith('vert')) return 'vertical'
  if (cleaned.startsWith('horiz')) return 'horizontal'
  return 'unknown'
}

function resolveGeometryProxy(typeValue, orientation) {
  const normalizedType = normalizeType(typeValue)

  if (normalizedType === 'drum' && orientation === 'horizontal') {
    return 'horizontalCylinder'
  }

  if (normalizedType === 'drum' && orientation === 'vertical') {
    return 'verticalCylinder'
  }

  return geometryByType[normalizedType] ?? 'unknown'
}

function toApproximatePosition(pdf2dMatch) {
  if (!pdf2dMatch) {
    return {
      position: { x: null, y: null, rotationDeg: null },
      positionStatus: 'unresolved',
      confidence: 0,
      unresolvedReason: 'No trustworthy 2D marker match found yet.',
      pdf2d: null,
    }
  }

  return {
    position: {
      x: pdf2dMatch.x ?? null,
      y: pdf2dMatch.y ?? null,
      rotationDeg: pdf2dMatch.rotationDeg ?? 0,
    },
    positionStatus: 'approximate',
    confidence: pdf2dMatch.confidence ?? 0.35,
    unresolvedReason: null,
    pdf2d: {
      page: pdf2dMatch.page,
      markerId: pdf2dMatch.markerId,
      method: '2d-overlay-estimate',
    },
  }
}

/**
 * Merge strategy:
 * 1) Excel supplies authoritative identity data: tag, size, orientation.
 * 2) 2D PDF may contribute approximate x/y/rotation only.
 * 3) Missing/uncertain positions are explicitly unresolved with confidence.
 */
export function mergeExcelAndPdfRows({
  excelRows,
  pdf2dByTag,
  sourceMeta,
}) {
  const equipment = excelRows.map((row, rowIndex) => {
    const orientation = normalizeOrientation(row.orientation)
    const approximate = toApproximatePosition(pdf2dByTag[row.tag])
    const geometryProxy = resolveGeometryProxy(row.type, orientation)

    return {
      id: `eq-${rowIndex + 1}`,
      tag: row.tag,
      size: row.size,
      type: normalizeType(row.type),
      orientation,
      geometryProxy,
      position: approximate.position,
      positionStatus: approximate.positionStatus,
      confidence: approximate.confidence,
      unresolvedReason: approximate.unresolvedReason,
      source: {
        excel: {
          rowIndex: rowIndex + 1,
          tagField: 'tag',
          sizeField: 'size',
          orientationField: 'orientation',
        },
        pdf2d: approximate.pdf2d,
        manualCorrection: null,
      },
    }
  })

  return {
    meta: {
      version: '0.1.0-scaffold',
      createdAt: new Date().toISOString(),
      sourceFiles: sourceMeta,
    },
    equipment,
  }
}
