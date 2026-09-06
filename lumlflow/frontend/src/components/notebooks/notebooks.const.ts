import {
  ChartBar,
  ChartSpline,
  CircuitBoard,
  FlaskConical,
  Table2,
  type LucideIcon,
} from 'lucide-vue-next'
import type { NotebookAssetType } from './notebooks.interface'

export const NOTEBOOK_ASSET_ICONS: Record<NotebookAssetType, LucideIcon> = {
  dataset: Table2,
  experiment: FlaskConical,
  graph: ChartSpline,
  model: CircuitBoard,
  unknown: ChartBar,
}
