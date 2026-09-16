import type {
  FileBlock,
  ImageBlock,
  KvBlock,
  MarkdownBlock,
  PreviewBlock,
  SeriesBlock,
  TableBlock,
} from '@/api/slices/workspace/workspace.interface'
import type { CellTabContent } from '@/composables/useCellTabs'

export interface CellBarChartProps {
  entries: [string, number][]
}

export interface CellFileBlockProps {
  block: FileBlock
}

export interface CellKeyValueBlockProps {
  block: KvBlock
}

export interface CellLineChartProps {
  block: SeriesBlock
}

export interface CellMarkdownBlockProps {
  block: MarkdownBlock
}

export interface CellOutputTabContentProps {
  content: CellTabContent
}

export interface CellPlotImageProps {
  block: ImageBlock
}

export interface CellPreviewBlocksProps {
  blocks: PreviewBlock[]
  truncated: boolean
}

export interface CellTableBlockProps {
  block: TableBlock
}
