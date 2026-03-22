import { zodResolver } from '@primevue/forms/resolvers/zod'
import type { DialogPassThroughOptions } from 'primevue'
import z from 'zod'
import { UploadTypeEnum } from './upload.interface'

type Resolver = ReturnType<typeof zodResolver>

export const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    class: 'w-[500px]',
  },
  header: {
    class: 'text-xl uppercase',
  },
}

export const resolver: Resolver = zodResolver(
  z
    .object({
      type: z.enum([UploadTypeEnum.AUTO, UploadTypeEnum.MODEL, UploadTypeEnum.EXPERIMENT]),
      organization: z.string().nullable(),
      orbit: z.string().nullable(),
      collection: z.string().nullable(),
      name: z.string().min(3).max(255),
      description: z
        .string()
        .max(255)
        .refine((val) => !val || val.length >= 3, {
          message: 'Description must be at least 3 characters if not empty',
        }),
      tags: z.array(z.string().min(3).max(255)),
      embedExperiment: z.boolean(),
    })
    .superRefine((data, ctx) => {
      if (!data.organization) {
        ctx.addIssue({
          path: ['organization'],
          code: z.ZodIssueCode.custom,
          message: 'Organization is required',
        })
      }

      if (data.organization && !data.orbit) {
        ctx.addIssue({
          path: ['orbit'],
          code: z.ZodIssueCode.custom,
          message: 'Orbit is required',
        })
      }

      if (data.orbit && !data.collection) {
        ctx.addIssue({
          path: ['collection'],
          code: z.ZodIssueCode.custom,
          message: 'Collection is required',
        })
      }
    }),
)

export const selectTypeOptions = [
  {
    label: 'Auto',
    value: UploadTypeEnum.AUTO,
  },
  {
    label: 'Model',
    value: UploadTypeEnum.MODEL,
  },
  {
    label: 'Experiment',
    value: UploadTypeEnum.EXPERIMENT,
  },
]
