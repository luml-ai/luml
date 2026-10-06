import type {
  FileBlock,
  ImageBlock,
  MarkdownBlock,
  PreviewBlock,
  TableBlock,
} from '@/api/slices/workspace/workspace.interface'
import type { CellTabContent } from '@/composables/useCellTabs'
import type { KvValue, PreviewSection } from './preview.helpers'

export interface CellChartProps {
  section: Extract<PreviewSection, { kind: 'lines' | 'bars' }>
  hidden: Set<number>
}

export interface CellChartFilterProps {
  metrics: { name: string; color: string }[]
}

export interface CellFileBlockProps {
  block: FileBlock
}

export interface CellKeyValueBlockProps {
  entries: [string, KvValue][]
  limit?: number | null
}

export interface CellMarkdownBlockProps {
  block: MarkdownBlock
}

export interface CellOutputTabContentProps {
  content: CellTabContent
  compact?: boolean
  slug?: string
}

export interface CellPlotImageProps {
  block: ImageBlock
}

export interface CellPreviewBlocksProps {
  blocks: PreviewBlock[]
  truncated: boolean
  compact?: boolean
  slug?: string
}

export interface CellTableBlockProps {
  block: TableBlock
}
