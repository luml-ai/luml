import type { CellStaleState, CellSummary } from '@/api/slices/workspace/workspace.interface'
import type { NotebookAssetInterface } from '@/components/notebooks/notebooks.interface'
import type { LucideIcon } from 'lucide-vue-next'
import type { MenuItem } from 'primevue/menuitem'

export interface ExpandedCellProps {
  cell: CellSummary
}

export interface NotebookCellProps {
  title: string
  icon: LucideIcon
  costSeconds: number | null
  state: CellStaleState
  causes: string[]
  reused: boolean
  cell: CellSummary
}

export interface NotebookCellFooterProps {
  state: CellStaleState
  causes: string[]
  reused: boolean
  cell: CellSummary
}

export interface NotebookCellHeaderProps {
  title: string
  icon: LucideIcon
  costSeconds: number | null
  cell: CellSummary
}

export type CellHeaderMenuItem = MenuItem & { glyph?: LucideIcon }

export interface NotebookCellNodeProps {
  asset: NotebookAssetInterface
  cell: CellSummary
  isSelected?: boolean
}

export interface CellTab {
  id: string
  label: string
  icon: LucideIcon
}

export interface NotebookLogsProps {
  slug: string
}

export interface NotebookCodeProps {
  slug: string
}

export interface NotebookOutputProps {
  slug: string
  name: string
}

export interface NotebookCellTabsProps {
  tabs: CellTab[]
}
