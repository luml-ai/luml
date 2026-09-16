import {
  Bot,
  ChartBar,
  ChartSpline,
  CircuitBoard,
  Cpu,
  FlaskConical,
  Notebook,
  Sparkles,
  Table2,
  Wand2,
  Workflow,
  type LucideIcon,
} from 'lucide-vue-next'
import type {
  NotebookAssetType,
  NotebookHealthState,
  PairableAgentInterface,
  ReactivityOption,
  ViewModeOption,
} from './notebooks.interface'

export const NOTEBOOK_ASSET_ICONS: Record<NotebookAssetType, LucideIcon> = {
  dataset: Table2,
  experiment: FlaskConical,
  graph: ChartSpline,
  model: CircuitBoard,
  unknown: ChartBar,
}

export const NOTEBOOK_CANVAS_NODE_WIDTH = 450
export const NOTEBOOK_CANVAS_LEVEL_HEIGHT = 550

export const NOTEBOOK_TERMINAL_HEIGHT = 180

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

export const NOTEBOOK_PAIRABLE_AGENTS: PairableAgentInterface[] = [
  { id: 'claude', name: 'Claude', icon: Bot },
  { id: 'codex', name: 'Codex', icon: Cpu },
  { id: 'cursor', name: 'Cursor', icon: Sparkles },
  { id: 'windsurf', name: 'Windsurf', icon: Wand2 },
]

export const NOTEBOOK_HEALTH_LABELS: Record<NotebookHealthState, string> = {
  synced: 'All cells are up to date',
  unsynced: 'Some cells are out of date and need to re-run',
  unmaterialized: 'Some cells have not been run yet',
  failed: 'One or more cells failed to run',
  empty: 'This lane has no cells yet',
}

export const NOTEBOOK_HEALTH_SEVERITY: Record<
  NotebookHealthState,
  'success' | 'warn' | 'info' | 'danger' | 'secondary'
> = {
  synced: 'success',
  unsynced: 'warn',
  unmaterialized: 'info',
  failed: 'danger',
  empty: 'secondary',
}
