import { mergeExcelAndPdfRows } from './parsingStrategy.js'

const sampleExcelRows = [
  { tag: 'V-101', size: '1800x6000', orientation: 'Vertical', type: 'Tank' },
  { tag: 'D-201', size: '1200x4500', orientation: 'Horizontal', type: 'Drum' },
  { tag: 'K-310', size: '2500x3200', orientation: 'Horizontal', type: 'Compressor' },
  { tag: 'P-410A', size: '6x4', orientation: 'Horizontal', type: 'Pump' },
]

const samplePdf2dByTag = {
  'V-101': { x: 18.4, y: 9.2, rotationDeg: 0, page: 1, markerId: 'm-v101', confidence: 0.42 },
  'D-201': { x: 26.1, y: 11.8, rotationDeg: 90, page: 1, markerId: 'm-d201', confidence: 0.36 },
  'P-410A': { x: 29.9, y: 15.1, rotationDeg: 180, page: 2, markerId: 'm-p410a', confidence: 0.31 },
}

export const mergedScaffoldDataset = mergeExcelAndPdfRows({
  excelRows: sampleExcelRows,
  pdf2dByTag: samplePdf2dByTag,
  sourceMeta: {
    excel: 'uploaded-equipment.xlsx',
    pdf2d: 'uploaded-layout.pdf',
    notes:
      'Scaffold data only. Replace with parsed content from the 3 uploaded files.',
  },
})
