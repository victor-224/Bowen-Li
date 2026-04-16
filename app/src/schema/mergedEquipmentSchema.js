import { z } from 'zod'

export const POSITION_STATUS = {
  RESOLVED: 'resolved',
  APPROXIMATE: 'approximate',
  UNRESOLVED: 'unresolved',
}

const SourcePrioritySchema = z.object({
  tag: z.literal('excel'),
  size: z.literal('excel'),
  orientation: z.literal('excel'),
  position: z.literal('pdf-2d-approx'),
})

const DimensionsSchema = z.object({
  diameterM: z.number().nullable().optional(),
  lengthM: z.number().nullable().optional(),
  widthM: z.number().nullable().optional(),
  heightM: z.number().nullable().optional(),
})

const PositionSchema = z.object({
  x: z.number().nullable(),
  y: z.number().nullable(),
  z: z.number().default(0),
  rotationDeg: z.number().nullable(),
  status: z.enum([
    POSITION_STATUS.RESOLVED,
    POSITION_STATUS.APPROXIMATE,
    POSITION_STATUS.UNRESOLVED,
  ]),
  confidence: z.number().min(0).max(1),
  note: z.string().min(1),
})

const SourceTraceSchema = z.object({
  excel: z.object({
    fileName: z.string().min(1),
    rowRef: z.string().min(1),
  }),
  pdf2d: z
    .object({
      fileName: z.string().min(1),
      pageRef: z.string().min(1),
      annotationRef: z.string().min(1),
    })
    .nullable(),
})

const ManualCorrectionSchema = z.object({
  isEdited: z.boolean(),
  editedAtIso: z.string().nullable(),
  reason: z.string().nullable(),
})

export const EquipmentRecordSchema = z.object({
  id: z.string().min(1),
  tag: z.string().min(1),
  type: z.enum([
    'vertical-tank',
    'vertical-drum',
    'horizontal-drum',
    'exchanger',
    'compressor',
    'pump',
    'unknown',
  ]),
  geometryPrimitive: z.enum([
    'vertical-cylinder',
    'horizontal-cylinder',
    'box',
    'proxy',
  ]),
  dimensions: DimensionsSchema,
  orientationDeg: z.number(),
  position: PositionSchema,
  sourcePriority: SourcePrioritySchema,
  sourceTrace: SourceTraceSchema,
  manualCorrection: ManualCorrectionSchema,
})

export const MergedModelSchema = z.object({
  generatedAtIso: z.string(),
  projectName: z.string().min(1),
  assumptions: z.array(z.string()),
  equipment: z.array(EquipmentRecordSchema),
})

export function validateMergedModel(model) {
  return MergedModelSchema.parse(model)
}
