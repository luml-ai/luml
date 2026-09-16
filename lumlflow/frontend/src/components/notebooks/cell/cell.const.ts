import type { CellStaleState } from '@/api/slices/workspace/workspace.interface'
import type { LucideIcon } from 'lucide-vue-next'
import type { MenuPassThroughOptions, TabListPassThroughOptions } from 'primevue'
import {
  AlertTriangle,
  ChartBar,
  ChartSpline,
  CheckCircle2,
  CircleDashed,
  CircuitBoard,
  ClipboardCheck,
  FlaskConical,
  RefreshCw,
  Save,
  StickyNote,
  Table2,
} from 'lucide-vue-next'

export const CELL_STATE_LABELS: Record<CellStaleState, string> = {
  synced: 'Up to date',
  unsynced: 'Out of date',
  unmaterialized: 'Not materialized',
  failed: 'Failed',
}

export const CELL_STATE_ICONS: Record<CellStaleState, LucideIcon> = {
  synced: CheckCircle2,
  unsynced: RefreshCw,
  unmaterialized: CircleDashed,
  failed: AlertTriangle,
}

export const CELL_NAME_UNSAFE = /[\x00-\x1f\x7f/\\:*?"<>|]/

export const CELL_NAME_INVALID_MESSAGE =
  'Name cannot start with a dot, contain ".." or invalid characters'

export function isValidCellName(name: string): boolean {
  if (!name) return false
  if (name.startsWith('.')) return false
  if (name.includes('..')) return false
  if (CELL_NAME_UNSAFE.test(name)) return false

  return true
}

export const CELL_HEADER_MENU_PT: MenuPassThroughOptions = {
  root: {
    style: 'background-color: var(--p-card-background);',
  },
}

export const CELL_TABS_LIST_PT: TabListPassThroughOptions = {
  root: {
    class: 'bg-transparent!',
  },
  tabList: {
    style: 'border-left: none; border-top: none; border-right: none; ',
  },
}

export const CELL_OUTPUT_KIND_ICONS: Record<string, LucideIcon> = {
  plot: ChartSpline,
  frame: Table2,
  dataset: Table2,
  model: CircuitBoard,
  experiment: FlaskConical,
  metric: ChartBar,
  eval: ClipboardCheck,
  checkpoint: Save,
  note: StickyNote,
}

export const DEFAULT_OUTPUT_KIND_ICON: LucideIcon = ChartBar
