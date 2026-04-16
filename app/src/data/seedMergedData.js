import { mergeEquipmentData } from '../parsing/mergeData'

const seedExcelRows = [
  {
    tag: 'V-101',
    type: 'Vertical Tank',
    diameterM: 2.8,
    heightM: 9,
    orientationDeg: 0,
    rowRef: 'row-2',
    excelFileName: 'equipment_list.xlsx',
  },
  {
    tag: 'E-205',
    type: 'Exchanger',
    diameterM: 1.2,
    lengthM: 6.5,
    orientationDeg: 90,
    rowRef: 'row-3',
    excelFileName: 'equipment_list.xlsx',
  },
  {
    tag: 'P-330',
    type: 'Pump',
    widthM: 1.2,
    lengthM: 2.4,
    heightM: 1.5,
    orientationDeg: 180,
    rowRef: 'row-4',
    excelFileName: 'equipment_list.xlsx',
  },
]

const seedPdfPositionsByTag = {
  'V-101': {
    x: 0,
    y: 0,
    rotationDeg: 0,
    confidence: 0.58,
    pageRef: 'p1',
    annotationRef: 'A-14',
    pdfFileName: 'plot_plan.pdf',
  },
  'E-205': {
    x: 7,
    y: -4,
    rotationDeg: 90,
    confidence: 0.52,
    pageRef: 'p1',
    annotationRef: 'A-47',
    pdfFileName: 'plot_plan.pdf',
  },
}

export const seedMergedModel = mergeEquipmentData({
  excelRows: seedExcelRows,
  pdfPositionsByTag: seedPdfPositionsByTag,
  projectName: 'Seed Model (Structure + Strategy Demo)',
})
