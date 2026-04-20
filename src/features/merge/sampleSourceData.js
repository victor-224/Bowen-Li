import { mergeExcelAndPdfRows } from './parsingStrategy.js'

const sampleExcelRows = [
  { tag: 'B200', size: '5300x14200', orientation: 'V', type: 'Drum' },
  { tag: 'B300', size: '1000x1800', orientation: 'V', type: 'Drum' },
  { tag: 'B301', size: '3100x6100', orientation: 'V', type: 'Drum' },
  { tag: 'B1000', size: '3000x8700', orientation: 'H', type: 'Drum' },
  { tag: 'E100', size: '440x6100', orientation: 'H', type: 'Exchanger' },
  { tag: 'X200A', size: '3000x6000', orientation: 'H', type: 'Compressor' },
  { tag: 'P001A', size: '1000x2000', orientation: 'H', type: 'Pump' },
]

const samplePdf2dByTag = {
  B200: {
    x: 8.2,
    y: 4.7,
    rotationDeg: 0,
    page: 1,
    markerId: 'm-b200',
    confidence: 0.52,
  },
  B300: {
    x: 11.4,
    y: 5.8,
    rotationDeg: 0,
    page: 1,
    markerId: 'm-b300',
    confidence: 0.47,
  },
  B1000: {
    x: 16.1,
    y: 7.9,
    rotationDeg: 90,
    page: 1,
    markerId: 'm-b1000',
    confidence: 0.44,
  },
  X200A: {
    x: 20.3,
    y: 9.1,
    rotationDeg: 90,
    page: 4,
    markerId: 'm-x200a',
    confidence: 0.48,
  },
  P001A: {
    x: 13.8,
    y: 11.2,
    rotationDeg: 180,
    page: 2,
    markerId: 'm-p001a',
    confidence: 0.41,
  },
}

export const mergedScaffoldDataset = mergeExcelAndPdfRows({
  excelRows: sampleExcelRows,
  pdf2dByTag: samplePdf2dByTag,
  sourceMeta: {
    excel: 'Annexe_2_Equipement_liste_et_taille.xlsx (pending parser wiring)',
    pdf2d: 'Annexe_3_Equipement_image_3D_Arrangement_2D.pdf',
    notes:
      'Scaffold demo rows for presentation. Use parsed real rows once input adapters are wired.',
  },
})
