import { zodResolver } from '@primevue/forms/resolvers/zod'
import { Smile, Target, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { z } from 'zod'
import { AnnotationKind, AnnotationValueType } from '../annotations.interface'

type Resolver = ReturnType<typeof zodResolver>

export const INITIAL_VALUES = {
  type: AnnotationKind.FEEDBACK,
  name: '',
  dataType: AnnotationValueType.BOOL,
  value: true,
  rationale: '',
}

export const RESOLVER: Resolver = zodResolver(
  z.object({
    type: z.enum([AnnotationKind.FEEDBACK, AnnotationKind.EXPECTATION]),
    name: z.string().min(1),
    dataType: z.enum([
      AnnotationValueType.BOOL,
      AnnotationValueType.STRING,
      AnnotationValueType.INT,
    ]),
    value: z.any(),
    rationale: z.string().min(1),
  }),
)

export const TYPE_OPTIONS: { label: string; value: AnnotationKind }[] = [
  { label: 'Feedback', value: AnnotationKind.FEEDBACK },
  { label: 'Expectation', value: AnnotationKind.EXPECTATION },
]

export const TYPE_ICONS: Record<AnnotationKind, { icon: any; iconColor: string }> = {
  feedback: {
    icon: Smile,
    iconColor: 'var(--p-charts-color-3)',
  },
  expectation: {
    icon: Target,
    iconColor: 'var(--p-charts-color-1)',
  },
}

export const DATA_TYPE_OPTIONS: { label: string; value: AnnotationValueType }[] = [
  { label: 'Boolean', value: AnnotationValueType.BOOL },
  { label: 'String', value: AnnotationValueType.STRING },
  { label: 'Number', value: AnnotationValueType.INT },
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
