import {
  ChartBar,
  ChartSpline,
  CircleOff,
  CircuitBoard,
  FlaskConical,
  LoaderCircle,
  Notebook,
  Table2,
  Workflow,
  type LucideIcon,
} from 'lucide-vue-next'
import type {
  NotebookAssetType,
  NotebookHealthState,
  NotebookHealthView,
  ReactivityOption,
  ViewModeOption,
} from './notebooks.interface'
import { CELL_STATE_ICONS, CELL_STATE_LABELS } from './cell/cell.const'

export const NOTEBOOK_ASSET_ICONS: Record<NotebookAssetType, LucideIcon> = {
  dataset: Table2,
  experiment: FlaskConical,
  graph: ChartSpline,
  model: CircuitBoard,
  unknown: ChartBar,
}

export const NOTEBOOK_CANVAS_NODE_WIDTH = 450
export const NOTEBOOK_CANVAS_LEVEL_HEIGHT = 680

export const NOTEBOOK_VIEW_MODE_OPTIONS: ViewModeOption[] = [
  { label: 'Canvas', value: 'canvas', icon: Workflow },
  { label: 'Notebook', value: 'notebook', icon: Notebook },
]

export const NOTEBOOK_REACTIVITY_OPTIONS: ReactivityOption[] = [
  { label: 'Lazy', value: 'lazy' },
  { label: 'Auto', value: 'auto' },
]

export const NOTEBOOK_REACTIVITY_HINTS: Record<ReactivityOption['value'], string> = {
  lazy: 'Nothing runs until you ask for it.',
  auto: 'A cell already timed under this refreshes itself when something above it changes. Anything dearer waits for you, and says so on the card.',
}

export const NOTEBOOK_HEALTH: Record<NotebookHealthState, NotebookHealthView> = {
  synced: {
    severity: 'success',
    label: 'Settled',
    tooltip: 'All cells are up to date',
    icon: CELL_STATE_ICONS.synced,
  },
  running: {
    severity: 'info',
    label: 'Running',
    tooltip: 'Cells are running on this lane',
    icon: LoaderCircle,
  },
  unsynced: {
    severity: 'warn',
    label: 'Stale',
    tooltip: 'Some cells are out of date and need to re-run',
    icon: CELL_STATE_ICONS.unsynced,
  },
  unmaterialized: {
    severity: 'secondary',
    label: CELL_STATE_LABELS.unmaterialized,
    tooltip: 'Some cells have not been run yet',
    icon: CELL_STATE_ICONS.unmaterialized,
  },
  failed: {
    severity: 'danger',
    label: CELL_STATE_LABELS.failed,
    tooltip: 'One or more cells failed to run',
    icon: CELL_STATE_ICONS.failed,
  },
  empty: {
    severity: 'secondary',
    label: 'Empty',
    tooltip: 'This lane has no cells yet',
    icon: CircleOff,
  },
}
