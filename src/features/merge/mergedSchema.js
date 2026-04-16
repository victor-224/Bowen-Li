export const mergedEquipmentSchema = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  title: 'MergedEquipmentDataset',
  type: 'object',
  required: ['meta', 'equipment'],
  properties: {
    meta: {
      type: 'object',
      required: ['version', 'createdAt', 'sourceFiles'],
      properties: {
        version: { type: 'string' },
        createdAt: { type: 'string' },
        sourceFiles: {
          type: 'object',
          required: ['excel', 'pdf2d'],
          properties: {
            excel: { type: 'string' },
            pdf2d: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      },
    },
    equipment: {
      type: 'array',
      items: {
        type: 'object',
        required: [
          'id',
          'tag',
          'size',
          'orientation',
          'geometryProxy',
          'position',
          'positionStatus',
          'confidence',
          'source',
        ],
        properties: {
          id: { type: 'string' },
          tag: { type: 'string' },
          size: { type: 'string' },
          orientation: {
            type: 'string',
            enum: ['vertical', 'horizontal', 'unknown'],
          },
          type: { type: 'string' },
          geometryProxy: {
            type: 'string',
            enum: [
              'verticalCylinder',
              'horizontalCylinder',
              'box',
              'pumpProxy',
              'unknown',
            ],
          },
          position: {
            type: 'object',
            required: ['x', 'y', 'rotationDeg'],
            properties: {
              x: { type: ['number', 'null'] },
              y: { type: ['number', 'null'] },
              rotationDeg: { type: ['number', 'null'] },
            },
          },
          positionStatus: {
            type: 'string',
            enum: ['corrected', 'approximate', 'unresolved'],
          },
          confidence: {
            type: 'number',
            minimum: 0,
            maximum: 1,
          },
          source: {
            type: 'object',
            required: ['excel'],
            properties: {
              excel: {
                type: 'object',
                required: ['rowIndex', 'tagField', 'sizeField', 'orientationField'],
                properties: {
                  rowIndex: { type: 'number' },
                  tagField: { type: 'string' },
                  sizeField: { type: 'string' },
                  orientationField: { type: 'string' },
                },
              },
              pdf2d: {
                type: ['object', 'null'],
                properties: {
                  page: { type: 'number' },
                  markerId: { type: 'string' },
                  method: { type: 'string' },
                },
              },
              manualCorrection: {
                type: ['object', 'null'],
                properties: {
                  correctedAt: { type: 'string' },
                  correctedBy: { type: 'string' },
                  reason: { type: 'string' },
                },
              },
            },
          },
          unresolvedReason: { type: ['string', 'null'] },
        },
      },
    },
  },
}
