import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { emptyToUndefined } from './helpers'

type Resolver = ReturnType<typeof zodResolver>

export const experimentGroupResolver: Resolver = zodResolver(
  z.object({
    name: z.string().min(3).max(255),
    description: emptyToUndefined(z.string().min(3).max(255).optional()),
    tags: emptyToUndefined(z.array(z.string().min(3).max(255))).optional(),
  }),
)
