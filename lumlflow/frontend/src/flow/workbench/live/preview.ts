import type { StoredPreview, TrackerExperiment } from '@/flow/api/types'
import type {
  AssetKind,
  BlocksPreview,
  ExperimentPreview,
  KvPreview,
  ParamValue,
  PreviewBlock,
  PreviewValue,
} from '../model/types'
import type { MetricValue } from '../model/format'

export const PREVIEW_SCHEMA = 1

export const NEWER_FORMAT_NOTE = 'newer preview format. showing the parts this build understands.'

const KINDS: Record<string, AssetKind> = {
  frame: 'frame',
  plot: 'plot',
  metric: 'metric',
  note: 'note',
  eval: 'eval',
  model: 'model',
  dataset: 'dataset',
  experiment: 'experiment',
  checkpoint: 'checkpoint',
  file: 'file',
  image: 'image',
  text: 'text',
  html: 'html',
}

export function assetKindOf(kind: string | null | undefined): AssetKind {
  return (kind && KINDS[kind]) || 'unknown'
}

export interface PreviewContext {
  runName?: string
  tracker?: TrackerExperiment | null
}

export function previewFrom(
  stored: StoredPreview | null | undefined,
  context: PreviewContext = {},
): PreviewValue {
  const kind = assetKindOf(stored?.kind)
  if (!stored || !Array.isArray(stored.blocks)) return empty(kind)
  if (!(stored.schema <= PREVIEW_SCHEMA)) return newerFormat(stored)
  const blocks = stored.blocks.map(readBlock).filter((block): block is PreviewBlock => !!block)
  if (kind === 'experiment') return experimentFrom(blocks, context)
  return { type: 'blocks', kind, blocks, truncated: stored.truncated }
}

const SECTION = /^\*\*(params|metrics)\*\*$/

function experimentFrom(blocks: PreviewBlock[], context: PreviewContext): ExperimentPreview {
  const sections = new Map<string, Record<string, ParamValue>>()
  let section = ''
  for (const block of blocks) {
    if (block.block === 'markdown') {
      section = SECTION.exec(block.text.trim())?.[1] ?? section
    } else if (block.block === 'kv' && section) {
      sections.set(section, { ...(sections.get(section) ?? {}), ...block.entries })
    }
  }
  const metrics = Object.entries(sections.get('metrics') ?? {}).flatMap(([name, value]) => {
    const metric = metricValue(value)
    return metric === null ? [] : [{ name, value: metric }]
  })
  return {
    type: 'experiment',
    runName: context.runName ?? 'experiment',
    mainMetric: metrics[0],
    metrics: metrics.slice(1),
    config: sections.get('params') ?? {},
    curves: [],
    tracker: context.tracker ?? undefined,
  }
}

function metricValue(value: ParamValue): MetricValue | null {
  if (typeof value === 'number') return value
  return value === 'nan' || value === 'inf' || value === '-inf' ? value : null
}

function empty(kind: AssetKind): BlocksPreview {
  return { type: 'blocks', kind, blocks: [] }
}

function newerFormat(stored: StoredPreview): KvPreview {
  const entries: Record<string, string | number | boolean> = {}
  for (const raw of stored.blocks) {
    const block = readBlock(raw)
    if (block?.block !== 'kv') continue
    for (const [name, value] of Object.entries(block.entries)) {
      if (value !== null && !Array.isArray(value)) entries[name] = value
    }
  }
  return {
    type: 'kv',
    entries,
    newerFormatNote: stored.truncated
      ? `${NEWER_FORMAT_NOTE} the payload also shrank to fit.`
      : NEWER_FORMAT_NOTE,
  }
}

function readBlock(raw: unknown): PreviewBlock | null {
  if (typeof raw !== 'object' || raw === null) return null
  const block = raw as Record<string, unknown>
  switch (block.block) {
    case 'table':
      return {
        block: 'table',
        columns: strings(block.columns),
        dtypes: strings(block.dtypes),
        rows: rows(block.rows),
        totalRows: count(block.total_rows),
        totalColumns: count(block.total_columns),
      }
    case 'series':
      return {
        block: 'series',
        name: text(block.name),
        points: points(block.points),
        totalPoints: count(block.total_points),
      }
    case 'image':
      return { block: 'image', mime: text(block.mime), data: text(block.data) }
    case 'markdown':
      return { block: 'markdown', text: text(block.text) }
    case 'kv':
      return { block: 'kv', entries: entriesOf(block.entries) }
    case 'file':
      return {
        block: 'file',
        name: text(block.name),
        size: count(block.size),
        contentType: text(block.content_type) || 'application/octet-stream',
      }
    default:
      return null
  }
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(text) : []
}

function rows(value: unknown): (string | number | boolean | null)[][] {
  if (!Array.isArray(value)) return []
  return value.map((row) => (Array.isArray(row) ? row.map(scalar) : []))
}

function points(value: unknown): [number, number][] {
  if (!Array.isArray(value)) return []
  return value
    .filter(
      (point): point is [number, number] =>
        Array.isArray(point) && point.length >= 2 && numeric(point[0]) && numeric(point[1]),
    )
    .map((point) => [point[0], point[1]])
}

function numeric(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function entriesOf(value: unknown): Record<string, ParamValue> {
  if (typeof value !== 'object' || value === null) return {}
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([name, entry]) => [name, scalar(entry)]),
  )
}

function scalar(value: unknown): string | number | boolean | null {
  if (value === null || value === undefined) return null
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') {
    return value
  }
  return JSON.stringify(value)
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function count(value: unknown): number {
  return numeric(value) ? value : 0
}
