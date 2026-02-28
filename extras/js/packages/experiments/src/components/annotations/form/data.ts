import { zodResolver } from '@primevue/forms/resolvers/zod'
import { Smile, Target, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { z } from 'zod'

type Resolver = ReturnType<typeof zodResolver>

export type AnnotationType = 'feedback' | 'expectation'

export type DataType = 'boolean' | 'string' | 'number' | 'date'

export const INITIAL_VALUES = {
  type: 'feedback',
  name: '',
  dataType: 'boolean',
  value: true,
  rationale: '',
}

export const RESOLVER: Resolver = zodResolver(
  z.object({
    type: z.enum(['feedback', 'expectation']),
    name: z.string().min(1),
    dataType: z.enum(['boolean', 'string', 'number', 'date']),
    value: z.any(),
    rationale: z.string().min(1),
  }),
)

export const TYPE_OPTIONS: { label: string; value: AnnotationType }[] = [
  { label: 'Feedback', value: 'feedback' },
  { label: 'Expectation', value: 'expectation' },
]

export const TYPE_ICONS: Record<AnnotationType, { icon: any; iconColor: string }> = {
  feedback: {
    icon: Smile,
    iconColor: 'var(--p-charts-color-3)',
  },
  expectation: {
    icon: Target,
    iconColor: 'var(--p-charts-color-1)',
  },
}

export const DATA_TYPE_OPTIONS: { label: string; value: DataType }[] = [
  { label: 'Boolean', value: 'boolean' },
]

export const VALUE_OPTIONS: { label: string; value: boolean }[] = [
  { label: 'True', value: true },
  { label: 'False', value: false },
]

export const VALUE_ICONS: Record<'true' | 'false', { icon: any; iconColor: string }> = {
  true: {
    icon: ThumbsUp,
    iconColor: 'var(--p-green-500)',
  },
  false: {
    icon: ThumbsDown,
    iconColor: 'var(--p-red-500)',
  },
}
