import type { CellStaleState } from '@/api/slices/workspace/workspace.interface'
import type { CellTab } from '@/components/notebooks/cell/cell.interface'
import type { LucideIcon } from 'lucide-vue-next'
import type { MenuPassThroughOptions, TabListPassThroughOptions } from 'primevue'
import {
  AlertTriangle,
  ChartSpline,
  CheckCircle2,
  CircleDashed,
  CodeXml,
  RefreshCw,
  Scroll,
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

export const NOTEBOOK_CELL_TABS: CellTab[] = [
  { label: 'Plot', icon: ChartSpline, value: 'plot' },
  { label: 'Code', icon: CodeXml, value: 'code' },
  { label: 'Logs', icon: Scroll, value: 'logs' },
]
