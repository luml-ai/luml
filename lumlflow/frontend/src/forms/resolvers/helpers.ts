import { z } from 'zod'

/**
 * Converts empty values ('', null, []) to undefined
 * and applies the provided schema as optional
 */
export const emptyToUndefined = <T extends z.ZodTypeAny>(schema: T) =>
  z.preprocess(
    (value) =>
      value === '' || value === null || (Array.isArray(value) && value.length === 0)
        ? undefined
        : value,
    schema.optional(),
  )
