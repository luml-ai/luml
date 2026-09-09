import {
  ChartBar,
  ChartSpline,
  CircuitBoard,
  FlaskConical,
  Notebook,
  Table2,
  Workflow,
  type LucideIcon,
} from 'lucide-vue-next'
import type { NotebookAssetType, ViewModeOption } from './notebooks.interface'

export const NOTEBOOK_ASSET_ICONS: Record<NotebookAssetType, LucideIcon> = {
  dataset: Table2,
  experiment: FlaskConical,
  graph: ChartSpline,
  model: CircuitBoard,
  unknown: ChartBar,
}

export const NOTEBOOK_CANVAS_NODE_WIDTH = 450
export const NOTEBOOK_CANVAS_LEVEL_HEIGHT = 550

export const NOTEBOOK_VIEW_MODE_OPTIONS: ViewModeOption[] = [
  { label: 'Canvas', value: 'canvas', icon: Workflow },
  { label: 'Notebook', value: 'notebook', icon: Notebook },
]
