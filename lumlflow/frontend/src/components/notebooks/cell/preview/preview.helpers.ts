import type {
  FileBlock,
  ImageBlock,
  MarkdownBlock,
  PreviewBlock,
  SeriesBlock,
  TableBlock,
} from '@/api/slices/workspace/workspace.interface'

export type KvValue = string | number | boolean | null

export type PreviewSection =
  | { kind: 'lines'; title: string | null; series: SeriesBlock[] }
  | { kind: 'bars'; title: string | null; entries: [string, number][] }
  | { kind: 'kv'; title: string | null; entries: [string, KvValue][] }
  | { kind: 'table'; title: string | null; block: TableBlock }
  | { kind: 'image'; title: string | null; block: ImageBlock }
  | { kind: 'markdown'; title: string | null; block: MarkdownBlock }
  | { kind: 'file'; title: string | null; block: FileBlock }

export const COMPACT_KV_ROWS = 7

const HEADING = /^\s*\*\*([^*\n]+)\*\*\s*$/

function headingOf(block: PreviewBlock): string | null {
  if (block.block !== 'markdown') return null
  const match = HEADING.exec(block.text)
  return match ? (match[1] ?? '').trim() : null
}

function numericEntries(entries: [string, KvValue][]): [string, number][] | null {
  if (entries.length < 2) return null
  const numeric = entries.filter((entry): entry is [string, number] => typeof entry[1] === 'number')
  return numeric.length === entries.length ? numeric : null
}

export function previewSections(blocks: PreviewBlock[]): PreviewSection[] {
  const sections: PreviewSection[] = []
  let title: string | null = null
  const take = (): string | null => {
    const held = title
    title = null
    return held
  }

  for (const block of blocks) {
    const heading = headingOf(block)
    if (heading !== null) {
      if (title !== null) {
        sections.push({
          kind: 'markdown',
          title: null,
          block: { block: 'markdown', text: `**${title}**` },
        })
      }
      title = heading
      continue
    }
    const last = sections[sections.length - 1]
    switch (block.block) {
      case 'series':
        if (last?.kind === 'lines' && title === null) last.series.push(block)
        else sections.push({ kind: 'lines', title: take(), series: [block] })
        break
      case 'kv': {
        const entries = Object.entries(block.entries)
        const numeric = numericEntries(entries)
        if (numeric) sections.push({ kind: 'bars', title: take(), entries: numeric })
        else sections.push({ kind: 'kv', title: take(), entries })
        break
      }
      case 'table':
        sections.push({ kind: 'table', title: take(), block })
        break
      case 'image':
        sections.push({ kind: 'image', title: take(), block })
        break
      case 'markdown':
        sections.push({ kind: 'markdown', title: take(), block })
        break
      default:
        sections.push({ kind: 'file', title: take(), block })
    }
  }
  if (title !== null) {
    sections.push({
      kind: 'markdown',
      title: null,
      block: { block: 'markdown', text: `**${title}**` },
    })
  }
  return sections
}

export function hasChart(sections: PreviewSection[]): boolean {
  return sections.some((section) => section.kind === 'lines' || section.kind === 'bars')
}
