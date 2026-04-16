import * as XLSX from 'xlsx'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'

/**
 * Placeholder adapters for initial scaffold:
 * - Excel parser is intentionally minimal and expects a normalized sheet.
 * - PDF parser currently returns approximate placeholders only.
 * Full extraction logic is intentionally deferred.
 */

GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url,
).toString()

export async function parseExcelEquipment(file) {
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  const sheetName = workbook.SheetNames[0]
  const worksheet = workbook.Sheets[sheetName]
  const rows = XLSX.utils.sheet_to_json(worksheet, { defval: null })

  return rows.map((row, index) => ({
    tag: row.tag ?? row.Tag ?? row.TAG ?? null,
    type: row.type ?? row.Type ?? null,
    diameterM: row.diameterM ?? row.DiameterM ?? row.Diameter ?? null,
    lengthM: row.lengthM ?? row.LengthM ?? row.Length ?? null,
    widthM: row.widthM ?? row.WidthM ?? row.Width ?? null,
    heightM: row.heightM ?? row.HeightM ?? row.Height ?? null,
    orientationDeg:
      row.orientationDeg ?? row.OrientationDeg ?? row.Orientation ?? null,
    rowRef: `row-${index + 2}`,
    excelFileName: file.name,
  }))
}

export async function parsePdfApproxPositions(file) {
  const buffer = await file.arrayBuffer()
  const pdfDoc = await getDocument({ data: buffer }).promise

  // Intentionally shallow placeholder:
  // We only mark pages as available, without guessing coordinates.
  const positionsByTag = {}

  for (let i = 1; i <= pdfDoc.numPages; i += 1) {
    // Read page to ensure the file can be parsed and for future extension.
    await pdfDoc.getPage(i)
  }

  return positionsByTag
}
