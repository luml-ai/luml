import type { Experiment } from '@/store/experiments/experiments.interface'
import { Check, CircleX, Timer } from 'lucide-vue-next'

export const BREADCRUMBS_PT = {
  root: {
    style: 'padding-left: 0',
  },
}

export const AUTOCOMPLETE_PT = {
  optionGroup: 'font-normal!',
}

export const SEARCH_ICON_TOOLTIP_PT = {
  root: '!max-w-[302px]',
  text: 'w-[284px] text-sm',
}

export const AUTOCOMPLETE_VIRTUAL_SCROLLER_OPTIONS = {
  itemSize: 32,
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

export const AUTOCOMPLETE_TOOLTIP = `Search runs using a simplified version of the
  SQL.

  Examples:
  • metrics.rmse >= 0.8
  • params.model = 'tree'
  • attributes.run_name = 'my run'
  • tags.\`mlflow.user\` = 'myUser'
  • metric.f1_score > 0.9 AND params.model = 'tree'
  • dataset.name IN ('dataset1', 'dataset2')
  • attributes.run_id IN ('a1b2c3d4', 'e5f6g7h8')
  • tags.model_class LIKE 'sklearn.linear_model%'
`
