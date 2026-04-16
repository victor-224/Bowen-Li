import { POSITION_STATUS } from '../schema/mergedEquipmentSchema'

export const parseStrategy = {
  coreRule: 'Excel is source-of-truth for tag, size, orientation.',
  positionRule:
    '2D PDF positions are approximate only and must be tagged with confidence.',
  noGuessingRule:
    'If coordinates cannot be extracted reliably, mark unresolved with null coordinates.',
  confidenceBands: {
    resolved: [0.85, 1],
    approximate: [0.3, 0.84],
    unresolved: [0, 0.29],
  },
}

const GEOMETRY_BY_TYPE = {
  'vertical-tank': 'vertical-cylinder',
  'vertical-drum': 'vertical-cylinder',
  'horizontal-drum': 'horizontal-cylinder',
  exchanger: 'horizontal-cylinder',
  compressor: 'box',
  pump: 'proxy',
  unknown: 'proxy',
}

export function inferGeometryPrimitive(type) {
  return GEOMETRY_BY_TYPE[type] ?? 'proxy'
}

export function classifyPosition(confidence) {
  if (confidence >= 0.85) {
    return POSITION_STATUS.RESOLVED
  }

  if (confidence >= 0.3) {
    return POSITION_STATUS.APPROXIMATE
  }

  return POSITION_STATUS.UNRESOLVED
}
