/**
 * The stored preview, turned into something the renderers accept.
 *
 * The envelope is the UI contract, and it is versioned because it will outlive
 * this build: a daemon a version ahead may send blocks nobody here has heard
 * of. So the rule is the schema's own — **a payload this build cannot vouch for
 * renders as the kv fallback with a note saying why**, never as a guess and
 * never as an error. Within a version it understands, blocks it does not
 * recognise are dropped rather than allowed to break the ones beside them.
 *
 * Nothing is inferred back out of a payload. A per-kind view wants fields the
 * kernel never recorded — which metric leads, whether higher is better, what a
 * run was called — and a card that filled those in would be claiming results
 * nobody measured.
 */

import type { StoredPreview } from '@/flow/api/types'
import type {
  AssetKind,
  BlocksPreview,
  KvPreview,
  ParamValue,
  PreviewBlock,
  PreviewValue,
} from '../model/types'

/** The envelope version this build renders block for block. */
export const PREVIEW_SCHEMA = 1

export const NEWER_FORMAT_NOTE = 'newer preview format. showing the parts this build understands.'

/** Daemon kinds are an open registry; unknown ones render as the kv grid. */
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

export function previewFrom(stored: StoredPreview | null | undefined): PreviewValue {
  const kind = assetKindOf(stored?.kind)
  if (!stored || !Array.isArray(stored.blocks)) return empty(kind)
  if (!(stored.schema <= PREVIEW_SCHEMA)) return newerFormat(stored)
  const blocks = stored.blocks.map(readBlock).filter((block): block is PreviewBlock => !!block)
  return { type: 'blocks', kind, blocks, truncated: stored.truncated }
}

function empty(kind: AssetKind): BlocksPreview {
  return { type: 'blocks', kind, blocks: [] }
}

/**
 * Newer than this build: the kv grid, plus whatever entries the payload's kv
 * blocks hold. A kv block is the one primitive whose meaning cannot have been
 * re-cut under it — a name and a scalar — so reading those and saying the rest
 * is not understood beats both a blank card and a confident misdraw.
 */
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

/**
 * The kernel emits `null` for a sample it could not read as a number — a NaN
 * epoch, say. Dropping it leaves a gap in the curve; passing it through `count`
 * would draw a dip to zero the run never had.
 */
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
