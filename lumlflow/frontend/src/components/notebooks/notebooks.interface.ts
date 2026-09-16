import type { CellStaleState, CellSummary } from '@/api/slices/workspace/workspace.interface'
import type { LucideIcon } from 'lucide-vue-next'

export type NotebookAssetType = 'graph' | 'model' | 'dataset' | 'experiment' | 'unknown'

export interface NotebookAssetInterface {
  id: string
  type: NotebookAssetType
  name: string
  unmaterialized: boolean
}

export interface CellNodeData {
  asset: NotebookAssetInterface
  cell: CellSummary
}

export interface CellEdge {
  from: string
  to: string
  input: string
}

export interface ViewModeOption {
  label: string
  value: 'canvas' | 'notebook'
  icon: LucideIcon
}

export interface ReactivityOption {
  label: string
  value: 'lazy' | 'auto'
}

export interface NotebooksCanvasToolbarEmits {
  zoomIn: []
  zoomOut: []
  zoomChange: [value: number]
}

export interface SidebarTooltipPlugProps {
  tooltip: string
  label: string
}

export interface PairableAgentInterface {
  id: string
  name: string
  icon: LucideIcon
}

export type NotebookHealthState = CellStaleState | 'empty'
