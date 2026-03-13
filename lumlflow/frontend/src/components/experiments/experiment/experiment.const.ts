import type { Experiment } from '@/store/experiments/experiments.interface'
import { Check, CircleX, Timer } from 'lucide-vue-next'

export const BREADCRUMBS_PT = {
  root: {
    style: 'padding-left: 0',
  },
}

export const CONSTANTS_COLUMNS: string[] = [
  'Experiment name',
  'Creation time',
  'Description',
  'Tags',
  'Duration',
  'Source',
  'Models',
]

export const getStatusIconInfo = (status: Experiment['status']) => {
  if (status === 'completed') return { icon: Check, color: 'var(--p-tag-success-color)' }
  if (status === 'active') return { icon: Timer, color: 'var(--p-tag-info-color)' }
  return { icon: CircleX, color: 'var(--p-tag-danger-color)' }
}
