import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { emptyToUndefined } from './helpers'

export const experimentResolver = zodResolver(
  z.object({
    name: z.string().min(3).max(255),
    description: emptyToUndefined(z.string().min(3).max(255).optional()),
    tags: emptyToUndefined(z.array(z.string().min(3).max(255))).optional(),
  }),
)
