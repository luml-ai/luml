import type { LucideIcon } from 'lucide-vue-next'
import {
  Archive,
  Box,
  Database,
  File,
  FileText,
  FlaskConical,
  Gauge,
  Globe,
  Image,
  LayoutList,
  LineChart,
  ListChecks,
  Table2,
  Type,
} from 'lucide-vue-next'
import type { AssetKind } from '../model/types'

export const KIND_ICONS: Record<AssetKind, LucideIcon> = {
  frame: Table2,
  plot: LineChart,
  metric: Gauge,
  note: FileText,
  eval: ListChecks,
  model: Box,
  dataset: Database,
  experiment: FlaskConical,
  checkpoint: Archive,
  file: File,
  image: Image,
  text: Type,
  html: Globe,
  unknown: LayoutList,
}

const BRANCH_PALETTE = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#f97316',
  '#84cc16',
]

export function branchColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) | 0
  return BRANCH_PALETTE[Math.abs(hash) % BRANCH_PALETTE.length]
}
